from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from .db.runtime_repository import RuntimeRepository


SESSION_COOKIE = "evilife_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("请输入有效邮箱")
        return normalized

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def require_password_variety(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("密码首尾不能包含空格")
        if not any(character.isalpha() for character in value) or not any(
            character.isdigit() for character in value
        ):
            raise ValueError("密码至少包含一个字母和一个数字")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PublicUser(BaseModel):
    id: str
    email: str
    display_name: str
    subject_id: str


class AccountSummary(BaseModel):
    user: PublicUser
    total_accounts: int
    registered_at: str | None = None
    last_login_at: str | None = None


class ConversationMessage(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    role: Literal["user", "assistant"]
    content: str | None = Field(default=None, max_length=20_000)
    file: dict[str, str] | None = None
    modulePlan: list[dict] | None = None


class ConversationUpsert(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    mode: Literal["life", "professional"] = "life"
    messages: list[ConversationMessage] = Field(min_length=1, max_length=200)


class ConversationResponse(ConversationUpsert):
    updated_at: str


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    subject_id: str
    email: str | None
    display_name: str
    session_id: str | None = None

    @property
    def registered(self) -> bool:
        return self.user_id is not None


class LoginRateLimiter:
    """Small single-process guard; production edge rate limiting is still recommended."""

    def __init__(self, *, attempts: int = 8, window_seconds: int = 900) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._failures: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            recent = [
                value
                for value in self._failures.get(key, [])
                if now - value < self.window_seconds
            ]
            self._failures[key] = recent
            if len(recent) >= self.attempts:
                raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试")

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(monotonic())

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


class AuthService:
    def __init__(self, repository: RuntimeRepository) -> None:
        self.repository = repository
        self.passwords = PasswordHasher(
            time_cost=2,
            memory_cost=19_456,
            parallelism=1,
            hash_len=32,
            salt_len=16,
        )

    @staticmethod
    def _public(user: dict) -> PublicUser:
        return PublicUser(
            id=user["id"],
            email=user["email"],
            display_name=user["display_name"],
            subject_id=user["subject_id"],
        )

    def register(self, request: RegisterRequest) -> PublicUser:
        password_hash = self.passwords.hash(request.password)
        user = self.repository.create_user(
            request.email, request.display_name, password_hash
        )
        return self._public(user)

    def authenticate(self, request: LoginRequest) -> PublicUser | None:
        user = self.repository.get_user_by_email(request.email)
        if user is None or not user["is_active"]:
            return None
        try:
            valid = self.passwords.verify(user["password_hash"], request.password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None
        if not valid:
            return None
        if self.passwords.check_needs_rehash(user["password_hash"]):
            self.repository.update_password_hash(
                user["id"], self.passwords.hash(request.password)
            )
        self.repository.mark_login(user["id"])
        return self._public(user)

    def issue_session(
        self,
        user_id: str,
        *,
        user_agent: str | None,
    ) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        days = max(1, min(30, int(os.getenv("EVILIFE_SESSION_DAYS", "14"))))
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        self.repository.create_auth_session(
            user_id,
            token_hash,
            expires_at.isoformat(),
            user_agent=(user_agent or "")[:300] or None,
        )
        return token, expires_at

    def resolve(self, token: str | None) -> Principal | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        session = self.repository.resolve_auth_session(
            token_hash, datetime.now(timezone.utc).isoformat()
        )
        if session is None:
            return None
        self.repository.touch_auth_session(session["session_id"])
        return Principal(
            user_id=session["user_id"],
            subject_id=session["subject_id"],
            email=session["email"],
            display_name=session["display_name"],
            session_id=session["session_id"],
        )

    def revoke(self, token: str | None) -> None:
        if token:
            self.repository.revoke_auth_session(
                hashlib.sha256(token.encode("utf-8")).hexdigest()
            )


def auth_required() -> bool:
    return os.getenv("EVILIFE_AUTH_REQUIRED", "false").strip().lower() == "true"


def cookie_secure() -> bool:
    return os.getenv("EVILIFE_COOKIE_SECURE", "false").strip().lower() == "true"


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        expires=expires_at,
        max_age=max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds())),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
    )


def request_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"{host}|{email}".encode("utf-8")).hexdigest()
