"""Objective lifestyle records that never produce medical recommendations."""

from __future__ import annotations

from datetime import date, datetime, timezone
import os
from pathlib import Path

from .db.connection import runtime_db_path
from .db.runtime_repository import RuntimeRepository
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FastStartRequest(BaseModel):
    goal_hours: float = Field(default=16, ge=1, le=24)


class FastRecord(BaseModel):
    id: str
    start_at: datetime
    end_at: datetime | None = None
    goal_hours: float
    status: Literal["active", "completed"]


class MealItemInput(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=80)
    portion: str = Field(min_length=1, max_length=80)
    portion_grams: tuple[int, int] | None = None
    estimated_calories: tuple[int, int]
    estimated_calories_center: int | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    reference_basis: str | None = Field(default=None, max_length=240)
    uncertainty: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_range(self) -> "MealItemInput":
        low, high = self.estimated_calories
        if low < 0 or high < low:
            raise ValueError("estimated calorie range must be ordered and non-negative")
        if self.estimated_calories_center is None:
            self.estimated_calories_center = round((low + high) / 2)
        if not low <= self.estimated_calories_center <= high:
            raise ValueError("estimated calorie center must be inside range")
        return self


class ActionConfirmRequest(BaseModel):
    run_id: str
    confirmed: bool
    client_action_id: str
    edited_items: list[MealItemInput] = Field(default_factory=list)
    estimated_total_calories: tuple[int, int] | None = None
    estimated_total_calories_center: int | None = None


class MealRecord(BaseModel):
    id: str
    action_id: str
    created_at: datetime
    items: list[MealItemInput]
    estimated_total_calories: tuple[int, int]
    estimated_total_calories_center: int | None = None
    status: Literal["confirmed"] = "confirmed"

    @model_validator(mode="after")
    def fill_total_center(self) -> "MealRecord":
        if self.estimated_total_calories_center is None:
            low, high = self.estimated_total_calories
            self.estimated_total_calories_center = round((low + high) / 2)
        return self


ObservationKind = Literal[
    "water_ml",
    "steps",
    "sleep_minutes",
    "weight_kg",
    "waist_cm",
    "resting_heart_rate",
    "mood_score",
    "note",
]
ObservationSource = Literal["self_report", "device", "ai_estimate"]


class ObservationCreate(BaseModel):
    kind: ObservationKind
    value: float | None = None
    note: str | None = Field(default=None, max_length=500)
    source: ObservationSource = "self_report"
    observed_at: datetime | None = None
    connector_id: str | None = Field(default=None, max_length=80)
    external_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_observation(self) -> "ObservationCreate":
        if self.kind == "note":
            if not self.note or not self.note.strip():
                raise ValueError("note is required")
            return self
        if self.value is None or self.value < 0:
            raise ValueError("a non-negative value is required")
        if self.kind == "mood_score" and not 1 <= self.value <= 5:
            raise ValueError("mood score must be between 1 and 5")
        return self


class ObservationRecord(BaseModel):
    id: str
    kind: ObservationKind
    value: float | None = None
    note: str | None = None
    source: ObservationSource
    observed_at: datetime
    connector_id: str | None = None
    external_id: str | None = None


class ObservationBatchCreate(BaseModel):
    observations: list[ObservationCreate] = Field(min_length=1, max_length=20)


class ActionConfirmResponse(BaseModel):
    action_id: str
    status: Literal["completed", "cancelled"]
    affected_resource: dict[str, str] | None = None


class TodaySummary(BaseModel):
    date: date
    fasts: list[FastRecord]
    meals: list[MealRecord]
    observations: list[ObservationRecord]


class LifestyleStore:
    """User-scoped SQLite store preserving the existing public API."""

    def __init__(
        self,
        storage_path: Path | None = None,
        *,
        default_subject_id: str = "sub-guest",
    ) -> None:
        self.default_subject_id = default_subject_id
        legacy_path: Path | None = None
        if storage_path is not None and storage_path.suffix.lower() == ".json":
            legacy_path = storage_path
            database_path = storage_path.with_suffix(".sqlite3")
        else:
            database_path = storage_path or runtime_db_path()
        self.repository = RuntimeRepository(database_path)
        self.repository.ensure_subject(default_subject_id)
        if legacy_path is not None and legacy_path.is_file():
            self.repository.import_legacy_lifestyle_json(legacy_path, default_subject_id)

    @classmethod
    def from_env(cls) -> "LifestyleStore":
        configured_db = os.getenv("EVILIFE_RUNTIME_DB", "").strip()
        store = cls(Path(configured_db).expanduser().resolve() if configured_db else None)
        legacy = os.getenv("EVILIFE_LIFESTYLE_STORE", "").strip()
        if legacy:
            legacy_path = Path(legacy).expanduser().resolve()
            if legacy_path.is_file():
                store.repository.import_legacy_lifestyle_json(
                    legacy_path, store.default_subject_id
                )
        return store

    def _subject(self, subject_id: str | None) -> str:
        return subject_id or self.default_subject_id

    @staticmethod
    def _fast(row: dict) -> FastRecord:
        return FastRecord.model_validate(row)

    @staticmethod
    def _observation(row: dict) -> ObservationRecord:
        return ObservationRecord.model_validate(row)

    @staticmethod
    def _meal(row: dict) -> MealRecord:
        items = [
            MealItemInput(
                id=item["id"],
                name=item["name"],
                portion=item["portion"],
                portion_grams=(
                    (item["portion_grams_low"], item["portion_grams_high"])
                    if item.get("portion_grams_low") is not None
                    and item.get("portion_grams_high") is not None
                    else None
                ),
                estimated_calories=(item["calories_low"], item["calories_high"]),
                estimated_calories_center=item["calories_center"],
                confidence=item.get("confidence"),
                reference_basis=item.get("reference_basis"),
                uncertainty=item.get("uncertainty"),
            )
            for item in row["items"]
        ]
        return MealRecord(
            id=row["id"],
            action_id=row["action_id"],
            created_at=row["created_at"],
            items=items,
            estimated_total_calories=(row["calories_low"], row["calories_high"]),
            estimated_total_calories_center=row["calories_center"],
            status="confirmed",
        )

    def start_fast(self, goal_hours: float, *, subject_id: str | None = None) -> FastRecord:
        return self._fast(
            self.repository.start_fast(self._subject(subject_id), goal_hours)
        )

    def active_fast(self, *, subject_id: str | None = None) -> FastRecord | None:
        row = self.repository.active_fast(self._subject(subject_id))
        return self._fast(row) if row is not None else None

    def end_fast(self, fast_id: str, *, subject_id: str | None = None) -> FastRecord:
        return self._fast(
            self.repository.end_fast(self._subject(subject_id), fast_id)
        )

    def list_fasts(
        self,
        limit: int = 20,
        *,
        subject_id: str | None = None,
    ) -> list[FastRecord]:
        return [
            self._fast(row)
            for row in self.repository.list_fasts(self._subject(subject_id), limit)
        ]

    def confirm_action(
        self,
        action_id: str,
        request: ActionConfirmRequest,
        *,
        subject_id: str | None = None,
    ) -> ActionConfirmResponse:
        if not request.confirmed:
            return ActionConfirmResponse(action_id=action_id, status="cancelled")

        low = sum(item.estimated_calories[0] for item in request.edited_items)
        high = sum(item.estimated_calories[1] for item in request.edited_items)
        total = request.estimated_total_calories or (low, high)
        total_center = request.estimated_total_calories_center
        if total_center is None:
            total_center = sum(
                item.estimated_calories_center or 0 for item in request.edited_items
            )
        if not total[0] <= total_center <= total[1]:
            raise ValueError("estimated total calorie center must be inside range")
        meal = self.repository.create_meal(
            self._subject(subject_id),
            action_id=action_id,
            items=[item.model_dump(mode="json") for item in request.edited_items],
            calorie_range=total,
            calorie_center=total_center,
        )
        return ActionConfirmResponse(
            action_id=action_id,
            status="completed",
            affected_resource={"type": "meal_record", "id": meal["id"]},
        )

    def add_observation(
        self,
        request: ObservationCreate,
        *,
        subject_id: str | None = None,
    ) -> ObservationRecord:
        payload = request.model_dump(mode="json")
        payload["note"] = request.note.strip() if request.note else None
        payload["observed_at"] = (
            request.observed_at or datetime.now(timezone.utc)
        ).isoformat()
        row, _ = self.repository.add_observation(self._subject(subject_id), payload)
        return self._observation(row)

    def add_device_observations_bulk(
        self,
        items: list[tuple[str, ObservationCreate]],
        *,
        connector_id: str,
        subject_id: str | None = None,
    ) -> tuple[int, int]:
        payloads = []
        for external_id, request in items:
            payload = request.model_dump(mode="json")
            payload["observed_at"] = (
                request.observed_at or datetime.now(timezone.utc)
            ).isoformat()
            payloads.append((external_id, payload))
        accepted, skipped, _ = self.repository.import_device_observations(
            self._subject(subject_id), connector_id, payloads
        )
        return accepted, skipped

    def add_observations(
        self,
        requests: list[ObservationCreate],
        *,
        subject_id: str | None = None,
    ) -> list[ObservationRecord]:
        payloads: list[dict] = []
        for request in requests:
            payload = request.model_dump(mode="json")
            payload["note"] = request.note.strip() if request.note else None
            payload["observed_at"] = (
                request.observed_at or datetime.now(timezone.utc)
            ).isoformat()
            payloads.append(payload)
        rows, _, _ = self.repository.add_observations(
            self._subject(subject_id), payloads
        )
        return [self._observation(row) for row in rows]

    def add_device_observation(
        self,
        request: ObservationCreate,
        *,
        connector_id: str,
        external_id: str,
        subject_id: str | None = None,
    ) -> tuple[ObservationRecord, bool]:
        payload = request.model_dump(mode="json")
        payload.update(
            {
                "source": "device",
                "connector_id": connector_id,
                "external_id": external_id,
                "observed_at": (
                    request.observed_at or datetime.now(timezone.utc)
                ).isoformat(),
            }
        )
        row, created = self.repository.add_observation(
            self._subject(subject_id), payload
        )
        return self._observation(row), created

    def delete_observation(
        self,
        observation_id: str,
        *,
        subject_id: str | None = None,
    ) -> ObservationRecord:
        return self._observation(
            self.repository.delete_observation(
                self._subject(subject_id), observation_id
            )
        )

    def list_observations(
        self,
        *,
        kind: ObservationKind | None = None,
        limit: int = 100,
        subject_id: str | None = None,
    ) -> list[ObservationRecord]:
        return [
            self._observation(row)
            for row in self.repository.list_observations(
                self._subject(subject_id), kind=kind, limit=limit
            )
        ]

    def today(
        self,
        selected_date: date,
        *,
        subject_id: str | None = None,
    ) -> TodaySummary:
        subject = self._subject(subject_id)
        fasts = [
            record
            for record in self.list_fasts(limit=100, subject_id=subject)
            if record.start_at.date() == selected_date
        ]
        meals = [
            self._meal(row)
            for row in self.repository.list_meals(subject, selected_date)
        ]
        observations = [
            self._observation(row)
            for row in self.repository.list_observations(subject, limit=5000)
            if datetime.fromisoformat(row["observed_at"]).date() == selected_date
        ]
        return TodaySummary(
            date=selected_date,
            fasts=fasts,
            meals=meals,
            observations=observations,
        )


lifestyle_store = LifestyleStore.from_env()

