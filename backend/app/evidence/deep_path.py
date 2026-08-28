from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from ..schemas import (
    DynamicEvidencePacket,
    EvidenceAnswer,
    EvidenceCitation,
    EvidenceGroupEntry,
    EvidenceItem,
    EvidencePacket,
    EvidenceQuerySet,
    ModulePlanItem,
)
from .citation_verifier import CitedClaim, CitationReference, CitationVerifier
from .repository import EvidencePacketRepository
from .safety import EvidenceGate, SafetyAssessment
from .topic_matcher import TopicMatcher, UNKNOWN_TOPIC


@dataclass(frozen=True, slots=True)
class DeepPathResult:
    topic: str
    packet: EvidencePacket
    dynamic_packet: DynamicEvidencePacket
    answer: EvidenceAnswer
    module: ModulePlanItem
    retrieve_ms: float
    verify_ms: float


class DeepPath:
    """Packet-only Deep Path with deterministic bidirectional retrieval."""

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
        safety: SafetyAssessment,
    ) -> DeepPathResult | None:
        normalized_question = (question or "").strip()
        topic = self.matcher.match(normalized_question)
        if topic == UNKNOWN_TOPIC:
            return None

        queries = self._queries(normalized_question)
        retrieve_started = perf_counter()
        packet = self.repository.get(topic)
        support_evidence = [
            self._group_entry(item, claim)
            for item in packet.evidence_items
            for claim in item.supports
        ]
        boundary_evidence = [
            self._group_entry(item, claim)
            for item in packet.evidence_items
            for claim in item.does_not_support
        ]
        retrieve_ms = round((perf_counter() - retrieve_started) * 1000, 3)

        dynamic_packet = DynamicEvidencePacket(
            packet_id=f"dynamic-{packet.packet_id}",
            source_packet_id=packet.packet_id,
            topic=packet.topic,
            question=normalized_question,
            queries=queries,
            support_evidence=support_evidence,
            boundary_evidence=boundary_evidence,
            evidence_strength=packet.evidence_strength,
            conflict_detected=packet.conflict_detected,
        )

        gate = self.gate.evaluate(packet, safety)
        conclusion = (
            f"支持证据：{support_evidence[0].claim} "
            "当前 Evidence Packet 不支持以下推断："
            f"{boundary_evidence[0].claim}"
        )
        explanation = " ".join(item.finding for item in packet.evidence_items)

        verify_started = perf_counter()
        self._verify_dynamic_packet(packet, dynamic_packet, conclusion, explanation)
        verify_ms = round((perf_counter() - verify_started) * 1000, 3)

        answer = EvidenceAnswer(
            conclusion=conclusion,
            gate_status=gate.gate_status,
            evidence_strength=packet.evidence_strength,
            explanation=explanation,
            target_population=[item.population for item in packet.evidence_items],
            non_target_population=[entry.claim for entry in boundary_evidence],
            general_advice=list(packet.safe_actions),
            limitations=[gate.reason, *self._limitations(packet)]
            if gate.gate_status == "degraded"
            else self._limitations(packet),
            citations=[self._citation_payload(item) for item in packet.evidence_items],
            packet_id=packet.packet_id,
            topic=packet.topic,
            dynamic_packet_id=dynamic_packet.packet_id,
            queries=queries,
            support_evidence=support_evidence,
            boundary_evidence=boundary_evidence,
        )
        module = ModulePlanItem(
            module_id=module_id,
            type="EvidenceAnswer",
            version="1",
            priority=1,
            status="ready",
            props=answer.model_dump(mode="json", exclude_none=True),
        )
        return DeepPathResult(
            topic=topic,
            packet=packet,
            dynamic_packet=dynamic_packet,
            answer=answer,
            module=module,
            retrieve_ms=retrieve_ms,
            verify_ms=verify_ms,
        )

    @staticmethod
    def _queries(question: str) -> EvidenceQuerySet:
        return EvidenceQuerySet(
            support_query=f"{question} 支持证据 适用人群",
            boundary_query=f"{question} 反向证据 局限 不适用人群",
        )

    @staticmethod
    def _group_entry(item: EvidenceItem, claim: str) -> EvidenceGroupEntry:
        return EvidenceGroupEntry(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            claim=claim,
            url=item.url,
        )

    @classmethod
    def _verify_dynamic_packet(
        cls,
        packet: EvidencePacket,
        dynamic_packet: DynamicEvidencePacket,
        conclusion: str,
        explanation: str,
    ) -> None:
        verifier = CitationVerifier(packet)
        references = {
            item.evidence_id: cls._citation_reference(item)
            for item in packet.evidence_items
        }
        all_references = list(references.values())
        for entry in [
            *dynamic_packet.support_evidence,
            *dynamic_packet.boundary_evidence,
        ]:
            verifier.verify_or_raise(
                CitedClaim(
                    text=entry.claim,
                    citations=[references[entry.evidence_id]],
                )
            )
        for text in (conclusion, explanation, *packet.safe_actions):
            verifier.verify_or_raise(
                CitedClaim(text=text, citations=all_references)
            )

    @staticmethod
    def _limitations(packet: EvidencePacket) -> list[str]:
        return [
            *(item.limitations for item in packet.evidence_items),
            *(packet.missing_evidence or []),
        ]

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
