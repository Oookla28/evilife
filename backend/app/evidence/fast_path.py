from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from ..schemas import (
    EvidenceAnswer,
    EvidenceCitation,
    EvidenceItem,
    EvidencePacket,
    ModulePlanItem,
)
from .citation_verifier import CitedClaim, CitationReference, CitationVerifier
from .repository import EvidencePacketRepository
from .safety import EvidenceGate, SafetyAssessment
from .topic_matcher import TopicMatcher, UNKNOWN_TOPIC


@dataclass(frozen=True, slots=True)
class FastPathResult:
    topic: str
    packet: EvidencePacket
    answer: EvidenceAnswer
    module: ModulePlanItem
    retrieve_ms: float
    verify_ms: float


class FastPath:
    """Packet-only, template-based evidence answer with mandatory verification."""

    def __init__(
        self,
        repository: EvidencePacketRepository,
        matcher: TopicMatcher | None = None,
        gate: EvidenceGate | None = None,
    ) -> None:
        self.repository = repository
        self.matcher = matcher or TopicMatcher()
        self.gate = gate or EvidenceGate()

    def run(
        self,
        question: str | None,
        module_id: str,
        safety: SafetyAssessment | None = None,
    ) -> FastPathResult | None:
        topic = self.matcher.match(question)
        if topic == UNKNOWN_TOPIC:
            return None

        retrieve_started = perf_counter()
        packet = self.repository.get(topic)
        retrieve_ms = round((perf_counter() - retrieve_started) * 1000, 3)
        gate = self.gate.evaluate(
            packet,
            safety
            or SafetyAssessment(
                gate_status="normal",
                risk_level="low",
                category="safe",
                reason="Fast Path direct call passed no safety boundary.",
            ),
        )
        citations = [self._citation_payload(item) for item in packet.evidence_items]
        conclusion = (
            (packet.missing_evidence or [packet.evidence_items[0].limitations])[0]
            if gate.gate_status == "degraded"
            else packet.evidence_items[0].supports[0]
        )
        explanation_parts = [item.finding for item in packet.evidence_items]
        limitations = [item.limitations for item in packet.evidence_items]
        limitations.extend(packet.missing_evidence or [])

        verify_started = perf_counter()
        self._verify_packet_claims(packet, conclusion, " ".join(explanation_parts))
        verify_ms = round((perf_counter() - verify_started) * 1000, 3)

        answer = EvidenceAnswer(
            conclusion=conclusion,
            gate_status=gate.gate_status,
            evidence_strength=packet.evidence_strength,
            explanation=" ".join(explanation_parts),
            target_population=[item.population for item in packet.evidence_items],
            non_target_population=[
                boundary
                for item in packet.evidence_items
                for boundary in item.does_not_support
            ],
            general_advice=list(packet.safe_actions),
            limitations=[gate.reason, *limitations]
            if gate.gate_status == "degraded"
            else limitations,
            citations=citations,
            packet_id=packet.packet_id,
            topic=packet.topic,
        )
        module = ModulePlanItem(
            module_id=module_id,
            type="EvidenceAnswer",
            version="1",
            priority=1,
            status="ready",
            props=answer.model_dump(mode="json", exclude_none=True),
        )
        return FastPathResult(
            topic=topic,
            packet=packet,
            answer=answer,
            module=module,
            retrieve_ms=retrieve_ms,
            verify_ms=verify_ms,
        )

    @classmethod
    def _verify_packet_claims(
        cls,
        packet: EvidencePacket,
        conclusion: str,
        explanation: str,
    ) -> None:
        verifier = CitationVerifier(packet)
        all_references = [
            cls._citation_reference(item) for item in packet.evidence_items
        ]

        for item in packet.evidence_items:
            reference = cls._citation_reference(item)
            for text in (item.finding, *item.supports):
                verifier.verify_or_raise(
                    CitedClaim(text=text, citations=[reference])
                )

        for advice in packet.safe_actions:
            verifier.verify_or_raise(
                CitedClaim(text=advice, citations=all_references)
            )

        verifier.verify_or_raise(
            CitedClaim(text=conclusion, citations=all_references)
        )
        verifier.verify_or_raise(
            CitedClaim(text=explanation, citations=all_references)
        )

    @staticmethod
    def _citation_reference(item: EvidenceItem) -> CitationReference:
        return CitationReference(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            url=item.url,
        )

    @staticmethod
    def _citation_payload(item: EvidenceItem) -> EvidenceCitation:
        return EvidenceCitation(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            title=item.title,
            year=item.year,
            source_type=item.source_type,
            organization=item.organization,
            url=item.url,
        )
