from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import EvaluationMode, RouteName
from .safety import SafetyAssessment


@dataclass(frozen=True, slots=True)
class ModeSelection:
    mode: EvaluationMode
    route: RouteName


class EvaluationModeRouter:
    """Normalize legacy modes and choose one deterministic evaluation route."""

    _COMPLEX = re.compile(
        r"比较|相比|对比|区别|哪个更|哪种更|优于|因果|导致|引起|"
        r"造成|是否因为|为什么会|冲突|矛盾|相反|反向|边界"
    )

    _ALIASES: dict[str, EvaluationMode] = {
        "auto": "eviroute_gate",
        "fast": "eviroute_gate",
        "deep": "always_deep",
        "evaluation": "eviroute_gate",
    }

    def select(
        self,
        requested_mode: str,
        question: str | None,
        safety: SafetyAssessment,
    ) -> ModeSelection:
        mode = self._ALIASES.get(requested_mode, requested_mode)
        if mode not in {"general", "rag", "always_deep", "eviroute_gate"}:
            raise ValueError(f"Unsupported evaluation mode: {requested_mode}")

        if requested_mode == "fast":
            return ModeSelection(mode="eviroute_gate", route="fast_path")
        if mode == "general":
            return ModeSelection(mode="general", route="general")
        if mode == "rag":
            return ModeSelection(mode="rag", route="rag")
        if mode == "always_deep":
            return ModeSelection(mode="always_deep", route="deep_path")

        is_boundary = safety.category in {
            "population_boundary",
            "evidence_boundary",
        }
        is_complex = bool(self._COMPLEX.search((question or "").strip()))
        return ModeSelection(
            mode="eviroute_gate",
            route="deep_path" if is_boundary or is_complex else "fast_path",
        )
