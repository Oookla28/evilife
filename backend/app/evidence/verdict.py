"""Deterministic claim-level Verdict computation.

The Verdict is the product-level centerpiece: it turns "是非题" from a chat
answer generator into a Claim Verification Engine. It is computed entirely
from the bidirectional evidence groups, the evidence gate, and the
grounding result -- a model never decides the verdict by itself.

Decision table (in order):

1. gate refused               -> insufficient (0.25)
2. no supporting evidence     -> insufficient (0.30)
3. no opposing evidence       -> true if strength high/medium
                                 partly_true if strength low
                                 insufficient if strength insufficient
4. both sides present         -> insufficient if strength insufficient
                                 partly_true if conflict_detected
                                 true if support_ratio >= 0.65 (high/medium)
                                 partly_true if 0.40 <= ratio < 0.65 or low
                                 false if ratio < 0.40
"""

from __future__ import annotations

from datetime import date

from .admission import (
    extract_concepts,
    is_absolute_claim,
    is_comparison_claim,
    is_universal_claim,
)
from ..schemas import (
    EvidenceStrength,
    GateStatus,
    Verdict,
    VerdictEvidenceItem,
    VerdictValue,
)

_GRADE_MAP: dict[EvidenceStrength, str] = {
    "high": "high",
    "medium": "moderate",
    "low": "low",
    "insufficient": "insufficient",
}

_BASE_CONFIDENCE: dict[EvidenceStrength, float] = {
    "high": 0.90,
    "medium": 0.78,
    "low": 0.68,
    "insufficient": 0.35,
}

_REASON_MAP: dict[VerdictValue, str] = {
    "true": (
        "支持证据充分且方向一致，未发现足以推翻结论的反对证据。"
    ),
    "partly_true": (
        "存在支持证据，但同样存在边界、冲突或局限证据，只能部分成立。"
    ),
    "false": (
        "反对或边界证据明显多于支持证据，该主张目前不成立。"
    ),
    "insufficient": (
        "当前语料与实时检索不足以支撑可靠判定，保持证据不足。"
    ),
}

_WHAT_COULD_CHANGE: list[str] = [
    "更长随访周期的高质量随机试验结果",
    "针对特定人群（年龄、疾病状态、用药情况）的亚组数据",
    "权威指南或系统综述的更新版本",
    "更大样本、更低偏倚风险的荟萃分析",
]


def _detail(
    *,
    verdict: VerdictValue,
    conflict_detected: bool,
    ratio: float,
    gate_status: GateStatus,
    universal_boundary: bool = False,
    broad_context: bool = False,
) -> str:
    """Map the coarse 4-value verdict to the six-value Engine 2.0 semantic.

    partly_true is refined by the support ratio and conflict signal:
      high ratio, no conflict      -> MOSTLY_SUPPORTED
      conflict detected            -> MIXED_EVIDENCE
      low ratio / population nuance -> CONTEXT_DEPENDENT
    """
    if gate_status == "refused" or verdict == "insufficient":
        return "INSUFFICIENT_EVIDENCE"
    if broad_context:
        return "CONTEXT_DEPENDENT"
    if verdict == "true":
        return "SUPPORTED"
    if verdict == "false":
        return "NOT_SUPPORTED"
    if conflict_detected:
        return "MIXED_EVIDENCE"
    if universal_boundary:
        return "CONTEXT_DEPENDENT"
    if ratio >= 0.6:
        return "MOSTLY_SUPPORTED"
    return "CONTEXT_DEPENDENT"


def build_verdict(
    *,
    claim: str,
    supporting: list[VerdictEvidenceItem],
    opposing: list[VerdictEvidenceItem],
    evidence_strength: EvidenceStrength,
    gate_status: GateStatus,
    conflict_detected: bool,
    applies_to: list[str],
    does_not_apply_to: list[str],
    limitations: list[str],
    today: date | None = None,
) -> Verdict:
    """Compute the claim-level verdict from deterministic evidence signals."""
    support_count = sum(
        item.direction in {"support", "mixed"} for item in supporting
    )
    oppose_count = sum(
        item.direction in {"against", "mixed"} for item in opposing
    )
    boundary_count = len(opposing) - oppose_count
    concepts = extract_concepts(claim)
    broad_claim = (
        bool(concepts["subject"])
        and not concepts["outcome"]
        and not is_absolute_claim(claim)
        and not is_comparison_claim(claim)
    )
    causal_observational_claim = "导致" in claim and not any(
        "随机" in (item.source_type or "")
        or "randomized" in (item.source_type or "").lower()
        for item in [*supporting, *opposing]
    )
    strength = evidence_strength
    base = _BASE_CONFIDENCE.get(strength, 0.5)

    if gate_status == "refused":
        verdict: VerdictValue = "insufficient"
        confidence = 0.25
    elif support_count == 0:
        if oppose_count > 0 and strength != "insufficient":
            verdict = "false"
            confidence = base
        else:
            verdict = "insufficient"
            confidence = 0.30
    elif oppose_count == 0:
        if broad_claim:
            verdict = "partly_true"
            confidence = round(base * 0.72, 2)
        elif boundary_count > 0 and is_universal_claim(claim):
            verdict = "partly_true"
            confidence = round(base * 0.78, 2)
        elif strength in {"high", "medium"}:
            verdict = "true"
            confidence = base
        elif strength == "low":
            verdict = "partly_true"
            confidence = base
        else:
            verdict = "insufficient"
            confidence = 0.40
    else:
        ratio = support_count / (support_count + oppose_count)
        if strength == "insufficient":
            verdict = "insufficient"
            confidence = 0.40
        elif conflict_detected:
            verdict = "partly_true"
            confidence = round(base * (0.55 + 0.45 * ratio), 2)
        elif ratio >= 0.65 and strength in {"high", "medium"}:
            verdict = "true"
            confidence = round(base * (0.55 + 0.45 * ratio), 2)
        elif ratio >= 0.40:
            verdict = "partly_true"
            confidence = round(base * (0.55 + 0.45 * ratio), 2)
        else:
            verdict = "false"
            confidence = round(base * (0.55 + 0.45 * ratio), 2)

    uncertainty = list(limitations)
    if oppose_count > 0:
        uncertainty.append(
            "存在直接反对证据，结论强度已相应下调，请结合具体人群判断。"
        )
    elif boundary_count > 0:
        uncertainty.append(
            "存在适用范围或外推边界；这些限制不等同于反证。"
        )
    uncertainty.append(
        "研究证据会随时间更新，本判定仅反映当前语料与检索时点。"
    )

    ratio = (
        support_count / (support_count + oppose_count)
        if support_count + oppose_count > 0
        else 0.5
    )
    verdict_detail = _detail(
        verdict=verdict,
        conflict_detected=conflict_detected,
        ratio=ratio,
        gate_status=gate_status,
        universal_boundary=(
            boundary_count > 0 and is_universal_claim(claim)
        ),
        broad_context=broad_claim or causal_observational_claim,
    )

    return Verdict(
        verdict=verdict,
        confidence=round(min(max(confidence, 0.0), 0.98), 2),
        evidence_grade=_GRADE_MAP.get(strength, "insufficient"),  # type: ignore[arg-type]
        claim=claim,
        short_reason=_REASON_MAP[verdict],
        applies_to=list(applies_to),
        does_not_apply_to=list(does_not_apply_to),
        supporting_evidence=list(supporting),
        opposing_evidence=list(opposing),
        uncertainty=uncertainty,
        last_updated=(today or date.today()).isoformat(),
        verdict_detail=verdict_detail,
        what_could_change_this_verdict=_WHAT_COULD_CHANGE,
    )
