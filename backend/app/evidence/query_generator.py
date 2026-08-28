"""Query Generator: one claim -> a bounded set of retrieval queries.

Per claim we produce up to MAX_QUERY_EXPANSION queries across directions:
primary / synonym / clinical / boundary / contradiction. Expansion is
bounded by design — the engine never loops infinitely on query variants.

Chinese health topics map to English Europe PMC query stems through a small
built-in glossary; unknown topics keep the Chinese claim text as the query
(the corpus layer handles Chinese, Europe PMC handles English queries).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ..claims.models import HealthClaim

MAX_QUERY_EXPANSION = 3
"""Hard cap on how many real searches one claim may trigger (spec §10)."""

QueryRole = Literal["primary", "synonym", "clinical", "boundary", "contradiction"]


class GeneratedQuery(BaseModel):
    role: QueryRole
    query: str = Field(min_length=1)
    direction: Literal["support", "against", "neutral"] = "neutral"
    language: Literal["zh", "en"] = "zh"


class QuerySet(BaseModel):
    claim_id: str
    queries: list[GeneratedQuery] = Field(min_length=1, max_length=MAX_QUERY_EXPANSION)


# Chinese health keyword -> English Europe PMC query stem.
_ZH_EN: tuple[tuple[str, str], ...] = (
    ("限时进食", "time-restricted eating"),
    ("16:8", "time-restricted eating"),
    ("间歇性禁食", "intermittent fasting"),
    ("限钠", "sodium restriction"),
    ("限盐", "salt reduction"),
    ("低盐", "low salt"),
    ("地中海饮食", "Mediterranean diet"),
    ("低碳水", "low-carbohydrate diet"),
    ("低碳", "low-carbohydrate diet"),
    ("低脂", "low-fat diet"),
    ("维生素D", "vitamin D"),
    ("维生素D补充", "vitamin D supplementation"),
    ("咖啡", "coffee"),
    ("鸡蛋", "egg consumption"),
    ("橄榄油", "olive oil"),
    ("有氧运动", "aerobic exercise"),
    ("力量训练", "resistance training"),
    ("规律运动", "exercise"),
    ("运动", "exercise"),
    ("蔬菜水果", "fruit and vegetable intake"),
    ("果蔬", "fruit and vegetable intake"),
    ("蔬菜", "vegetable intake"),
    ("水果", "fruit intake"),
    ("睡眠", "sleep"),
    ("减重", "weight loss"),
    ("减肥", "weight loss"),
    ("血压", "blood pressure"),
    ("高血压", "hypertension"),
    ("血糖", "blood glucose"),
    ("胰岛素抵抗", "insulin resistance"),
    ("胆固醇", "cholesterol"),
    ("心血管", "cardiovascular"),
    ("二级预防", "secondary prevention"),
    ("骨骼", "bone health"),
)

# Claim-type -> direction preference for the primary query.
_TYPE_DIRECTION: dict[str, str] = {
    "effectiveness": "support",
    "causal": "support",
    "risk_factor": "support",
    "metabolic": "support",
    "longevity": "support",
    "comparison": "neutral",
    "population_claim": "against",
    "safety_or_body_composition": "neutral",
}


class QueryGenerator:
    """Deterministic, bounded query expansion for one health claim."""

    def generate(self, claim: HealthClaim) -> QuerySet:
        zh_text = re.sub(r"[吗呢？?。！!，,、]+$", "", claim.claim).strip()
        en_stem = self._zh_to_en(zh_text)

        primary = GeneratedQuery(
            role="primary",
            query=zh_text,
            direction=_TYPE_DIRECTION.get(claim.type, "support"),  # type: ignore[arg-type]
            language="zh",
        )
        queries: list[GeneratedQuery] = [primary]

        if en_stem:
            queries.append(
                GeneratedQuery(
                    role="synonym",
                    query=en_stem,
                    direction="neutral",
                    language="en",
                )
            )
        if len(queries) < MAX_QUERY_EXPANSION:
            # Boundary/contradiction query: null results + limitations.
            # The against side is a core engine signal, so it outranks the
            # clinical (evidence-type-restricted) variant when space is tight.
            queries.append(
                GeneratedQuery(
                    role="contradiction",
                    query=(
                        f'{en_stem or zh_text} AND ("no benefit" OR "no effect" OR '
                        '"no difference" OR conflicting OR "not superior")'
                    ),
                    direction="against",
                    language="en" if en_stem else "zh",
                )
            )
        if len(queries) < MAX_QUERY_EXPANSION and en_stem:
            # Clinical query: restrict to strong evidence types.
            queries.append(
                GeneratedQuery(
                    role="clinical",
                    query=(
                        f'{en_stem} AND (PUB_TYPE:"systematic review" OR '
                        'PUB_TYPE:"meta-analysis" OR PUB_TYPE:"practice guideline")'
                    ),
                    direction="support",
                    language="en",
                )
            )
        return QuerySet(claim_id=claim.claim_id, queries=queries[:MAX_QUERY_EXPANSION])

    @staticmethod
    def _zh_to_en(text: str) -> str | None:
        matches = [(zh, en) for zh, en in _ZH_EN if zh in text]
        matches.sort(key=lambda item: len(item[0]), reverse=True)
        hits: list[str] = []
        selected_zh: list[str] = []
        for zh, en in matches:
            # A longer phrase already carries the shorter nested concept:
            # “维生素D补充” must not expand again to “维生素D”, and
            # “蔬菜水果” must not become three redundant AND clauses.
            if any(zh in selected for selected in selected_zh):
                continue
            selected_zh.append(zh)
            if en not in hits:
                hits.append(en)
        if not hits:
            return None
        # Combine the central exposure/intervention and outcome. Searching only
        # “Mediterranean diet” retrieved menopause/BMI papers for a CVD claim.
        return " AND ".join(f'"{hit}"' if " " in hit else hit for hit in hits[:3])

    @classmethod
    def english_query(cls, text: str) -> str | None:
        """Public bounded translation used by the local PubMed corpus."""
        return cls._zh_to_en(text)
