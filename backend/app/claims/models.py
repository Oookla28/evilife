"""Health Claim domain models (Engine 2.0).

A single user sentence may contain multiple health claims. Each claim is a
testable proposition that will go through its own evidence chain:
Safety → Search → Verify → Grade → Verdict.

Claim decomposition must never change the user's meaning: `original_text`
and character spans always link a claim back to the raw input.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ClaimType = Literal[
    "effectiveness",           # X 有效 / 可以改善
    "causal",                  # X 导致 / 引起 / 增加风险
    "risk_factor",             # X 是风险因素
    "metabolic",               # 血糖 / 胰岛素 / 血脂等代谢结局
    "safety_or_body_composition",  # 副作用 / 肌肉量 / 安全性
    "longevity",               # 延缓衰老 / 寿命
    "comparison",              # A 比 B 更……
    "population_claim",        # 对某人群普遍适用 / 所有人都……
    "other",
]


class HealthClaim(BaseModel):
    """One normalized, traceable health claim extracted from user input."""

    claim_id: str = Field(min_length=1, pattern=r"^C[0-9]+$")
    claim: str = Field(min_length=1, description="归一化后的主张（可证伪命题）")
    type: ClaimType = "other"
    original_text: str = Field(min_length=1, description="原文片段，保留用户原义")
    span_start: int = Field(default=0, ge=0)
    span_end: int = Field(default=0, ge=0)
    source_intent: str | None = Field(
        default=None, description="整句原始输入，用于跨 claim 追溯"
    )

    @model_validator(mode="after")
    def span_is_valid(self) -> "HealthClaim":
        if self.span_end < self.span_start:
            raise ValueError("span_end must not precede span_start")
        if self.source_intent and self.original_text not in self.source_intent:
            # The original fragment must appear verbatim in the source input.
            raise ValueError("original_text must be a substring of source_intent")
        return self

    def to_verdict_claim(self) -> str:
        """The claim string used by verdict/gate layers."""
        return self.claim


MAX_CLAIMS = 5
"""Hard cap: never decompose a single input into more claims than this."""
