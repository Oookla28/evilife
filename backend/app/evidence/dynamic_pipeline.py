"""DynamicEvidencePipeline: claim -> FOR/AGAINST retrieval -> dedup -> rank
-> EvidenceNotes.

New Engine 2.0 path, deliberately standalone: the existing orchestrator
blend path stays untouched as the fallback until Phase 4/5 wiring.

The pipeline runs a bounded number of real searches (spec §10):
- FOR side:     primary query (support direction)
- AGAINST side: contradiction query (against direction)
Each query goes to the configured EvidenceProvider; the authoritative corpus
adds reviewed claims as a curated channel. Results are deduplicated by
stable key, ranked by EvidenceRanker, and converted into EvidenceNotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..claims.models import HealthClaim
from ..tools.base import (
    EvidenceProvider,
    SearchFilters,
    ToolError,
)
from .corpus import AuthoritativeCorpus
from .dedup import deduplicate
from .evidence_note import EvidenceNote, build_evidence_note
from .query_generator import QueryGenerator, QuerySet
from .ranker import EvidenceRanker, RankedEvidence
from .admission import assess_evidence, boundary_direction
from ..tools.base import utc_now

MAX_PROVIDER_CALLS_PER_CLAIM = 2
"""Bounded: one FOR search + one AGAINST search per claim (spec §10/§23)."""


@dataclass(slots=True)
class DynamicResult:
    claim: HealthClaim
    queries: QuerySet
    notes: list[EvidenceNote]
    supporting_notes: list[EvidenceNote]
    opposing_notes: list[EvidenceNote]
    provider: str | None
    tool_calls: int = 0
    provider_error: str | None = None
    trace: list[str] = field(default_factory=list)


class DynamicEvidencePipeline:
    """Standalone dynamic retrieval pipeline (Engine 2.0)."""

    def __init__(
        self,
        provider: EvidenceProvider | None = None,
        corpus: AuthoritativeCorpus | None = None,
        *,
        query_generator: QueryGenerator | None = None,
        ranker: EvidenceRanker | None = None,
    ) -> None:
        self.provider = provider
        self.corpus = corpus or AuthoritativeCorpus.from_env()
        self.query_generator = query_generator or QueryGenerator()
        self.ranker = ranker or EvidenceRanker()

    async def run(self, claim: HealthClaim) -> DynamicResult:
        queries = self.query_generator.generate(claim)
        trace: list[str] = [f"claim {claim.claim_id}: {claim.claim}"]

        # ---- 1. select bounded queries: FOR primary + AGAINST contradiction
        for_query = next(
            (q for q in queries.queries if q.role == "synonym" and q.language == "en"),
            next(
                (q for q in queries.queries if q.role == "primary" and q.direction != "against"),
                queries.queries[0],
            ),
        )
        against_query = next(
            (q for q in queries.queries if q.role == "contradiction"),
            None,
        )

        sources: list[EvidenceNote] = []
        tool_calls = 0
        provider_error: str | None = None

        # ---- 2. provider FOR search
        if self.provider is not None and tool_calls < MAX_PROVIDER_CALLS_PER_CLAIM:
            try:
                hits = await self.provider.search(
                    for_query.query,
                    direction="support",  # type: ignore[arg-type]
                    filters=SearchFilters(max_results=6),
                )
                tool_calls += 1
                trace.append(f"provider FOR: {len(hits)} hits")
                admitted = 0
                for hit in hits:
                    decision = assess_evidence(
                        claim.claim, title=hit.title, text=hit.abstract,
                        population=hit.population,
                    )
                    note = build_evidence_note(hit)
                    if decision.relevant and note.direction in {"support", "mixed"}:
                        sources.append(note)
                        admitted += 1
                trace.append(f"provider FOR admitted: {admitted}/{len(hits)}")
            except ToolError as error:
                provider_error = error.code
                trace.append(f"provider FOR failed: {error.code}")

        # ---- 3. provider AGAINST search
        if (
            against_query is not None
            and self.provider is not None
            and tool_calls < MAX_PROVIDER_CALLS_PER_CLAIM
        ):
            try:
                hits = await self.provider.search(
                    against_query.query,
                    direction="against",  # type: ignore[arg-type]
                    filters=SearchFilters(max_results=6),
                )
                tool_calls += 1
                trace.append(f"provider AGAINST: {len(hits)} hits")
                admitted = 0
                for hit in hits:
                    decision = assess_evidence(
                        claim.claim, title=hit.title, text=hit.abstract,
                        population=hit.population,
                    )
                    note = build_evidence_note(hit)
                    if decision.relevant and note.direction in {"against", "mixed"}:
                        sources.append(note)
                        admitted += 1
                trace.append(f"provider AGAINST admitted: {admitted}/{len(hits)}")
            except ToolError as error:
                provider_error = provider_error or error.code
                trace.append(f"provider AGAINST failed: {error.code}")

        # ---- 4. corpus curated channel
        if self.corpus is not None:
            corpus_hits = self.corpus.search(
                claim.claim,
                claims_limit=4,
                literature_limit=2,
            )
            for hit in corpus_hits:
                decision = assess_evidence(
                    claim.claim, title=hit.title, text=hit.finding
                )
                if not decision.relevant:
                    continue
                direction = hit.direction
                if direction == "context":
                    direction = boundary_direction(claim.claim, hit.finding, hit.title)
                sources.append(
                    EvidenceNote(
                        evidence_id=f"N-{hit.evidence_id}",
                        source_id=hit.source_id,
                        title=hit.title,
                        year=hit.year,
                        study_type=hit.source_type,
                        population=None,
                        finding=hit.finding,
                        supports=[hit.finding] if hit.direction == "support" else [],
                        does_not_support=[hit.finding]
                        if hit.direction == "against"
                        else [],
                        limitations=["语料库人工审核摘要，需回原文核对细节"],
                        source_excerpt=hit.finding,
                        url=hit.url,
                        retrieved_at=utc_now(),
                        direction=direction,  # type: ignore[arg-type]
                    )
                )
            if corpus_hits:
                trace.append(f"corpus: {len(corpus_hits)} curated hits")

        # ---- 5. dedup
        unique = deduplicate(sources)
        trace.append(f"dedup: {len(sources)} -> {len(unique)}")

        # ---- 6. rank (map notes back to their source for the ranker)
        ranked: list[EvidenceNote] = []
        if unique:
            ranked_sources = [
                self._note_to_source(note) for note in unique
            ]
            en_terms = [
                q.query for q in queries.queries if q.language == "en"
            ]
            ranked_items = self.ranker.rank(
                ranked_sources,
                claim,
                en_terms=en_terms,
            )
            by_source_id = {note.source_id: note for note in unique}
            ranked = [
                by_source_id[item.source.source_id]
                for item in ranked_items
                if item.source.source_id in by_source_id
            ]
            trace.append(f"ranked: top {len(ranked)}")

        # ---- 7. split FOR / AGAINST
        supporting_notes = [n for n in ranked if n.direction in {"support", "mixed"}]
        opposing_notes = [n for n in ranked if n.direction in {"against", "mixed"}]

        return DynamicResult(
            claim=claim,
            queries=queries,
            notes=ranked,
            supporting_notes=supporting_notes,
            opposing_notes=opposing_notes,
            provider=self.provider.name if self.provider else None,
            tool_calls=tool_calls,
            provider_error=provider_error,
            trace=trace,
        )

    @staticmethod
    def _note_to_source(note: EvidenceNote):
        from ..tools.base import EvidenceSource

        return EvidenceSource(
            source_id=note.source_id,
            source_database="dynamic",
            title=note.title,
            year=note.year,
            source_type=note.study_type,
            journal_or_organization=None,
            url=note.url,
            abstract=note.source_excerpt,
            population=note.population,
        )
