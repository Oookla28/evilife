"""EvidenceRanker: score and order retrieved evidence.

Combines, for each candidate source:

- publication quality (source type hierarchy, question-type aware)
- relevance (claim keyword coverage in title/abstract)
- recency (year decay against the current date)
- population match (claim population words vs source population)
- directness (study design vs claim type)

Newer is not always better and RCTs do not dominate every question type:
risk/causal claims weight observational/cohort evidence higher than pure RCTs.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ..claims.models import HealthClaim
from ..tools.base import EvidenceSource

# Baseline quality by source type (0..1).
_QUALITY: dict[str, float] = {
    "guideline": 1.00,
    "meta_analysis": 0.96,
    "systematic_review": 0.93,
    "rct": 0.90,
    "cohort": 0.76,
    "observational": 0.72,
    "review": 0.70,
    "other": 0.55,
}

# Question type -> source-type weight adjustments (directness).
_DIRECTNESS: dict[str, dict[str, float]] = {
    "effectiveness": {"rct": 1.0, "meta_analysis": 1.0, "systematic_review": 0.95, "guideline": 0.9, "cohort": 0.6, "observational": 0.55, "review": 0.6, "other": 0.4},
    "causal": {"cohort": 0.9, "observational": 0.85, "meta_analysis": 0.85, "systematic_review": 0.85, "rct": 0.9, "guideline": 0.8, "review": 0.6, "other": 0.4},
    "risk_factor": {"cohort": 0.9, "observational": 0.85, "meta_analysis": 0.85, "systematic_review": 0.85, "rct": 0.8, "guideline": 0.8, "review": 0.6, "other": 0.4},
    "metabolic": {"rct": 0.95, "meta_analysis": 0.95, "systematic_review": 0.9, "guideline": 0.9, "cohort": 0.6, "observational": 0.6, "review": 0.6, "other": 0.4},
    "safety_or_body_composition": {"rct": 0.9, "meta_analysis": 0.9, "systematic_review": 0.9, "guideline": 0.85, "cohort": 0.7, "observational": 0.7, "review": 0.6, "other": 0.4},
    "longevity": {"cohort": 0.85, "observational": 0.8, "meta_analysis": 0.8, "systematic_review": 0.8, "rct": 0.7, "guideline": 0.7, "review": 0.6, "other": 0.4},
    "comparison": {"rct": 1.0, "meta_analysis": 1.0, "systematic_review": 0.95, "guideline": 0.85, "cohort": 0.6, "observational": 0.55, "review": 0.6, "other": 0.4},
    "population_claim": {"guideline": 1.0, "meta_analysis": 0.9, "systematic_review": 0.9, "rct": 0.8, "cohort": 0.6, "observational": 0.55, "review": 0.6, "other": 0.4},
    "other": {"guideline": 0.9, "meta_analysis": 0.9, "systematic_review": 0.9, "rct": 0.9, "cohort": 0.7, "observational": 0.7, "review": 0.7, "other": 0.5},
}

_POPULATION_WORDS = re.compile(
    r"孕妇|儿童|老人|老年|青少年|成人|男性|女性|肾病|透析|心衰|"
    r"糖尿病|高血压|超重|肥胖|运动员|术后|二级预防"
)

# Chinese population words -> English synonyms found in Europe PMC population/
# abstract text (cross-language matching for the population signal).
_POPULATION_EN: dict[str, tuple[str, ...]] = {
    "孕妇": ("pregnan", "maternal", "antenatal"),
    "儿童": ("child", "pediatric", "paediatric", "adolescent"),
    "老人": ("elderly", "older", "geriatric"),
    "老年": ("elderly", "older", "geriatric"),
    "青少年": ("adolescent", "teen"),
    "成人": ("adult",),
    "男性": ("male", "men"),
    "女性": ("female", "women"),
    "肾病": ("kidney", "renal", "nephro"),
    "透析": ("dialysis", "hemodialysis"),
    "心衰": ("heart failure", "cardiac failure"),
    "糖尿病": ("diabet",),
    "高血压": ("hypertension", "hypertensive", "blood pressure"),
    "超重": ("overweight",),
    "肥胖": ("obes",),
    "运动员": ("athlete",),
    "术后": ("postoperative", "post-surgical"),
    "二级预防": ("secondary prevention",),
}

_CURRENT_YEAR = date.today().year


class RankedEvidence(BaseModel):
    source: EvidenceSource
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class EvidenceRanker:
    """Deterministic multi-signal ranking for retrieved evidence."""

    def rank(
        self,
        sources: list[EvidenceSource],
        claim: HealthClaim,
        *,
        en_terms: list[str] | None = None,
        today: date | None = None,
    ) -> list[RankedEvidence]:
        ranked = [
            self._score(
                source,
                claim,
                en_terms=en_terms or [],
                today=today or date.today(),
            )
            for source in sources
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def _score(
        self,
        source: EvidenceSource,
        claim: HealthClaim,
        *,
        en_terms: list[str],
        today: date,
    ) -> RankedEvidence:
        quality = _QUALITY.get(source.source_type, 0.55)
        directness = _DIRECTNESS.get(claim.type, _DIRECTNESS["other"]).get(
            source.source_type, 0.5
        )
        relevance = self._relevance(source, claim.claim, en_terms)
        recency = self._recency(source.year, today)
        population = self._population_match(source.population, claim.claim)

        score = (
            0.30 * relevance
            + 0.25 * quality
            + 0.20 * directness
            + 0.15 * recency
            + 0.10 * population
        )
        reasons = [
            f"相关度 {relevance:.2f}",
            f"来源质量 {quality:.2f}",
            f"问题适配 {directness:.2f}",
            f"新鲜度 {recency:.2f}",
            f"人群匹配 {population:.2f}",
        ]
        return RankedEvidence(
            source=source,
            score=round(min(max(score, 0.0), 1.0), 4),
            reasons=reasons,
        )

    @staticmethod
    def _relevance(
        source: EvidenceSource, claim: str, en_terms: list[str] | None = None
    ) -> float:
        """Keyword overlap between claim (and optional en stems) and source."""
        text = f"{source.title} {source.abstract}".lower()
        tokens = [token for token in re.findall(r"[a-z]{3,}", claim.lower())]
        zh_words = re.findall(r"[\u4e00-\u9fff]{2,6}", claim)
        en_terms = [term.lower() for term in (en_terms or []) if len(term) >= 3]
        hits = 0
        for token in tokens:
            if token in text:
                hits += 1
        for term in en_terms:
            if term in text:
                hits += 1
        zh_hits = 0
        for word in zh_words:
            if word in source.title or word in source.abstract:
                zh_hits += 1
        total = len(tokens) + len(zh_words) + len(en_terms)
        if total == 0:
            return 0.5
        return min((hits + zh_hits) / total, 1.0)

    @staticmethod
    def _recency(year: int | None, today: date) -> float:
        if year is None:
            return 0.4
        age = max(0, today.year - year)
        return max(0.3, 1.0 - age * 0.03)

    @staticmethod
    def _population_match(source_population: str | None, claim: str) -> float:
        if not source_population:
            return 0.5
        claim_groups = set(_POPULATION_WORDS.findall(claim))
        if not claim_groups:
            return 0.7
        text = source_population.lower()
        matched = 0
        for group in claim_groups:
            if group in source_population:
                matched += 1
            elif any(alias in text for alias in _POPULATION_EN.get(group, ())):
                matched += 1
        return min(0.5 + 0.5 * matched / len(claim_groups), 1.0)
