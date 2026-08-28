from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, model_validator


ModuleStatus = Literal["loading", "ready", "error", "skipped", "pending"]
GateStatus = Literal["normal", "degraded", "refused"]
RunStatus = Literal["queued", "running", "completed", "failed"]
EvaluationMode = Literal["general", "rag", "always_deep", "eviroute_gate"]
RouteName = Literal[
    "general",
    "rag",
    "fast_path",
    "deep_path",
    "safety_refusal",
    "injection_refusal",
    "mock",
]
EvidenceDirection = Literal["support", "mixed", "insufficient", "against"]
EvidenceStrength = Literal["high", "medium", "low", "insufficient"]
VerdictValue = Literal["true", "partly_true", "false", "insufficient"]
EvidenceGrade = Literal["high", "moderate", "low", "insufficient"]
# Engine 2.0 semantic verdict (spec §19): six values with applicability nuance.
VerdictValue2 = Literal[
    "SUPPORTED",
    "MOSTLY_SUPPORTED",
    "CONTEXT_DEPENDENT",
    "MIXED_EVIDENCE",
    "NOT_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
]
StreamEventType = Literal[
    "run.started",
    "route.selected",
    "evidence.snapshot",
    "answer.delta",
    "module.ready",
    "gate.completed",
    "action.required",
    "run.completed",
    "run.failed",
    "heartbeat",
]


class StrictSchemaModel(BaseModel):
    """Base model matching contracts that disallow additional properties."""

    model_config = ConfigDict(extra="forbid")


class EvidenceItem(StrictSchemaModel):
    """One traceable source inside an Evidence Packet."""

    evidence_id: str = Field(min_length=1, pattern=r"^E[1-9]\d*$")
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int | None = None
    source_type: str = Field(min_length=1)
    organization: str | None = None
    population: str = Field(min_length=1)
    intervention: str | None = None
    outcome: str | None = None
    direction: str | None = None
    finding: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    supports: list[str]
    does_not_support: list[str]
    url: AnyUrl


class EvidencePacket(StrictSchemaModel):
    """Precompiled, bounded evidence used to ground generated claims."""

    packet_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    question: str | None = None
    overall_direction: EvidenceDirection
    evidence_strength: EvidenceStrength
    conflict_detected: bool
    evidence_items: list[EvidenceItem]
    safe_actions: list[str]
    unsafe_actions: list[str]
    missing_evidence: list[str] | None = None
    evidence_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_ids_are_unique_and_contiguous(self) -> "EvidencePacket":
        actual = [item.evidence_id for item in self.evidence_items]
        expected = [f"E{index}" for index in range(1, len(actual) + 1)]
        if actual != expected:
            raise ValueError(f"evidence_id values must be ordered and contiguous: {expected}")
        return self


class EvidenceCitation(StrictSchemaModel):
    """Traceable citation exposed by an EvidenceAnswer module."""

    evidence_id: str = Field(min_length=1, pattern=r"^E[1-9]\d*$")
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int | None = None
    source_type: str = Field(min_length=1)
    organization: str | None = None
    url: AnyUrl
    reliability_score: float | None = Field(default=None, ge=0, le=1)
    channel: Literal["curated_database", "live_medical_search"] | None = None


class VerdictEvidenceItem(StrictSchemaModel):
    """One directional evidence item used inside a claim-level Verdict.

    Unlike EvidenceGroupEntry, this contract deliberately allows curated
    (E1-En / C-xxx) and live-retrieved (W1-Wn) identifiers so that FOR and
    AGAINST evidence from independent channels can coexist in one verdict.
    """

    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int | None = None
    source_type: str = Field(min_length=1)
    organization: str | None = None
    direction: Literal["support", "against", "mixed", "context"]
    finding: str = Field(min_length=1)
    url: str
    channel: Literal["curated_database", "live_medical_search"] | None = None
    reliability_score: float | None = Field(default=None, ge=0, le=1)


class Verdict(StrictSchemaModel):
    """Claim-level final verdict: 是 / 部分正确 / 否 / 证据不足.

    This is the product-level centerpiece that turns the pipeline into a
    Claim Verification Engine instead of a chat answer generator. It is
    computed from the bidirectional evidence groups, the evidence gate and
    citation grounding, never hallucinated by a model.
    """

    verdict: VerdictValue
    confidence: float = Field(ge=0, le=1)
    evidence_grade: EvidenceGrade
    claim: str = Field(min_length=1)
    short_reason: str = Field(min_length=1)
    applies_to: list[str]
    does_not_apply_to: list[str]
    supporting_evidence: list[VerdictEvidenceItem]
    opposing_evidence: list[VerdictEvidenceItem]
    uncertainty: list[str]
    last_updated: str = Field(min_length=1)
    # Engine 2.0 extensions (optional until Phase 5 fills them in).
    verdict_detail: VerdictValue2 | None = None
    what_could_change_this_verdict: list[str] = Field(default_factory=list)

    verdict: VerdictValue
    confidence: float = Field(ge=0, le=1)
    evidence_grade: EvidenceGrade
    claim: str = Field(min_length=1)
    short_reason: str = Field(min_length=1)
    applies_to: list[str]
    does_not_apply_to: list[str]
    supporting_evidence: list[VerdictEvidenceItem]
    opposing_evidence: list[VerdictEvidenceItem]
    uncertainty: list[str]
    last_updated: str = Field(min_length=1)


class EvidenceQuerySet(StrictSchemaModel):
    """Deterministic support and boundary queries used by Deep Path."""

    support_query: str = Field(min_length=1)
    boundary_query: str = Field(min_length=1)


class EvidenceGroupEntry(StrictSchemaModel):
    """One packet-bounded result in a dynamic evidence group."""

    evidence_id: str = Field(min_length=1, pattern=r"^E[1-9]\d*$")
    source_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    url: AnyUrl


class DynamicEvidencePacket(StrictSchemaModel):
    """Deep Path view that keeps support and boundary evidence separate."""

    packet_id: str = Field(min_length=1)
    source_packet_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    question: str = Field(min_length=1)
    queries: EvidenceQuerySet
    support_evidence: list[EvidenceGroupEntry] = Field(min_length=1)
    boundary_evidence: list[EvidenceGroupEntry] = Field(min_length=1)
    evidence_strength: EvidenceStrength
    conflict_detected: bool
    live_support_evidence: list[VerdictEvidenceItem] | None = None
    live_boundary_evidence: list[VerdictEvidenceItem] | None = None


class EvidenceAnswer(StrictSchemaModel):
    """Typed props contract for normal, degraded, and refused answers."""

    conclusion: str = Field(min_length=1)
    gate_status: GateStatus
    evidence_strength: EvidenceStrength
    explanation: str = Field(min_length=1)
    target_population: list[str]
    non_target_population: list[str]
    general_advice: list[str]
    limitations: list[str]
    citations: list[EvidenceCitation]
    packet_id: str | None = None
    topic: str | None = None
    dynamic_packet_id: str | None = None
    queries: EvidenceQuerySet | None = None
    support_evidence: list[EvidenceGroupEntry] | None = None
    boundary_evidence: list[EvidenceGroupEntry] | None = None
    source: str | None = None
    model: str | None = None
    scope_reason: str | None = None
    evidence_mix: dict[str, Any] | None = None
    grounding: dict[str, Any] | None = None
    verdict: Verdict | None = None
    tcm_perspective: dict[str, Any] | None = None
    status: Literal["ready"] = "ready"
    # Engine 2.0 observability: decomposed claims + evidence-chain trace.
    claims: list[dict[str, Any]] | None = None
    trace_steps: list[dict[str, Any]] | None = None
    # Phase 3 dynamic evidence: EvidenceNotes from the dynamic pipeline.
    dynamic_notes: list[dict[str, Any]] | None = None


class ModulePlanItem(BaseModel):
    module_id: str
    type: str
    version: str | None = None
    priority: float | None = None
    status: ModuleStatus
    props: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    action_id: str
    type: str
    label: str
    requires_confirmation: bool
    status: Literal["pending", "completed", "failed", "cancelled"] = "pending"
    payload_preview: dict[str, Any] | None = None


class OrchestrateResponse(BaseModel):
    request_id: str
    session_id: str
    run_id: str
    intent: str | None = None
    risk_level: str | None = None
    gate_status: GateStatus
    status: RunStatus
    module_plan: list[ModulePlanItem]
    actions: list[Action] = Field(default_factory=list)
    mode: EvaluationMode | None = None
    route: RouteName | None = None
    evidence_count: int = Field(default=0, ge=0)
    support_evidence_count: int = Field(default=0, ge=0)
    boundary_evidence_count: int = Field(default=0, ge=0)
    timing_ms: dict[str, float] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    event_id: str
    request_id: str
    run_id: str
    type: StreamEventType
    timestamp: datetime
    payload: dict[str, Any] | None = None
