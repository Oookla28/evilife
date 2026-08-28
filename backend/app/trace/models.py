"""Trace: record the system's *visible* evidence chain, not chain-of-thought.

A trace step captures what the system did (step/action/tool), what it saw
(output summary), and what it decided — never private reasoning, API keys,
secrets, PHI, or full sensitive prompts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

TraceStatus = Literal["ok", "failed", "degraded", "skipped"]


class TraceStep(BaseModel):
    step: str = Field(min_length=1, description="阶段名，如 claim.parse / pubmed.search")
    action: str = Field(min_length=1, description="动作，如 search / verify / grade")
    tool: str | None = None
    input_summary: str | None = Field(default=None, max_length=200)
    output_summary: str | None = Field(default=None, max_length=500)
    observation: str | None = Field(default=None, max_length=300)
    decision: str | None = Field(default=None, max_length=300)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    latency_ms: float | None = None
    status: TraceStatus = "ok"


class TraceRecorder:
    """Bounded, in-memory step recorder per run."""

    def __init__(self, run_id: str, *, max_steps: int = 64) -> None:
        self.run_id = run_id
        self._steps: list[TraceStep] = []
        self._max_steps = max_steps

    def add(
        self,
        *,
        step: str,
        action: str,
        tool: str | None = None,
        input_summary: str | None = None,
        output_summary: str | None = None,
        observation: str | None = None,
        decision: str | None = None,
        latency_ms: float | None = None,
        status: TraceStatus = "ok",
    ) -> TraceStep:
        record = TraceStep(
            step=step,
            action=action,
            tool=tool,
            input_summary=input_summary,
            output_summary=output_summary,
            observation=observation,
            decision=decision,
            latency_ms=latency_ms,
            status=status,
        )
        self._steps.append(record)
        if len(self._steps) > self._max_steps:
            self._steps = self._steps[-self._max_steps :]
        return record

    def snapshot(self) -> list[TraceStep]:
        return list(self._steps)

    def to_user_facing_summary(self) -> list[str]:
        """Human-readable one-liners for the UI (trace panel / printing phase)."""
        return [
            f"{step.step}: {step.output_summary}" if step.output_summary else step.step
            for step in self._steps
            if step.output_summary
        ]
