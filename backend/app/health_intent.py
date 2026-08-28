"""Conservative extraction of explicit, first-person health observations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .lifestyle import ObservationKind


@dataclass(frozen=True, slots=True)
class ObservationDraft:
    kind: ObservationKind
    value: float
    source_text: str


PERSONAL_CUE = re.compile(r"我|本人|今天|今日|刚刚|刚才|昨晚|昨夜|今早|记录|记一下|帮我记|添加")
QUESTION_CUE = re.compile(r"[？?]|吗\b|是否|能不能|为什么|怎么|怎样|多少合适|正常吗")


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def extract_observation_drafts(text: str | None) -> list[ObservationDraft]:
    if not text or not text.strip():
        return []
    normalized = text.strip()
    if QUESTION_CUE.search(normalized) and not PERSONAL_CUE.search(normalized):
        return []

    drafts: dict[ObservationKind, ObservationDraft] = {}

    def add(kind: ObservationKind, value: float, source: str) -> None:
        if value >= 0:
            drafts[kind] = ObservationDraft(kind, round(value, 2), source.strip())

    water = re.search(r"(?:喝水|饮水)(?:量)?(?:是|约|大概|了|为|[:：])?\s*(\d[\d,]*(?:\.\d+)?)\s*(ml|毫升|l|升)\b", normalized, re.I)
    if water:
        value = _number(water.group(1))
        if water.group(2).lower() in {"l", "升"}:
            value *= 1000
        add("water_ml", value, water.group(0))

    steps = re.search(r"(?:走了?|步数(?:是|为|[:：])?|步行(?:了)?)\s*(\d[\d,]*)\s*步", normalized)
    if not steps:
        steps = re.search(r"(\d[\d,]*)\s*步(?:路|步数)?", normalized)
    if steps:
        add("steps", _number(steps.group(1)), steps.group(0))

    sleep = re.search(r"(?:睡眠|睡了|睡觉)(?:时长)?(?:是|约|大概|为|[:：])?\s*(\d+(?:\.\d+)?)\s*(小时|分钟)(?:\s*(\d+)\s*分钟)?", normalized)
    if sleep:
        value = _number(sleep.group(1))
        minutes = value * 60 if sleep.group(2) == "小时" else value
        if sleep.group(3):
            minutes += _number(sleep.group(3))
        add("sleep_minutes", minutes, sleep.group(0))

    patterns: list[tuple[ObservationKind, str]] = [
        ("weight_kg", r"体重(?:是|约|为|[:：])?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)"),
        ("waist_cm", r"腰围(?:是|约|为|[:：])?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)"),
        ("resting_heart_rate", r"(?:静息心率|心率)(?:是|约|为|[:：])?\s*(\d+(?:\.\d+)?)\s*(?:次(?:/分|每分钟)?|bpm)?"),
        ("mood_score", r"(?:心情|情绪)(?:是|约|为|[:：])?\s*([1-5](?:\.0)?)\s*(?:分|/\s*5)?"),
    ]
    for kind, pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if match:
            add(kind, _number(match.group(1)), match.group(0))
    return list(drafts.values())


def is_pure_record_intent(text: str | None, drafts: list[ObservationDraft]) -> bool:
    return bool(drafts) and not QUESTION_CUE.search(text or "")
