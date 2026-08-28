from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .auth import (
    SESSION_COOKIE,
    AuthService,
    ConversationResponse,
    ConversationUpsert,
    LoginRateLimiter,
    LoginRequest,
    Principal,
    PublicUser,
    RegisterRequest,
    auth_required,
    clear_session_cookie,
    request_key,
    set_session_cookie,
)

from .ai_provider import AIProvider, AIProviderError, ProfileAnalysis, ProfileAnalysisCard
from .apple_health_import import (
    AppleHealthImportJob,
    AppleHealthImportSummary,
    parse_apple_health_xml,
)
from .evidence_blend import EvidenceBlendService, EuropePMCSearch
from .lifestyle import (
    ActionConfirmRequest,
    ActionConfirmResponse,
    FastRecord,
    FastStartRequest,
    ObservationCreate,
    ObservationBatchCreate,
    ObservationKind,
    ObservationRecord,
    TodaySummary,
    lifestyle_store,
)
from .health_connectors import (
    CONNECTORS,
    ConnectorId,
    ConnectorIngestRequest,
    ConnectorIngestResponse,
    ConnectorObservation,
    HealthConnector,
    get_connector,
)
from .general_search import GeneralWebSearch
from .orchestrator import OrchestrateInput, Orchestrator
from .schemas import OrchestrateResponse, StreamEvent
from .report_analysis import ReportAnalysis, ReportItem, analyze_text, extract_report_text

app = FastAPI(title="EviLife Backend", version="0.1.0")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REPORT_BYTES = 20 * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _normalized_image_type(
    declared_type: str | None,
    filename: str | None,
    payload: bytes,
) -> str | None:
    """Recover image MIME types lost by Windows clipboard/form uploads."""
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    if declared_type in SUPPORTED_IMAGE_TYPES:
        return declared_type
    extension = Path(filename or "").suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "EVILIFE_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ai_provider = AIProvider.from_env()
_orchestrator = Orchestrator(
    ai_provider=_ai_provider,
    blend_service=EvidenceBlendService(live_search=EuropePMCSearch.from_env()),
    general_search=GeneralWebSearch.from_env(),
)
_runs: dict[str, OrchestrateResponse] = {}
_run_owners: dict[str, str] = {}
_apple_import_jobs: dict[str, AppleHealthImportJob] = {}
_apple_import_owners: dict[str, str] = {}
_apple_import_lock = Lock()
MAX_APPLE_EXPORT_BYTES = 1024 * 1024 * 1024

_runtime_repository = lifestyle_store.repository
_auth_service = AuthService(_runtime_repository)
_login_limiter = LoginRateLimiter()


def _principal(request: Request) -> Principal:
    resolved = _auth_service.resolve(request.cookies.get(SESSION_COOKIE))
    if resolved is not None:
        return resolved
    if auth_required():
        raise HTTPException(status_code=401, detail="请先登录")
    _runtime_repository.ensure_subject("sub-guest", display_name="体验用户")
    return Principal(
        user_id=None,
        subject_id="sub-guest",
        email=None,
        display_name="体验用户",
    )


def _registered_principal(request: Request) -> Principal:
    resolved = _auth_service.resolve(request.cookies.get(SESSION_COOKIE))
    if resolved is None or not resolved.registered:
        raise HTTPException(status_code=401, detail="请先登录")
    return resolved


def _conversation_response(item: dict) -> ConversationResponse:
    return ConversationResponse(
        session_id=item["session_id"],
        title=item["title"],
        mode=item["mode"],
        messages=item["messages"],
        updated_at=item["updated_at"],
    )


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "evilife-backend",
        "phase": "hybrid-evidence-blend",
    }


@app.post("/api/v1/auth/register", response_model=PublicUser, status_code=201)
def register_account(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> PublicUser:
    key = request_key(request, payload.email)
    _login_limiter.check(key)
    try:
        user = _auth_service.register(payload)
    except ValueError as exc:
        _login_limiter.fail(key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    token, expires_at = _auth_service.issue_session(
        user.id, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, token, expires_at)
    _login_limiter.success(key)
    return user


@app.post("/api/v1/auth/login", response_model=PublicUser)
def login_account(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> PublicUser:
    key = request_key(request, payload.email)
    _login_limiter.check(key)
    user = _auth_service.authenticate(payload)
    if user is None:
        _login_limiter.fail(key)
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token, expires_at = _auth_service.issue_session(
        user.id, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(response, token, expires_at)
    _login_limiter.success(key)
    return user


@app.post("/api/v1/auth/logout", status_code=204)
def logout_account(request: Request, response: Response) -> Response:
    _auth_service.revoke(request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)
    response.status_code = 204
    return response


@app.get("/api/v1/auth/me", response_model=PublicUser)
def current_account(
    principal: Principal = Depends(_registered_principal),
) -> PublicUser:
    return PublicUser(
        id=principal.user_id or "",
        email=principal.email or "",
        display_name=principal.display_name,
        subject_id=principal.subject_id,
    )


# --- 设备配对（二维码）：网页端生成一次性配对码，iOS 扫码绑定同一账号 ----------
# 流程：网页端（已登录）POST /device-pairing/create 拿到 6 位码并渲染二维码；
# iOS 扫码后 POST /device-pairing/claim，服务端给手机签发该用户的会话 cookie，
# 之后手机 HealthKit（含 Apple Watch 数据）ingest 写入同一 subject_id，
# 网页端即可看到同步的健康数据。

_device_pairings: dict[str, dict] = {}
_device_pairing_codes: dict[str, str] = {}
PAIRING_TTL_SECONDS = 300


def _purge_device_pairings() -> None:
    now = datetime.now(timezone.utc)
    expired = [
        pairing_id
        for pairing_id, pairing in _device_pairings.items()
        if pairing["expires_at"] < now
    ]
    for pairing_id in expired:
        code = _device_pairings.pop(pairing_id, {}).get("code")
        if code:
            _device_pairing_codes.pop(code, None)


@app.post("/api/v1/device-pairing/create")
def create_device_pairing(
    principal: Principal = Depends(_registered_principal),
) -> dict:
    _purge_device_pairings()
    assert principal.user_id is not None
    code = "".join(
        secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6)
    )
    pairing_id = f"pair-{uuid4().hex[:12]}"
    _device_pairings[pairing_id] = {
        "user_id": principal.user_id,
        "email": principal.email or "",
        "display_name": principal.display_name,
        "subject_id": principal.subject_id,
        "code": code,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=PAIRING_TTL_SECONDS),
    }
    _device_pairing_codes[code] = pairing_id
    return {"pairing_id": pairing_id, "code": code, "expires_in": PAIRING_TTL_SECONDS}


class DevicePairingClaim(BaseModel):
    code: str = Field(min_length=4, max_length=16)
    # login：手机登录为该账号（默认，subject 相同 → 后续同步即对方账号）
    # transfer：手机保持当前登录，返回一次性传输令牌，把数据批量写入对方账号
    mode: Literal["login", "transfer"] = "login"


_transfer_tokens: dict[str, dict] = {}
TRANSFER_TOKEN_TTL_SECONDS = 24 * 3600


@app.post("/api/v1/device-pairing/claim")
def claim_device_pairing(
    payload: DevicePairingClaim,
    request: Request,
    response: Response,
) -> dict:
    code = payload.code.strip().upper()
    pairing_id = _device_pairing_codes.pop(code, None)
    if pairing_id is None:
        raise HTTPException(status_code=404, detail="配对码无效或已过期")
    pairing = _device_pairings.pop(pairing_id, None)
    if pairing is None or pairing["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="配对码无效或已过期")

    target_user = PublicUser(
        id=pairing["user_id"],
        email=pairing["email"],
        display_name=pairing["display_name"],
        subject_id=pairing["subject_id"],
    )

    if payload.mode == "transfer":
        token = secrets.token_urlsafe(24)
        _transfer_tokens[token] = {
            "user_id": pairing["user_id"],
            "subject_id": pairing["subject_id"],
            "email": pairing["email"],
            "display_name": pairing["display_name"],
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=TRANSFER_TOKEN_TTL_SECONDS),
        }
        return {
            "mode": "transfer",
            "transfer_token": token,
            "expires_in": TRANSFER_TOKEN_TTL_SECONDS,
            "target": target_user.model_dump(mode="json"),
        }

    token, expires_at = _auth_service.issue_session(
        pairing["user_id"],
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, token, expires_at)
    return {"mode": "login", "user": target_user.model_dump(mode="json")}


class DevicePairingTransfer(BaseModel):
    transfer_token: str = Field(min_length=8, max_length=128)
    consent_receipt: str = Field(min_length=8, max_length=240)
    observations: list[ConnectorObservation] = Field(min_length=1, max_length=500)


@app.post(
    "/api/v1/device-pairing/transfer-data",
    response_model=ConnectorIngestResponse,
)
def transfer_device_data(payload: DevicePairingTransfer) -> ConnectorIngestResponse:
    """把手机端数据写入扫码目标账号（跨账号传输，保留手机自身登录态）。"""
    link = _transfer_tokens.get(payload.transfer_token.strip())
    if link is None or link["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="传输令牌无效或已过期")
    records: list[ObservationRecord] = []
    accepted = 0
    for item in payload.observations:
        record, created = lifestyle_store.add_device_observation(
            item.observation,
            connector_id="apple_healthkit",
            external_id=item.external_id,
            subject_id=link["subject_id"],
        )
        records.append(record)
        accepted += int(created)
    return ConnectorIngestResponse(
        connector_id="apple_healthkit",
        accepted=accepted,
        skipped=len(records) - accepted,
        records=records,
    )


@app.get("/api/v1/conversations", response_model=list[ConversationResponse])
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(_registered_principal),
) -> list[ConversationResponse]:
    assert principal.user_id is not None
    return [
        _conversation_response(item)
        for item in _runtime_repository.list_conversations(principal.user_id, limit)
    ]


@app.put(
    "/api/v1/conversations/{session_id}",
    response_model=ConversationResponse,
)
def save_conversation(
    session_id: str,
    payload: ConversationUpsert,
    principal: Principal = Depends(_registered_principal),
) -> ConversationResponse:
    if payload.session_id != session_id:
        raise HTTPException(status_code=422, detail="session_id不一致")
    assert principal.user_id is not None
    item = _runtime_repository.upsert_conversation(
        user_id=principal.user_id,
        session_id=session_id,
        title=payload.title,
        mode=payload.mode,
        messages=[message.model_dump(mode="json") for message in payload.messages],
    )
    return _conversation_response(item)


@app.delete("/api/v1/conversations/{session_id}", status_code=204)
def delete_conversation(
    session_id: str,
    principal: Principal = Depends(_registered_principal),
) -> Response:
    assert principal.user_id is not None
    deleted = _runtime_repository.delete_conversation(principal.user_id, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="对话不存在")
    return Response(status_code=204)


@app.post("/api/v1/fasts/start", response_model=FastRecord)
def start_fast(
    request: FastStartRequest,
    principal: Principal = Depends(_principal),
) -> FastRecord:
    try:
        return lifestyle_store.start_fast(
            request.goal_hours, subject_id=principal.subject_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/fasts/active", response_model=FastRecord | None)
def get_active_fast(
    principal: Principal = Depends(_principal),
) -> FastRecord | None:
    return lifestyle_store.active_fast(subject_id=principal.subject_id)


@app.get("/api/v1/fasts", response_model=list[FastRecord])
def list_fasts(
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(_principal),
) -> list[FastRecord]:
    return lifestyle_store.list_fasts(limit, subject_id=principal.subject_id)


@app.post("/api/v1/fasts/{fast_id}/end", response_model=FastRecord)
def end_fast(
    fast_id: str,
    principal: Principal = Depends(_principal),
) -> FastRecord:
    try:
        return lifestyle_store.end_fast(fast_id, subject_id=principal.subject_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="active timer not found") from exc


@app.post(
    "/api/v1/actions/{action_id}/confirm",
    response_model=ActionConfirmResponse,
)
def confirm_action(
    action_id: str,
    request: ActionConfirmRequest,
    principal: Principal = Depends(_principal),
) -> ActionConfirmResponse:
    return lifestyle_store.confirm_action(
        action_id, request, subject_id=principal.subject_id
    )


@app.get("/api/v1/today", response_model=TodaySummary)
def get_today(
    selected_date: date = Query(alias="date"),
    principal: Principal = Depends(_principal),
) -> TodaySummary:
    return lifestyle_store.today(selected_date, subject_id=principal.subject_id)


@app.post("/api/v1/observations", response_model=ObservationRecord)
def add_observation(
    request: ObservationCreate,
    principal: Principal = Depends(_principal),
) -> ObservationRecord:
    return lifestyle_store.add_observation(
        request, subject_id=principal.subject_id
    )


@app.post("/api/v1/observations/batch", response_model=list[ObservationRecord])
def add_observation_batch(
    request: ObservationBatchCreate,
    principal: Principal = Depends(_principal),
) -> list[ObservationRecord]:
    return lifestyle_store.add_observations(
        request.observations, subject_id=principal.subject_id
    )


@app.get("/api/v1/observations", response_model=list[ObservationRecord])
def list_observations(
    kind: ObservationKind | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=5000),
    principal: Principal = Depends(_principal),
) -> list[ObservationRecord]:
    return lifestyle_store.list_observations(
        kind=kind, limit=limit, subject_id=principal.subject_id
    )


@app.delete("/api/v1/observations/{observation_id}", response_model=ObservationRecord)
def delete_observation(
    observation_id: str,
    principal: Principal = Depends(_principal),
) -> ObservationRecord:
    try:
        return lifestyle_store.delete_observation(
            observation_id, subject_id=principal.subject_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="observation not found") from exc


@app.get("/api/v1/health-connectors", response_model=list[HealthConnector])
def list_health_connectors() -> list[HealthConnector]:
    return CONNECTORS


def _run_apple_health_import(
    job_id: str,
    path: Path,
    source_name: str,
    subject_id: str,
) -> None:
    try:
        with _apple_import_lock:
            _apple_import_jobs[job_id].status = "running"

        def update_progress(count: int) -> None:
            with _apple_import_lock:
                _apple_import_jobs[job_id].processed_records = count

        parsed = parse_apple_health_xml(path, progress=update_progress)
        accepted, skipped = lifestyle_store.add_device_observations_bulk(
            parsed.observations,
            connector_id="apple_healthkit",
            subject_id=subject_id,
        )
        counts = Counter(request.kind for _, request in parsed.observations)
        summary = AppleHealthImportSummary(
            source_file=source_name,
            processed_records=parsed.processed_records,
            accepted=accepted,
            skipped=skipped,
            date_from=parsed.date_from,
            date_to=parsed.date_to,
            counts=dict(counts),
        )
        with _apple_import_lock:
            job = _apple_import_jobs[job_id]
            job.status = "completed"
            job.processed_records = parsed.processed_records
            job.summary = summary
    except Exception:
        with _apple_import_lock:
            job = _apple_import_jobs[job_id]
            job.status = "failed"
            job.error = "Apple 健康导出文件解析失败，请确认选择的是原始导出 XML。"
    finally:
        path.unlink(missing_ok=True)


@app.post("/api/v1/reports/analyze", response_model=ReportAnalysis)
async def analyze_medical_report(
    file: UploadFile = File(...),
    principal: Principal = Depends(_principal),
) -> ReportAnalysis:
    payload = await file.read(MAX_REPORT_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(payload) > MAX_REPORT_BYTES:
        raise HTTPException(status_code=413, detail="体检报告不能超过 20 MB")
    filename = Path(file.filename or "report").name
    mime_type = (file.content_type or "application/octet-stream").lower()
    allowed = mime_type in {
        "application/pdf", "text/plain", "text/csv",
        "image/jpeg", "image/png", "image/webp",
    }
    if not allowed:
        raise HTTPException(status_code=415, detail="支持 PDF、TXT、CSV、JPG、PNG 和 WebP")

    digest = hashlib.sha256(payload).hexdigest()
    report, _ = _runtime_repository.create_report(
        principal.subject_id,
        sha256=digest,
        mime_type=mime_type,
        size_bytes=len(payload),
        storage_key=f"ephemeral:{digest}",
    )
    if mime_type.startswith("image/"):
        if _ai_provider is None:
            result = analyze_text("", filename)
            result.limitations.insert(0, "当前部署未配置独立视觉服务，图片尚未识别。")
        else:
            try:
                raw = await _ai_provider.read_medical_report_image(
                    payload, content_type=mime_type
                )
                result = ReportAnalysis(
                    file_name=filename,
                    source="deepseek_vl2",
                    summary=str(raw.get("summary") or "已完成报告图片结构化抄录。"),
                    items=[ReportItem.model_validate(item) for item in raw.get("items", [])],
                    limitations=[str(item) for item in raw.get("limitations", [])]
                    + ["视觉模型结果必须与原报告逐项核对，不构成诊断。"],
                )
            except (AIProviderError, ValueError):
                result = analyze_text("", filename)
                result.limitations.insert(0, "视觉服务暂不可用，图片未被可靠识别。")
    else:
        result = analyze_text(extract_report_text(payload, mime_type, filename), filename)

    result.report_id = report["id"]
    _runtime_repository.save_report_analysis(
        principal.subject_id,
        result.report_id,
        model=result.source,
        summary=result.summary,
        items=[item.model_dump() for item in result.items],
        limitations=result.limitations,
    )
    return result


@app.get("/api/v1/reports")
def list_medical_reports(
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(_principal),
) -> list[dict]:
    return _runtime_repository.list_report_analyses(principal.subject_id, limit)


@app.post("/api/v1/health-imports/apple", response_model=AppleHealthImportJob)
def start_apple_health_import(
    background_tasks: BackgroundTasks,
    export: UploadFile = File(...),
    principal: Principal = Depends(_principal),
) -> AppleHealthImportJob:
    name = Path(export.filename or "apple-health.xml").name
    if not name.lower().endswith(".xml"):
        raise HTTPException(status_code=415, detail="请选择 Apple 健康导出的 XML 文件")
    job_id = f"apple-import-{uuid4().hex[:12]}"
    destination = Path(tempfile.gettempdir()) / f"{job_id}.xml"
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := export.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_APPLE_EXPORT_BYTES:
                    raise HTTPException(status_code=413, detail="Apple 健康导出文件超过 1 GB 限制")
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        export.file.close()
    try:
        prefix = destination.open("rb").read(256)
        if b"<HealthData" not in prefix and b"<?xml" not in prefix:
            raise HTTPException(status_code=422, detail="文件不是有效的 Apple 健康 XML")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    job = AppleHealthImportJob(id=job_id, status="queued")
    with _apple_import_lock:
        _apple_import_jobs[job_id] = job
        _apple_import_owners[job_id] = principal.subject_id
    background_tasks.add_task(
        _run_apple_health_import,
        job_id,
        destination,
        name,
        principal.subject_id,
    )
    return job


@app.get("/api/v1/health-imports/apple/{job_id}", response_model=AppleHealthImportJob)
def get_apple_health_import(
    job_id: str,
    principal: Principal = Depends(_principal),
) -> AppleHealthImportJob:
    with _apple_import_lock:
        job = _apple_import_jobs.get(job_id)
        if job is None or _apple_import_owners.get(job_id) != principal.subject_id:
            raise HTTPException(status_code=404, detail="import job not found")
        return job.model_copy(deep=True)


@app.post(
    "/api/v1/health-connectors/{connector_id}/ingest",
    response_model=ConnectorIngestResponse,
)
def ingest_health_observations(
    connector_id: ConnectorId,
    request: ConnectorIngestRequest,
    principal: Principal = Depends(_principal),
) -> ConnectorIngestResponse:
    connector = get_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="connector not found")
    records: list[ObservationRecord] = []
    accepted = 0
    for item in request.observations:
        record, created = lifestyle_store.add_device_observation(
            item.observation,
            connector_id=connector_id,
            external_id=item.external_id,
            subject_id=principal.subject_id,
        )
        records.append(record)
        accepted += int(created)
    return ConnectorIngestResponse(
        connector_id=connector_id,
        accepted=accepted,
        skipped=len(records) - accepted,
        records=records,
    )


def _fallback_profile_analysis(observations: list[ObservationRecord]) -> ProfileAnalysis:
    summary = _profile_summary(observations)
    return ProfileAnalysis(
        cards=[
            ProfileAnalysisCard(
                tone="summary",
                title="综合健康分析",
                preview=summary["overview"],
                details=[
                    {"label": "分析依据", "value": summary["basis"]},
                    {"label": "整体趋势", "value": summary["trend"]},
                    {"label": "需关注信号", "value": summary["alerts"]},
                    {"label": "生活建议", "value": summary["advice"]},
                    {"label": "复测建议", "value": "尽量在相近条件下持续记录；单次偏离先复测，不把设备值直接当诊断。"},
                    {"label": "就医提醒", "value": "若异常反复、持续或伴胸痛、呼吸困难、晕厥、意识改变等，请及时就医；严重时立即联系急救。"},
                    {"label": "分析边界", "value": "未纳入年龄、病史、药物、妊娠和运动员状态，结论仅用于健康记录整理。"},
                ],
            ),
        ]
    )


def _profile_summary(observations: list[ObservationRecord]) -> dict[str, str]:
    numeric = [item for item in observations if item.kind != "note" and item.value is not None]
    kinds = sorted({item.kind for item in numeric})
    ordered = sorted(numeric, key=lambda item: item.observed_at)
    date_from = ordered[0].observed_at.date().isoformat() if ordered else "暂无"
    date_to = ordered[-1].observed_at.date().isoformat() if ordered else "暂无"
    grouped: dict[str, list[ObservationRecord]] = {}
    for item in ordered:
        grouped.setdefault(item.kind, []).append(item)
    alerts: list[str] = []
    heart = grouped.get("resting_heart_rate", [])[-7:]
    if heart:
        average = sum(float(item.value or 0) for item in heart) / len(heart)
        if average < 60 or average > 100:
            alerts.append(f"最近静息心率均值约 {average:.0f} 次/分，超出多数成人常见的静息范围；运动员、药物和身体状态会改变解释，建议在安静状态复测")
    sleep = grouped.get("sleep_minutes", [])[-7:]
    if sleep:
        average = sum(float(item.value or 0) for item in sleep) / len(sleep)
        if average < 360:
            alerts.append(f"最近睡眠记录均值约 {average / 60:.1f} 小时，持续偏短值得关注")
    mood = grouped.get("mood_score", [])[-7:]
    if mood:
        average = sum(float(item.value or 0) for item in mood) / len(mood)
        if average <= 2:
            alerts.append("近期情绪评分持续较低；若影响生活或出现伤害自己的想法，请尽快寻求专业帮助")
    weight = grouped.get("weight_kg", [])
    recent_weight = [item for item in weight if weight and item.observed_at >= weight[-1].observed_at - timedelta(days=90)]
    if len(recent_weight) >= 2 and float(recent_weight[0].value or 0) > 0:
        change = (float(recent_weight[-1].value or 0) - float(recent_weight[0].value or 0)) / float(recent_weight[0].value or 1) * 100
        if abs(change) >= 5:
            alerts.append(f"最近 90 天可比记录中的体重变化约 {change:+.1f}%；若非主动计划或伴不适，建议核对测量条件并咨询医生")
    alert_text = "；".join(alerts) if alerts else "基于现有数值暂未标记到明确的持续偏离；这不等于排除疾病，缺失数据也不能当作正常。"
    latest = {kind: records[-1].value for kind, records in grouped.items() if records}
    trend_bits = []
    for kind, label, unit in (("steps", "步数", "步"), ("sleep_minutes", "睡眠", "分钟"), ("weight_kg", "体重", "kg"), ("resting_heart_rate", "静息心率", "次/分")):
        if kind in latest:
            trend_bits.append(f"{label}最近为 {latest[kind]:g} {unit}")
    return {
        "overview": f"综合 {len(numeric)} 条客观记录、{len(kinds)} 类指标，优先提示持续变化与需要复测的信号。",
        "basis": f"使用 {date_from} 至 {date_to} 的全部 {len(numeric)} 条数值记录；自由文本备注未发送给 AI。",
        "trend": "；".join(trend_bits) or "可用连续数据不足，暂不能描述趋势。",
        "alerts": alert_text,
        "advice": "保持规律睡眠与进餐、循序增加日常活动、按需饮水；优先做一两项可持续改变，并用连续记录观察变化。",
        "raw": {"record_count": len(numeric), "kinds": kinds, "date_from": date_from, "date_to": date_to, "latest": latest, "alerts": alerts},
    }


@app.post("/api/v1/profile/analyze")
async def analyze_profile(
    principal: Principal = Depends(_principal),
) -> dict:
    observations = [
        item
        for item in lifestyle_store.list_observations(
            limit=5000, subject_id=principal.subject_id
        )
        if item.kind != "note"
    ]
    summary = _profile_summary(observations)
    safe_payload = [{"history_summary": summary["raw"], "program_attention_signals": summary["alerts"], "recent_records": [
        {"kind": item.kind, "value": item.value, "source": item.source, "observed_at": item.observed_at.isoformat()}
        for item in observations[:60]
    ]}]
    if _ai_provider is not None:
        try:
            analysis = await _ai_provider.analyze_profile(safe_payload)
            return {"source": "ai", "cards": analysis.cards}
        except AIProviderError:
            pass
    fallback = _fallback_profile_analysis(observations)
    return {"source": "deterministic_fallback", "cards": fallback.cards}


@app.post("/api/v1/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    principal: Principal = Depends(_principal),
    session_id: str = Form(...),
    mode: Literal[
        "auto",
        "fast",
        "deep",
        "evaluation",
        "general",
        "rag",
        "always_deep",
        "eviroute_gate",
    ] = Form("auto"),
    text: str | None = Form(None),
    image: UploadFile | None = File(None),
    document: UploadFile | None = File(None),
) -> OrchestrateResponse:
    normalized_text = text.strip() if text else None
    if not normalized_text and image is None and document is None:
        raise HTTPException(status_code=422, detail="text, image or document is required")
    if image is not None and document is not None:
        raise HTTPException(status_code=422, detail="MVP accepts at most one attachment per turn")

    image_bytes: bytes | None = None
    image_content_type: str | None = None
    if image is not None:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        if not image_bytes:
            raise HTTPException(status_code=422, detail="image is empty")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="image exceeds 10 MB")
        image_content_type = _normalized_image_type(
            image.content_type,
            image.filename,
            image_bytes,
        )
        if image_content_type not in SUPPORTED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="unsupported image type")

    response = await _orchestrator.run_async(
        OrchestrateInput(
            session_id=session_id,
            text=normalized_text,
            has_image=image is not None,
            has_document=document is not None,
            mode=mode,
            attachment_name=(document or image).filename if (document or image) else None,
            attachment_content_type=image_content_type,
            attachment_bytes=image_bytes,
        )
    )
    _runs[response.run_id] = response
    _run_owners[response.run_id] = principal.subject_id
    return response


@app.get("/api/v1/runs/{run_id}", response_model=OrchestrateResponse)
def get_run(
    run_id: str,
    principal: Principal = Depends(_principal),
) -> OrchestrateResponse:
    run = _runs.get(run_id)
    if run is None or _run_owners.get(run_id) != principal.subject_id:
        raise HTTPException(status_code=404, detail="run not found")
    return run


def _event(run: OrchestrateResponse, event_type: str, payload: dict | None = None) -> StreamEvent:
    return StreamEvent(
        event_id=f"evt-{uuid4().hex[:12]}",
        request_id=run.request_id,
        run_id=run.run_id,
        type=event_type,  # type: ignore[arg-type]
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    )


@app.get("/api/v1/runs/{run_id}/events")
def run_events(
    run_id: str,
    principal: Principal = Depends(_principal),
) -> StreamingResponse:
    run = _runs.get(run_id)
    if run is None or _run_owners.get(run_id) != principal.subject_id:
        raise HTTPException(status_code=404, detail="run not found")

    async def stream():
        module = next(
            (item for item in run.module_plan if item.type == "EvidenceAnswer"),
            run.module_plan[0],
        )
        packet_id = module.props.get("packet_id")
        topic = module.props.get("topic")
        route = (
            run.route
            if run.route == "deep_path"
            else module.props.get("source") or run.route
        ) or (
            "fast_path"
            if packet_id
            else "safety_refusal"
            if run.gate_status == "refused"
            else "mock"
        )
        events = [
            _event(run, "run.started", {"status": "running"}),
            _event(
                run,
                "route.selected",
                {
                    "route": route,
                    "mode": run.mode,
                    "topic": topic or "unknown",
                    "route_ms": run.timing_ms.get("route_ms", 0),
                },
            ),
        ]
        if packet_id:
            events.append(
                _event(
                    run,
                    "evidence.snapshot",
                    {
                        "packet_id": packet_id,
                        "topic": topic,
                        "evidence_strength": module.props["evidence_strength"],
                        "citations": module.props["citations"],
                        "route": route,
                        "evidence_count": run.evidence_count,
                        "support_evidence_count": run.support_evidence_count,
                        "boundary_evidence_count": run.boundary_evidence_count,
                        "queries": module.props.get("queries"),
                        "evidence_mix": module.props.get("evidence_mix"),
                    },
                )
            )
        events.extend(
            [
                _event(
                    run,
                    "gate.completed",
                    {
                        "status": run.gate_status,
                        "route": route,
                        "evidence_count": run.evidence_count,
                        "verify_ms": run.timing_ms.get("verify_ms", 0),
                    },
                ),
                _event(
                    run,
                    "module.ready",
                    {
                        "module_plan": [
                            item.model_dump(mode="json") for item in run.module_plan
                        ]
                    },
                ),
                _event(run, "run.completed", {"status": "completed"}),
            ]
        )
        for event in events:
            yield f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)

        _runs[run.run_id] = run.model_copy(update={"status": "completed"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
