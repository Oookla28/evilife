"""Build the V2 authoritative evidence corpus from checked-in JSON packets.

The build is deliberately offline. JSON packets are validated before any
database is written, records are inserted in deterministic order, and the
finished temporary database replaces the configured output only after both
SQLite and corpus-level validation succeed.

The legacy SQLite file is never used as content input. It may be inspected by
operators to establish expected row counts, but authoritative content must
come from the checked-in packets and their reviewed metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
PACKETS_DIR = ROOT / "data" / "evidence"
DEFAULT_OUTPUT = Path(__file__).with_name("authoritative_health.sqlite3")
DEFAULT_MANIFEST = Path(__file__).with_name("corpus_manifest.json")
SCHEMA_PATH = Path(__file__).with_name("schema_v2.sql")

SCHEMA_VERSION = "2.0.0"
BUILDER_VERSION = "2.0.0"
DEFAULT_MINIMUM_COUNTS = (10, 33, 10)  # sources, claims, documents

TOPIC_IDS = {
    "sodium_and_hypertension": "sodium_hypertension",
    "mediterranean_diet_and_cardiovascular_risk": "mediterranean_cvd",
    "time_restricted_eating_and_weight": "time_restricted_eating",
}

_PMID_URL = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)(?:/|$)", re.I)
_PMC_URL = re.compile(
    r"(?:europepmc\.org/articles/|ncbi\.nlm\.nih\.gov/pmc/articles/)(PMC\d+)",
    re.I,
)
_COCHRANE_ID = re.compile(r"\b(CD\d{6})\b", re.I)
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
_DOCUMENT_ID = re.compile(r"^[a-z][a-z0-9_]*:[^\s:][^\s]*$")


class PacketValidationError(ValueError):
    """Raised when a checked-in evidence packet violates the input contract."""


class CorpusValidationError(RuntimeError):
    """Raised when a built database fails SQLite or business validation."""


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_stable_json(value).encode("utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PacketValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _required_text(value: Mapping[str, Any], key: str, context: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise PacketValidationError(f"{context}.{key} must be a non-empty string")
    return raw.strip()


def _optional_text(value: Mapping[str, Any], key: str, context: str) -> str | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise PacketValidationError(f"{context}.{key} must be null or a non-empty string")
    return raw.strip()


def _text_array(raw: Any, context: str, *, default: Sequence[str] = ()) -> list[str]:
    if raw is None:
        return list(default)
    if not isinstance(raw, list):
        raise PacketValidationError(f"{context} must be an array")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise PacketValidationError(
                f"{context}[{index}] must be a non-empty string"
            )
        result.append(item.strip())
    return result


def _https_url(raw: str, context: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise PacketValidationError(f"{context} must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise PacketValidationError(f"{context} must not contain credentials")
    return raw


def _utc_timestamp(raw: str | None, context: str) -> str | None:
    if raw is None:
        return None
    if not raw.endswith("Z"):
        raise PacketValidationError(f"{context} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise PacketValidationError(
            f"{context} must be an ISO-8601 UTC timestamp"
        ) from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PacketValidationError(f"{context} must use UTC")
    return raw


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = _sha256_bytes(value.encode("utf-8"))[:16]
    return normalized


def _normalize_doi(value: str | None, context: str) -> str | None:
    if value is None:
        return None
    normalized = unquote(value).strip()
    normalized = re.sub(
        r"^https?://(?:dx\.)?doi\.org/", "", normalized, flags=re.I
    ).lower()
    if not _DOI.fullmatch(normalized):
        raise PacketValidationError(f"{context} is not a valid DOI")
    return normalized


def _pmid_from_url(url: str) -> str | None:
    match = _PMID_URL.search(url)
    return match.group(1) if match else None


def _pmcid_from_url(url: str) -> str | None:
    match = _PMC_URL.search(url)
    return match.group(1).upper() if match else None


def _doi_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"doi.org", "dx.doi.org"}:
        return None
    return _normalize_doi(unquote(parsed.path.lstrip("/")), "DOI URL")


def _document_identity(
    item: Mapping[str, Any], context: str
) -> tuple[str, str, str | None, str | None]:
    url = _required_text(item, "url", context)
    explicit_pmid = _optional_text(item, "pmid", context)
    if explicit_pmid is not None and not re.fullmatch(r"[1-9]\d*", explicit_pmid):
        raise PacketValidationError(
            f"{context}.pmid must contain a positive decimal identifier"
        )
    url_pmid = _pmid_from_url(url)
    if explicit_pmid and url_pmid and explicit_pmid != url_pmid:
        raise PacketValidationError(f"{context}.pmid conflicts with its PubMed URL")
    pmid = explicit_pmid or url_pmid

    doi = _normalize_doi(_optional_text(item, "doi", context), f"{context}.doi")
    doi = doi or _doi_from_url(url)
    pmcid = _optional_text(item, "pmcid", context) or _pmcid_from_url(url)
    if pmcid is not None:
        pmcid = pmcid.upper()
        if not re.fullmatch(r"PMC\d+", pmcid):
            raise PacketValidationError(f"{context}.pmcid must look like PMC123456")

    explicit_document_id = _optional_text(item, "document_id", context)
    if explicit_document_id:
        if not _DOCUMENT_ID.fullmatch(explicit_document_id):
            raise PacketValidationError(
                f"{context}.document_id must be a stable namespaced identifier"
            )
        document_id = explicit_document_id
    elif pmid:
        document_id = f"pubmed:{pmid}"
    elif pmcid:
        document_id = f"europe_pmc:{pmcid}"
    elif doi:
        document_id = f"doi:{doi}"
    else:
        cochrane = _COCHRANE_ID.search(
            " ".join(
                [
                    str(item.get("source_id", "")),
                    str(item.get("external_id", "")),
                    url,
                ]
            )
        )
        if cochrane:
            document_id = f"cochrane:{cochrane.group(1).upper()}"
        else:
            # Explicitly an internal curated identifier, not a claimed PMID,
            # DOI, or external accession.
            source_id = _required_text(item, "source_id", context)
            document_id = f"curated:{_slug(source_id)}"

    external_id = (
        _optional_text(item, "external_id", context)
        or pmid
        or pmcid
        or doi
        or _required_text(item, "source_id", context)
    )
    return document_id, external_id, pmid, doi


def _claim_entries(raw: Any, context: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise PacketValidationError(f"{context} must be an array")
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(raw):
        entry_context = f"{context}[{index}]"
        if isinstance(entry, str):
            if not entry.strip():
                raise PacketValidationError(f"{entry_context} must not be empty")
            result.append({"claim_text_zh": entry.strip()})
        elif isinstance(entry, dict):
            _required_text(entry, "claim_text_zh", entry_context)
            result.append(dict(entry))
        else:
            raise PacketValidationError(
                f"{entry_context} must be a string or claim object"
            )
    return result


def _load_packets(
    packets_dir: Path,
) -> tuple[list[tuple[str, dict[str, Any]]], str, list[dict[str, str]]]:
    paths = sorted(packets_dir.glob("*.json"), key=lambda path: path.name)
    if not paths:
        raise RuntimeError(f"no evidence packets found in {packets_dir}")

    packets: list[tuple[str, dict[str, Any]]] = []
    digest = hashlib.sha256()
    file_manifest: list[dict[str, str]] = []
    for path in paths:
        raw = path.read_bytes()
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PacketValidationError(f"{path.name} is not valid UTF-8") from exc
        try:
            packet = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise PacketValidationError(f"invalid JSON in {path.name}: {exc}") from exc
        if not isinstance(packet, dict):
            raise PacketValidationError(f"{path.name} must contain a JSON object")
        file_hash = _sha256_bytes(raw)
        name_bytes = path.name.encode("utf-8")
        digest.update(len(name_bytes).to_bytes(4, "big"))
        digest.update(name_bytes)
        digest.update(bytes.fromhex(file_hash))
        packets.append((path.name, packet))
        file_manifest.append({"name": path.name, "sha256": file_hash})
    return packets, digest.hexdigest(), file_manifest


def _add_unique(
    records: dict[str, dict[str, Any]],
    key: str,
    record: dict[str, Any],
    context: str,
) -> None:
    previous = records.get(key)
    if previous is not None and previous != record:
        raise PacketValidationError(f"conflicting records for {context} {key}")
    records[key] = record


def _normalize_span(
    raw: Any,
    *,
    document_id: str,
    abstract: str | None,
    context: str,
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(raw, dict):
        raise PacketValidationError(f"{context} must be an object")
    locator = _required_text(raw, "locator", context)
    quote_text = _required_text(raw, "quote_text", context)
    char_start = raw.get("char_start")
    char_end = raw.get("char_end")
    if (char_start is None) != (char_end is None):
        raise PacketValidationError(
            f"{context}.char_start and char_end must be provided together"
        )
    if char_start is not None:
        if (
            not isinstance(char_start, int)
            or isinstance(char_start, bool)
            or not isinstance(char_end, int)
            or isinstance(char_end, bool)
            or char_start < 0
            or char_end <= char_start
        ):
            raise PacketValidationError(f"{context} has invalid character offsets")
        if locator == "abstract" and abstract is not None:
            if char_end > len(abstract) or abstract[char_start:char_end] != quote_text:
                raise PacketValidationError(
                    f"{context} offsets do not select quote_text from the abstract"
                )

    span_id = _optional_text(raw, "span_id", context)
    if span_id is None:
        identity = {
            "document_id": document_id,
            "locator": locator,
            "quote_text": quote_text,
        }
        span_id = f"span-{_sha256_json(identity)[:20]}"
    elif not re.fullmatch(r"span-[A-Za-z0-9._-]+", span_id):
        raise PacketValidationError(f"{context}.span_id has an invalid format")

    claim_ids = _text_array(raw.get("claim_ids"), f"{context}.claim_ids")
    record = {
        "span_id": span_id,
        "document_id": document_id,
        "locator": locator,
        "quote_text": quote_text,
        "char_start": char_start,
        "char_end": char_end,
        "content_hash": _sha256_bytes(quote_text.encode("utf-8")),
        "review_status": _optional_text(raw, "review_status", context)
        or "human_quote_checked",
    }
    return record, claim_ids


def _records_from_packets(
    packets: Sequence[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], str | None]:
    sources: dict[str, dict[str, Any]] = {}
    documents: dict[str, dict[str, Any]] = {}
    topics: dict[str, dict[str, Any]] = {}
    spans: dict[str, dict[str, Any]] = {}
    claims: dict[str, dict[str, Any]] = {}
    document_topics: dict[str, dict[str, Any]] = {}
    links: dict[str, dict[str, Any]] = {}
    pending_span_links: list[tuple[str, str, str]] = []
    corpus_versions: set[str] = set()

    for file_name, packet in packets:
        context = file_name
        packet_topic = _required_text(packet, "topic", context)
        topic_id = TOPIC_IDS.get(packet_topic, packet_topic)
        corpus_version = _optional_text(packet, "corpus_version", context)
        if corpus_version:
            corpus_versions.add(corpus_version)

        aliases = _text_array(packet.get("aliases"), f"{context}.aliases")
        aliases = list(dict.fromkeys([packet_topic, topic_id, *aliases]))
        topic_record = {
            "topic_id": topic_id,
            "title_zh": _optional_text(packet, "title_zh", context)
            or _optional_text(packet, "topic_title_zh", context)
            or topic_id,
            "title_en": _optional_text(packet, "title_en", context)
            or _optional_text(packet, "topic_title_en", context),
            "aliases_json": _stable_json(aliases),
            "status": _optional_text(packet, "status", context) or "active",
        }
        _add_unique(topics, topic_id, topic_record, "topic")

        safe_actions = _text_array(
            packet.get("safe_actions"), f"{context}.safe_actions"
        )
        packet_strength = _optional_text(packet, "evidence_strength", context)
        evidence_items = packet.get("evidence_items")
        if not isinstance(evidence_items, list) or not evidence_items:
            raise PacketValidationError(
                f"{context}.evidence_items must be a non-empty array"
            )

        for item_index, raw_item in enumerate(evidence_items):
            item_context = f"{context}.evidence_items[{item_index}]"
            if not isinstance(raw_item, dict):
                raise PacketValidationError(f"{item_context} must be an object")
            item = raw_item
            source_id = _required_text(item, "source_id", item_context)
            title = _required_text(item, "title", item_context)
            organization = _required_text(item, "organization", item_context)
            source_type = _required_text(item, "source_type", item_context)
            url = _https_url(
                _required_text(item, "url", item_context), f"{item_context}.url"
            )
            parsed_url = urlparse(url)
            default_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            base_url = _https_url(
                _optional_text(item, "base_url", item_context) or default_base_url,
                f"{item_context}.base_url",
            )
            access_policy = (
                _optional_text(item, "access_policy", item_context)
                or "metadata_only"
            )
            if access_policy not in {"open", "metadata_only", "licensed"}:
                raise PacketValidationError(
                    f"{item_context}.access_policy is invalid"
                )
            review_status = (
                _optional_text(item, "review_status", item_context)
                or "human_summary_checked"
            )

            source_record = {
                "source_id": source_id,
                "title": title,
                "organization": organization,
                "source_type": source_type,
                "base_url": base_url,
                "access_policy": access_policy,
                "review_status": review_status,
            }
            _add_unique(sources, source_id, source_record, "source")

            document_id, external_id, pmid, doi = _document_identity(
                item, item_context
            )
            abstract = _optional_text(item, "abstract", item_context)
            year = item.get("year")
            if year is not None and (
                not isinstance(year, int)
                or isinstance(year, bool)
                or not 1000 <= year <= 9999
            ):
                raise PacketValidationError(
                    f"{item_context}.year must be a four-digit integer"
                )
            publication_types = _text_array(
                item.get("publication_types"),
                f"{item_context}.publication_types",
                default=(source_type,),
            )
            evidence_tier = (
                _optional_text(item, "evidence_tier", item_context) or "ungraded"
            )
            document_version = (
                _optional_text(item, "document_version", item_context) or "1"
            )
            retrieved_at = _utc_timestamp(
                _optional_text(item, "retrieved_at", item_context),
                f"{item_context}.retrieved_at",
            )
            document_content = {
                "document_id": document_id,
                "external_id": external_id,
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "year": year,
                "publication_types": publication_types,
                "evidence_tier": evidence_tier,
            }
            document_record = {
                "document_id": document_id,
                "source_id": source_id,
                "external_id": external_id,
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "year": year,
                "publication_types_json": _stable_json(publication_types),
                "evidence_tier": evidence_tier,
                "landing_url": url,
                "content_hash": _sha256_json(document_content),
                "document_version": document_version,
                "retrieved_at": retrieved_at,
                "review_status": review_status,
            }
            _add_unique(documents, document_id, document_record, "document")

            relevance = item.get("topic_relevance")
            if relevance is not None and (
                not isinstance(relevance, (int, float))
                or isinstance(relevance, bool)
                or not 0 <= relevance <= 1
            ):
                raise PacketValidationError(
                    f"{item_context}.topic_relevance must be 0..1"
                )
            topic_link = {
                "document_id": document_id,
                "topic_id": topic_id,
                "relevance": float(relevance) if relevance is not None else None,
            }
            _add_unique(
                document_topics,
                f"{document_id}\0{topic_id}",
                topic_link,
                "document-topic link",
            )

            support_entries = _claim_entries(
                item.get("supports"), f"{item_context}.supports"
            )
            boundary_entries = _claim_entries(
                item.get("does_not_support"),
                f"{item_context}.does_not_support",
            )
            boundaries_as_text = [
                _required_text(entry, "claim_text_zh", item_context)
                for entry in boundary_entries
            ]
            for direction, entries, prefix in (
                ("support", support_entries, "S"),
                ("boundary", boundary_entries, "B"),
            ):
                for claim_index, entry in enumerate(entries, start=1):
                    claim_context = (
                        f"{item_context}.{direction}[{claim_index - 1}]"
                    )
                    claim_text = _required_text(
                        entry, "claim_text_zh", claim_context
                    )
                    claim_id = _optional_text(
                        entry, "claim_id", claim_context
                    ) or f"C_{_safe_id(source_id)}_{prefix}{claim_index}"
                    if not re.fullmatch(
                        r"[A-Za-z][A-Za-z0-9_.-]*", claim_id
                    ):
                        raise PacketValidationError(
                            f"{claim_context}.claim_id has an invalid format"
                        )
                    finding = (
                        _optional_text(entry, "finding", claim_context)
                        or claim_text
                    )
                    relation = (
                        _optional_text(entry, "relation", claim_context)
                        or ("supports" if direction == "support" else "boundary")
                    )
                    if relation not in {
                        "supports",
                        "refutes",
                        "context",
                        "boundary",
                    }:
                        raise PacketValidationError(
                            f"{claim_context}.relation is invalid"
                        )
                    consumer_ready = entry.get(
                        "consumer_ready", item.get("consumer_ready", 1)
                    )
                    if consumer_ready not in (0, 1, False, True):
                        raise PacketValidationError(
                            f"{claim_context}.consumer_ready must be 0 or 1"
                        )
                    claim_record = {
                        "claim_id": claim_id,
                        "topic_id": topic_id,
                        "claim_text_zh": claim_text,
                        "direction": direction,
                        "population": _optional_text(
                            entry, "population", claim_context
                        )
                        or _optional_text(item, "population", item_context),
                        "finding": finding,
                        "limitations": _optional_text(
                            entry, "limitations", claim_context
                        )
                        or _optional_text(item, "limitations", item_context),
                        "evidence_strength": _optional_text(
                            entry, "evidence_strength", claim_context
                        )
                        or _optional_text(
                            item, "evidence_strength", item_context
                        )
                        or packet_strength,
                        "safe_actions_json": _stable_json(safe_actions),
                        "does_not_support_json": _stable_json(
                            boundaries_as_text
                        ),
                        "review_status": _optional_text(
                            entry, "review_status", claim_context
                        )
                        or review_status,
                        "consumer_ready": int(bool(consumer_ready)),
                    }
                    _add_unique(claims, claim_id, claim_record, "claim")
                    link_record = {
                        "claim_id": claim_id,
                        "document_id": document_id,
                        "span_id": None,
                        "relation": relation,
                        "is_primary": 1,
                        "note": _optional_text(
                            entry, "link_note", claim_context
                        ),
                    }
                    _add_unique(
                        links,
                        f"{claim_id}\0{document_id}\0",
                        link_record,
                        "claim-document link",
                    )

            raw_spans = item.get(
                "evidence_spans", item.get("spans", [])
            )
            if not isinstance(raw_spans, list):
                raise PacketValidationError(
                    f"{item_context}.evidence_spans must be an array"
                )
            for span_index, raw_span in enumerate(raw_spans):
                span_context = (
                    f"{item_context}.evidence_spans[{span_index}]"
                )
                span_record, linked_claim_ids = _normalize_span(
                    raw_span,
                    document_id=document_id,
                    abstract=abstract,
                    context=span_context,
                )
                _add_unique(
                    spans, span_record["span_id"], span_record, "span"
                )
                for claim_id in linked_claim_ids:
                    pending_span_links.append(
                        (claim_id, document_id, span_record["span_id"])
                    )

    if len(corpus_versions) > 1:
        raise PacketValidationError(
            "packets declare conflicting corpus versions: "
            f"{sorted(corpus_versions)}"
        )
    for claim_id, document_id, span_id in pending_span_links:
        if claim_id not in claims:
            raise PacketValidationError(
                f"span {span_id} references unknown claim {claim_id}"
            )
        document_link = links.get(f"{claim_id}\0{document_id}\0")
        if document_link is None:
            raise PacketValidationError(
                f"span {span_id} and claim {claim_id} do not share a document"
            )
        span_link = {
            **document_link,
            "span_id": span_id,
            "is_primary": 0,
        }
        _add_unique(
            links,
            f"{claim_id}\0{document_id}\0{span_id}",
            span_link,
            "claim-span link",
        )

    tables = {
        "sources": sources,
        "evidence_documents": documents,
        "topics": topics,
        "document_topics": document_topics,
        "evidence_spans": spans,
        "claims": claims,
        "claim_evidence_links": links,
    }
    corpus_version = next(iter(corpus_versions), None)
    return tables, corpus_version


def _insert_records(
    connection: sqlite3.Connection,
    tables: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> None:
    order = (
        "sources",
        "evidence_documents",
        "topics",
        "document_topics",
        "evidence_spans",
        "claims",
        "claim_evidence_links",
    )
    for table in order:
        records = tables[table]
        for record_key in sorted(records):
            record = records[record_key]
            columns = tuple(record)
            placeholders = ", ".join("?" for _ in columns)
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({placeholders})"
            )
            connection.execute(
                sql, tuple(record[column] for column in columns)
            )


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "schema_meta",
        "sources",
        "evidence_documents",
        "topics",
        "document_topics",
        "evidence_spans",
        "claims",
        "claim_evidence_links",
    )
    return {
        table: int(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
        for table in tables
    }


def _validate_database(
    connection: sqlite3.Connection,
    *,
    minimum_counts: tuple[int, int, int],
) -> tuple[dict[str, int], str, list[tuple[Any, ...]]]:
    integrity = str(
        connection.execute("PRAGMA integrity_check").fetchone()[0]
    )
    if integrity != "ok":
        raise CorpusValidationError(
            f"PRAGMA integrity_check failed: {integrity}"
        )
    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()
    if foreign_key_errors:
        raise CorpusValidationError(
            f"PRAGMA foreign_key_check failed: {foreign_key_errors!r}"
        )

    counts = _table_counts(connection)
    if counts["schema_meta"] != 1:
        raise CorpusValidationError(
            "schema_meta must contain exactly one row; "
            f"found {counts['schema_meta']}"
        )
    expected_sources, expected_claims, expected_documents = minimum_counts
    failures = []
    for table, expected in (
        ("sources", expected_sources),
        ("claims", expected_claims),
        ("evidence_documents", expected_documents),
    ):
        if counts[table] < expected:
            failures.append(
                f"{table}={counts[table]} (minimum {expected})"
            )
    if failures:
        raise CorpusValidationError(
            "baseline count validation failed: " + ", ".join(failures)
        )

    checks = {
        "documents without content hash": (
            "SELECT COUNT(*) FROM evidence_documents "
            "WHERE content_hash IS NULL OR content_hash = ''"
        ),
        "non-HTTPS source URLs": (
            "SELECT COUNT(*) FROM sources WHERE base_url NOT LIKE 'https://%'"
        ),
        "non-HTTPS document URLs": (
            "SELECT COUNT(*) FROM evidence_documents "
            "WHERE landing_url NOT LIKE 'https://%'"
        ),
        "orphan document topics": (
            "SELECT COUNT(*) FROM document_topics dt "
            "LEFT JOIN evidence_documents d ON d.document_id=dt.document_id "
            "LEFT JOIN topics t ON t.topic_id=dt.topic_id "
            "WHERE d.document_id IS NULL OR t.topic_id IS NULL"
        ),
        "orphan claim links": (
            "SELECT COUNT(*) FROM claim_evidence_links l "
            "LEFT JOIN claims c ON c.claim_id=l.claim_id "
            "LEFT JOIN evidence_documents d ON d.document_id=l.document_id "
            "WHERE c.claim_id IS NULL OR d.document_id IS NULL"
        ),
        "invalid spans": (
            "SELECT COUNT(*) FROM evidence_spans "
            "WHERE trim(locator)='' OR trim(quote_text)=''"
        ),
    }
    for label, sql in checks.items():
        count = int(connection.execute(sql).fetchone()[0])
        if count:
            raise CorpusValidationError(f"{label}: {count}")
    return counts, integrity, foreign_key_errors


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".json", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            _stable_json(payload) + "\n", encoding="utf-8"
        )
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _preserve_existing_database(output: Path) -> Path | None:
    if not output.exists():
        return None
    backup = output.with_name(f"{output.stem}.backup{output.suffix}")
    if backup.exists():
        return backup
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{backup.stem}-", suffix=backup.suffix, dir=backup.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(output, temporary)
        temporary.replace(backup)
        return backup
    finally:
        temporary.unlink(missing_ok=True)


def build_database(
    output: Path,
    *,
    force: bool = False,
    packets_dir: Path | None = None,
    manifest_path: Path | None = None,
    minimum_counts: tuple[int, int, int] = DEFAULT_MINIMUM_COUNTS,
    backup_existing: bool = True,
) -> tuple[int, int, int]:
    """Build a V2 database and return ``(claims, sources, documents)``.

    ``minimum_counts`` is ordered as ``(sources, claims, documents)``. It is
    configurable for isolated fixtures, while production builds retain the
    established 10/33/10 corpus baseline by default.
    """

    if len(minimum_counts) != 3 or any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        for value in minimum_counts
    ):
        raise ValueError(
            "minimum_counts must contain three non-negative integers"
        )
    output = output.resolve()
    packets_dir = (packets_dir or PACKETS_DIR).resolve()
    manifest_path = (
        manifest_path or output.with_name(DEFAULT_MANIFEST.name)
    ).resolve()
    if output.exists() and not force:
        raise FileExistsError(
            f"database already exists: {output}; use --force to rebuild"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if output.parent != manifest_path.parent:
        raise ValueError(
            "database and manifest must be written to the same directory"
        )

    packets, source_digest, input_files = _load_packets(packets_dir)
    records, declared_corpus_version = _records_from_packets(packets)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    built_at = _utc_now()
    corpus_version = (
        declared_corpus_version or f"corpus-{source_digest[:12]}"
    )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}-",
        suffix=".sqlite3",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    manifest_temporary: Path | None = None
    try:
        with sqlite3.connect(temporary) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.executescript(schema_sql)
            connection.execute(
                """
                INSERT INTO schema_meta (
                    schema_version, corpus_version, built_at,
                    builder_version, source_digest
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    SCHEMA_VERSION,
                    corpus_version,
                    built_at,
                    BUILDER_VERSION,
                    source_digest,
                ),
            )
            _insert_records(connection, records)
            connection.commit()
            counts, integrity, foreign_key_errors = _validate_database(
                connection, minimum_counts=minimum_counts
            )

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "corpus_version": corpus_version,
            "built_at": built_at,
            "builder_version": BUILDER_VERSION,
            "source_digest": source_digest,
            "input_files": input_files,
            "table_row_counts": counts,
            "validation": {
                "integrity_check": integrity,
                "foreign_key_check_errors": len(foreign_key_errors),
            },
        }
        manifest_temporary = _atomic_write_json(manifest_path, manifest)
        if backup_existing:
            _preserve_existing_database(output)
        temporary.replace(output)
        manifest_temporary.replace(manifest_path)
        output.chmod(0o444)
        manifest_path.chmod(0o644)
        return (
            counts["claims"],
            counts["sources"],
            counts["evidence_documents"],
        )
    finally:
        temporary.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)
        for suffix in ("-journal", "-wal", "-shm"):
            Path(f"{temporary}{suffix}").unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--packets-dir", type=Path, default=PACKETS_DIR)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument(
        "--minimum-sources", type=int, default=DEFAULT_MINIMUM_COUNTS[0]
    )
    parser.add_argument(
        "--minimum-claims", type=int, default=DEFAULT_MINIMUM_COUNTS[1]
    )
    parser.add_argument(
        "--minimum-documents", type=int, default=DEFAULT_MINIMUM_COUNTS[2]
    )
    args = parser.parse_args()
    claims, sources, documents = build_database(
        args.output,
        force=args.force,
        packets_dir=args.packets_dir,
        manifest_path=args.manifest,
        minimum_counts=(
            args.minimum_sources,
            args.minimum_claims,
            args.minimum_documents,
        ),
        backup_existing=not args.no_backup,
    )
    print(
        f"built {args.output}: {claims} claims, {sources} sources, "
        f"{documents} evidence documents"
    )


if __name__ == "__main__":
    main()

