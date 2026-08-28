"""Deterministic citation-envelope verification.

Adapted from medgroundAI's MIT-licensed grounding contract (fixed upstream
commit a113b4b, Copyright 2026 Arnaud Tauveron). EviLife supplies its own
source set instead of medgroundAI's DuckDB DocStore.

This verifies provenance existence and retrieval-envelope membership. It does
not claim that a cited source semantically entails a medical conclusion.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


STATUS_UNCITED = "uncited"
STATUS_PHANTOM = "phantom_citation"
STATUS_OFF_ENVELOPE = "off_envelope"
STATUS_GROUNDED = "grounded"


def _normalize_claim(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return {"text": raw.strip(), "citations": []}
    if not isinstance(raw, Mapping):
        return {"text": str(raw).strip(), "citations": []}
    text = str(raw.get("text") or raw.get("claim") or "").strip()
    citations = raw.get("citations")
    if citations is None:
        citations = raw.get("source_ids") or raw.get("source_id") or []
    if isinstance(citations, str):
        citations = [citations]
    return {
        "text": text,
        "citations": [str(item).strip() for item in citations if str(item).strip()],
    }


def verify_claims(
    claims: Iterable[Any],
    *,
    known_source_ids: Iterable[str],
    allowed_source_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return a machine-checkable report for missing or fabricated sources."""
    known = {str(item).strip() for item in known_source_ids if str(item).strip()}
    allowed = (
        {str(item).strip() for item in allowed_source_ids if str(item).strip()}
        if allowed_source_ids is not None
        else None
    )
    normalized = [claim for claim in map(_normalize_claim, claims) if claim["text"]]
    results: list[dict[str, Any]] = []

    for claim in normalized:
        citations = claim["citations"]
        problems: list[str] = []
        if not citations:
            status = STATUS_UNCITED
            problems.append("no source_id cited")
        else:
            phantom = [source_id for source_id in citations if source_id not in known]
            off_envelope = (
                [
                    source_id
                    for source_id in citations
                    if source_id in known and source_id not in allowed
                ]
                if allowed is not None
                else []
            )
            if phantom:
                status = STATUS_PHANTOM
                problems.append(f"unknown source_id: {', '.join(phantom)}")
            elif off_envelope:
                status = STATUS_OFF_ENVELOPE
                problems.append(
                    f"source_id outside retrieved envelope: {', '.join(off_envelope)}"
                )
            else:
                status = STATUS_GROUNDED
        results.append(
            {
                "text": claim["text"],
                "citations": citations,
                "status": status,
                "problems": problems,
            }
        )

    grounded_count = sum(
        result["status"] == STATUS_GROUNDED for result in results
    )
    violations = [
        result for result in results if result["status"] != STATUS_GROUNDED
    ]
    total = len(results)
    return {
        "grounded": total > 0 and not violations,
        "grounded_ratio": round(grounded_count / total, 3) if total else 0.0,
        "claim_count": total,
        "claims": results,
        "violations": violations,
        "checks": ["source_exists", "inside_retrieved_envelope"],
        "semantic_entailment_checked": False,
    }
