"""Deterministic admission gate for candidate medical evidence.

Search rank is not evidence direction.  A paper is admitted only when its
title/abstract covers the claim's central subject and outcome.  Direction is
then inferred from a *direct* sentence instead of copied from the query that
retrieved it.  Ambiguous limitation/background text stays context-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


EvidenceSemanticDirection = Literal["support", "against", "mixed", "context"]


_CONCEPTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "sodium": ("subject", (r"限钠|限盐|低钠|低盐|少盐|钠摄入|食盐摄入", r"\bsodium\b|\bsalt\b")),
    "mediterranean": ("subject", (r"地中海(?:饮食|膳食)", r"mediterranean diet")),
    "fasting": ("subject", (r"16:8|限时进食|间歇性(?:禁食|断食)", r"time[- ]restricted eating|intermittent fasting|\btre\b")),
    "coffee": ("subject", (r"咖啡", r"\bcoffee\b|caffeine")),
    "egg": ("subject", (r"鸡蛋|蛋类", r"\begg(?:s)?\b|egg consumption")),
    "olive_oil": ("subject", (r"橄榄油", r"olive oil")),
    "low_carb": ("subject", (r"低碳水|低碳饮食", r"low[- ]carbohydrate|low[- ]carb")),
    "vitamin_d": ("subject", (r"维生素\s*[dD]", r"vitamin\s*d")),
    "exercise": ("subject", (r"运动|锻炼|有氧|力量训练", r"exercise|physical activity|aerobic|resistance training")),
    "fruit_vegetable": ("subject", (r"蔬菜|水果|果蔬", r"fruit|vegetable")),
    "medication": ("subject", (r"药物|用药|剂量|换药|停药", r"medication|medicine|drug|dosage|dose")),
    "blood_pressure": ("outcome", (r"血压|高血压", r"blood pressure|hypertension|hypertensive")),
    "cardiovascular": ("outcome", (r"心血管|心脏病|卒中|中风", r"cardiovascular|\bcvd\b|stroke|myocardial|heart disease")),
    "weight": ("outcome", (r"减重|减肥|体重|肥胖|限热量", r"weight loss|body weight|obesity|\bbmi\b|calorie restriction")),
    "sleep": ("outcome", (r"睡眠|失眠", r"sleep|insomnia")),
    "glucose": ("outcome", (r"血糖|胰岛素|糖尿病", r"glucose|insulin|diabet")),
    "lipid": ("outcome", (r"血脂|胆固醇", r"lipid|cholesterol|triglyceride")),
    "bone": ("outcome", (r"骨骼|骨密度|骨折", r"bone|fracture|osteoporosis")),
    "pregnancy": ("population", (r"孕妇|孕期|怀孕", r"pregnan|gestation")),
    "children": ("population", (r"儿童|孩子|青少年", r"child|children|adolescen|pediatric")),
    "secondary_cvd": ("population", (r"心血管二级预防|已确诊心血管", r"secondary prevention|established cardiovascular")),
    "sleep_apnea": ("population", (r"睡眠呼吸暂停", r"sleep apn(?:ea|oea)|\bosa\b")),
    "arthritis": ("population", (r"关节炎", r"arthritis")),
    "cancer": ("population", (r"癌症|肿瘤", r"cancer|carcinoma|tumou?r")),
    "psychiatric": ("population", (r"精神障碍|精神疾病", r"psychiatric disorder")),
    "menopause": ("population", (r"绝经|更年期", r"menopaus|postmenopausal")),
}

_SUPPORT = re.compile(
    r"降低|减少|改善|有益|有效|维持|风险更低|显著下降|"
    r"\b(reduced|lowered|decreased|improved|beneficial|effective|"
    r"associated with lower|lower risk|significant reduction|important for|"
    r"supports?|helps? maintain|maintains?)\b",
    re.IGNORECASE,
)
_AGAINST = re.compile(
    r"无显著(?:差异|作用|获益)|没有显著(?:差异|作用|获益)|未发现(?:额外)?获益|"
    r"没有可靠证据证明|不优于|未降低|无关联|风险升高|增加.{0,8}风险|可能不利|"
    r"\b(no benefit|no effect|no difference|not superior|not better|"
    r"no association|no significant|did not reduce|failed to|"
    r"no evidence of benefit)\b",
    re.IGNORECASE,
)
_BOUNDARY_ONLY = re.compile(
    r"不能据此|不能证明|不能推断|不能替代|不确定|证据(?:仍)?有限|"
    r"外推.{0,8}有限|"
    r"\b(uncertain|limited evidence|cannot be generalized|not generalizable|"
    r"insufficient evidence|limitation|limitations)\b",
    re.IGNORECASE,
)
_ABSOLUTE_CLAIM = re.compile(
    r"100\s*%|百分之百|一定|必然|保证|完全(?:预防|避免)|绝对"
)
_UNIVERSAL_CLAIM = re.compile(r"所有人|每个人|任何人|人人")
_COMPARISON_CLAIM = re.compile(r"比|优于|更有效|不劣于|versus|compared with", re.I)
_ACTIVE_COMPARATOR = re.compile(
    r"相比|相对|与.{0,20}(?:比较|相比)|compared with|versus|vs\.?|"
    r"calorie restriction|energy restriction|低脂饮食",
    re.I,
)


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    relevant: bool
    score: float
    direction: EvidenceSemanticDirection
    matched_subjects: tuple[str, ...]
    matched_outcomes: tuple[str, ...]
    matched_populations: tuple[str, ...]
    reason: str


def extract_concepts(text: str | None) -> dict[str, set[str]]:
    value = (text or "").lower()
    found = {"subject": set(), "outcome": set(), "population": set()}
    for name, (kind, patterns) in _CONCEPTS.items():
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
            found[kind].add(name)
    return found


def assess_evidence(
    claim: str,
    *,
    title: str,
    text: str,
    population: str | None = None,
) -> AdmissionDecision:
    requested = extract_concepts(claim)
    source_text = " ".join(part for part in (title, text, population or "") if part)
    available = extract_concepts(source_text)
    matched_subjects = requested["subject"] & available["subject"]
    matched_outcomes = requested["outcome"] & available["outcome"]
    matched_populations = requested["population"] & available["population"]

    subject_ok = not requested["subject"] or bool(matched_subjects)
    outcome_ok = not requested["outcome"] or bool(matched_outcomes)
    population_ok = (
        bool(matched_populations)
        if requested["population"]
        else not available["population"]
    )
    relevant = subject_ok and outcome_ok and population_ok and bool(
        requested["subject"] or requested["outcome"]
    )

    if not relevant:
        missing = []
        if not subject_ok:
            missing.append("核心干预/暴露不匹配")
        if not outcome_ok:
            missing.append("结局不匹配")
        if not population_ok:
            missing.append("目标人群不匹配")
        if not requested["subject"] and not requested["outcome"]:
            missing.append("主张缺少可识别医学概念")
        return AdmissionDecision(
            relevant=False,
            score=0.0,
            direction="context",
            matched_subjects=tuple(sorted(matched_subjects)),
            matched_outcomes=tuple(sorted(matched_outcomes)),
            matched_populations=tuple(sorted(matched_populations)),
            reason="；".join(missing),
        )

    sentences = _sentences(text) or [text]
    direct_sentences = [
        sentence
        for sentence in sentences
        if _sentence_is_direct(claim, title, sentence)
    ]
    direction = _direction(direct_sentences)
    score = 0.55
    if requested["subject"]:
        score += 0.20
    if requested["outcome"]:
        score += 0.20
    if direct_sentences:
        score += 0.05
    return AdmissionDecision(
        relevant=True,
        score=round(min(score, 1.0), 2),
        direction=direction,
        matched_subjects=tuple(sorted(matched_subjects)),
        matched_outcomes=tuple(sorted(matched_outcomes)),
        matched_populations=tuple(sorted(matched_populations)),
        reason=(
            "主题与结局匹配，存在直接方向句"
            if direct_sentences
            else "主题匹配，但未发现直接支持或反对句"
        ),
    )


def boundary_direction(claim: str, finding: str, title: str = "") -> EvidenceSemanticDirection:
    """Separate real null-result counterevidence from applicability caveats."""
    decision = assess_evidence(claim, title=title, text=finding)
    if not decision.relevant:
        return "context"
    calibrated = calibrate_direction(claim, finding, decision.direction)
    if calibrated == "against" or (
        is_absolute_claim(claim) and _BOUNDARY_ONLY.search(finding)
    ):
        return "against"
    return "context"


def is_absolute_claim(claim: str) -> bool:
    return bool(_ABSOLUTE_CLAIM.search(claim or ""))


def is_universal_claim(claim: str) -> bool:
    return bool(_UNIVERSAL_CLAIM.search(claim or ""))


def calibrate_direction(
    claim: str,
    text: str,
    direction: EvidenceSemanticDirection,
) -> EvidenceSemanticDirection:
    """Keep active-comparator null results from refuting simpler benefit claims."""
    if (
        direction in {"against", "mixed"}
        and _ACTIVE_COMPARATOR.search(text or "")
        and not is_comparison_claim(claim)
    ):
        return "context"
    return direction


def is_comparison_claim(claim: str) -> bool:
    return bool(_COMPARISON_CLAIM.search(claim or ""))


def _sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?。！？；;])\s*", text or "")
        if len(item.strip()) >= 12
    ]


def _sentence_is_direct(claim: str, title: str, sentence: str) -> bool:
    requested = extract_concepts(claim)
    scope = extract_concepts(f"{title} {sentence}")
    return (
        (not requested["subject"] or bool(requested["subject"] & scope["subject"]))
        and (not requested["outcome"] or bool(requested["outcome"] & scope["outcome"]))
        and (
            not requested["population"]
            or bool(requested["population"] & scope["population"])
        )
    )


def _direction(sentences: list[str]) -> EvidenceSemanticDirection:
    support = False
    against = False
    for sentence in sentences:
        # A limitation statement is not counterevidence unless it contains a
        # direct null-result marker as well.
        has_against = bool(_AGAINST.search(sentence))
        has_support = bool(_SUPPORT.search(sentence))
        if _BOUNDARY_ONLY.search(sentence) and not has_against:
            continue
        against = against or has_against
        support = support or has_support
    if support and against:
        return "mixed"
    if against:
        return "against"
    if support:
        return "support"
    return "context"
