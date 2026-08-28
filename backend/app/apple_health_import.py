"""Streaming Apple Health XML import with conservative daily aggregation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from xml.etree.ElementTree import iterparse

from pydantic import BaseModel, Field

from .lifestyle import ObservationCreate


APPLE_TYPES = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierDietaryWater": "water_ml",
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep_minutes",
    "HKQuantityTypeIdentifierBodyMass": "weight_kg",
    "HKQuantityTypeIdentifierWaistCircumference": "waist_cm",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
}


class AppleHealthImportSummary(BaseModel):
    source_file: str
    processed_records: int
    accepted: int
    skipped: int
    date_from: str | None = None
    date_to: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class AppleHealthImportJob(BaseModel):
    id: str
    status: str
    processed_records: int = 0
    summary: AppleHealthImportSummary | None = None
    error: str | None = None


@dataclass
class ParsedAppleHealth:
    observations: list[tuple[str, ObservationCreate]]
    processed_records: int
    date_from: str | None
    date_to: str | None


def _date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def _number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _water_ml(value: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"l", "liter", "litre"}:
        return value * 1000
    if normalized in {"fl_oz_us", "floz", "oz"}:
        return value * 29.5735
    return value


def _body_value(value: float, kind: str, unit: str) -> float:
    normalized = unit.strip().lower()
    if kind == "weight_kg" and normalized in {"lb", "lbs"}:
        return value * 0.45359237
    if kind == "waist_cm" and normalized in {"in", "inch", "inches"}:
        return value * 2.54
    return value


def parse_apple_health_xml(
    path: Path,
    *,
    progress: Callable[[int], None] | None = None,
) -> ParsedAppleHealth:
    source_totals: dict[tuple[str, str, str], float] = defaultdict(float)
    sleep_totals: dict[tuple[str, str, str, str], float] = defaultdict(float)
    daily_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    daily_latest: dict[tuple[str, str], tuple[datetime, float]] = {}
    processed = 0
    earliest: str | None = None
    latest: str | None = None

    for _, element in iterparse(path, events=("end",)):
        if element.tag != "Record":
            element.clear()
            continue
        processed += 1
        if progress and processed % 10_000 == 0:
            progress(processed)
        attrs = element.attrib
        apple_type = attrs.get("type", "")
        kind = APPLE_TYPES.get(apple_type)
        if kind is None:
            element.clear()
            continue
        try:
            started = _date(attrs["startDate"])
            ended = _date(attrs["endDate"])
        except (KeyError, ValueError):
            element.clear()
            continue
        day = started.date().isoformat()
        earliest = day if earliest is None or day < earliest else earliest
        latest = day if latest is None or day > latest else latest
        source = attrs.get("sourceName", "未知来源")

        if kind == "sleep_minutes":
            value_name = attrs.get("value", "")
            if value_name.endswith("Awake") or value_name.endswith("InBed"):
                element.clear()
                continue
            if "Asleep" not in value_name:
                element.clear()
                continue
            minutes = max(0.0, (ended - started).total_seconds() / 60)
            stage = "generic" if value_name.endswith("Asleep") else "staged"
            sleep_totals[(kind, day, source, stage)] += minutes
            element.clear()
            continue

        value = _number(attrs.get("value", ""))
        if value is None or value < 0:
            element.clear()
            continue
        unit = attrs.get("unit", "")
        if kind == "water_ml":
            source_totals[(kind, day, source)] += _water_ml(value, unit)
        elif kind == "steps":
            source_totals[(kind, day, source)] += value
        elif kind == "resting_heart_rate":
            daily_values[(kind, day)].append(value)
        else:
            converted = _body_value(value, kind, unit)
            key = (kind, day)
            previous = daily_latest.get(key)
            if previous is None or started >= previous[0]:
                daily_latest[key] = (started, converted)
        element.clear()

    aggregated: dict[tuple[str, str], float] = {}
    by_kind_day: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (kind, day, _source), total in source_totals.items():
        by_kind_day[(kind, day)].append(total)
    for key, totals in by_kind_day.items():
        aggregated[key] = max(totals)

    sleep_sources: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for (kind, day, source, stage), total in sleep_totals.items():
        sleep_sources[(kind, day, source)][stage] = total
    sleep_days: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (kind, day, _source), stages in sleep_sources.items():
        sleep_days[(kind, day)].append(stages.get("staged") or stages.get("generic", 0))
    for key, totals in sleep_days.items():
        aggregated[key] = max(totals)

    for key, values in daily_values.items():
        if values:
            aggregated[key] = sum(values) / len(values)
    for key, (_, value) in daily_latest.items():
        aggregated[key] = value

    observations: list[tuple[str, ObservationCreate]] = []
    for (kind, day), value in sorted(aggregated.items(), key=lambda item: item[0][1]):
        rounded = round(value) if kind in {"steps", "sleep_minutes", "water_ml"} else round(value, 2)
        observed_at = datetime.fromisoformat(f"{day}T12:00:00+00:00")
        external_id = f"apple-export:{kind}:{day}"
        observations.append((external_id, ObservationCreate(
            kind=kind, value=rounded, source="device", observed_at=observed_at,
            connector_id="apple_healthkit", external_id=external_id,
        )))

    if progress:
        progress(processed)
    return ParsedAppleHealth(observations, processed, earliest, latest)
