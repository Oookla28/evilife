"""Focused tests for the offline authoritative evidence database V2."""

from __future__ import annotations

import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "authoritative_health"))
sys.path.insert(0, str(ROOT / "backend"))

from build_database import (  # noqa: E402
    CorpusValidationError,
    PacketValidationError,
    build_database,
)
from app.evidence.corpus import (  # noqa: E402
    AuthoritativeCorpus,
    CorpusQueryError,
    CorpusSchemaError,
)


BASELINE = (10, 33, 10)
TABLES = {
    "schema_meta",
    "sources",
    "evidence_documents",
    "topics",
    "document_topics",
    "evidence_spans",
    "claims",
    "claim_evidence_links",
}


def _packet() -> dict:
    items = []
    for index in range(10):
        supports = [
            f"测试支持主张 {index}-1",
            f"测试支持主张 {index}-2",
        ]
        boundaries = [f"测试边界主张 {index}-1"]
        if index < 3:
            boundaries.append(f"测试边界主张 {index}-2")
        item = {
            "source_id": f"TEST_SOURCE_{index:02d}",
            "document_id": f"fixture:doc-{index:02d}",
            "external_id": f"FIXTURE-{index:02d}",
            "title": f"Fixture document {index:02d} sodium evidence",
            "year": 2025,
            "source_type": "Systematic Review",
            "organization": "Example Test Organization",
            "url": f"https://example.test/evidence/{index:02d}",
            "publication_types": ["Systematic Review"],
            "evidence_tier": "T2_evidence_synthesis",
            "supports": supports,
            "does_not_support": boundaries,
            "population": "Synthetic test population",
            "limitations": "Synthetic test fixture only",
        }
        if index == 0:
            quote_text = "Test fixture exact quote."
            abstract = f"Background. {quote_text} Conclusion."
            start = abstract.index(quote_text)
            item["abstract"] = abstract
            item["evidence_spans"] = [
                {
                    "span_id": "span-fixture-exact-01",
                    "locator": "abstract",
                    "quote_text": quote_text,
                    "char_start": start,
                    "char_end": start + len(quote_text),
                    "claim_ids": ["C_TEST_SOURCE_00_S1"],
                    "review_status": "fixture_quote_checked",
                }
            ]
        items.append(item)
    return {
        "topic": "fixture_topic",
        "title_zh": "测试主题",
        "title_en": "Fixture topic",
        "aliases": ["fixture"],
        "corpus_version": "fixture-v1",
        "evidence_strength": "medium",
        "safe_actions": ["仅用于自动化测试"],
        "evidence_items": items,
    }


def _write_packet(directory: Path, packet: dict | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "fixture_packet.json"
    path.write_text(
        json.dumps(packet or _packet(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _build(tmp_path: Path, *, name: str = "corpus.sqlite3") -> Path:
    packets = tmp_path / f"packets-{name}"
    _write_packet(packets)
    output = tmp_path / name
    counts = build_database(
        output,
        packets_dir=packets,
        manifest_path=tmp_path / f"{name}.manifest.json",
        minimum_counts=BASELINE,
    )
    assert counts == (33, 10, 10)
    return output


def _rows(db_path: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(sql).fetchall()


def _ensure_verdict_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply the one omitted handoff-pack model when the full app is absent."""

    try:
        __import__("app.schemas")
        return
    except ModuleNotFoundError:
        pass

    schemas = types.ModuleType("app.schemas")

    class VerdictEvidenceItem:
        def __init__(self, **values: object) -> None:
            self.__dict__.update(values)

    schemas.VerdictEvidenceItem = VerdictEvidenceItem
    monkeypatch.setitem(sys.modules, "app.schemas", schemas)


def test_builds_v2_from_an_empty_output_path_and_writes_safe_manifest(
    tmp_path: Path,
) -> None:
    output = _build(tmp_path)
    manifest_path = tmp_path / "corpus.sqlite3.manifest.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)

    assert output.is_file()
    assert manifest["schema_version"] == "2.0.0"
    assert manifest["corpus_version"] == "fixture-v1"
    assert len(manifest["source_digest"]) == 64
    assert manifest["validation"] == {
        "foreign_key_check_errors": 0,
        "integrity_check": "ok",
    }
    assert str(tmp_path) not in manifest_text


def test_schema_tables_indexes_and_version_exist(tmp_path: Path) -> None:
    output = _build(tmp_path)
    table_names = {
        row[0]
        for row in _rows(
            output,
            "SELECT name FROM sqlite_master WHERE type='table'",
        )
    }
    index_names = {
        row[0]
        for row in _rows(
            output,
            "SELECT name FROM sqlite_master WHERE type='index'",
        )
    }

    assert TABLES <= table_names
    assert {
        "uq_evidence_documents_pmid",
        "uq_evidence_documents_doi",
        "idx_document_topics_topic",
        "idx_claims_topic",
        "idx_claim_evidence_links_claim",
        "idx_evidence_spans_document",
    } <= index_names
    assert _rows(output, "SELECT schema_version FROM schema_meta") == [
        ("2.0.0",)
    ]


def test_preserves_baseline_counts_and_sqlite_integrity(tmp_path: Path) -> None:
    output = _build(tmp_path)
    counts = dict(
        _rows(
            output,
            """
            SELECT 'sources', COUNT(*) FROM sources
            UNION ALL SELECT 'claims', COUNT(*) FROM claims
            UNION ALL SELECT 'evidence_documents', COUNT(*) FROM evidence_documents
            """,
        )
    )
    assert counts == {
        "sources": 10,
        "claims": 33,
        "evidence_documents": 10,
    }
    assert _rows(output, "PRAGMA integrity_check") == [("ok",)]
    assert _rows(output, "PRAGMA foreign_key_check") == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("doi", "10.9999/fixture.duplicate"),
        ("pmid", "999999999"),
    ],
)
def test_duplicate_pmid_or_doi_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    packet = _packet()
    packet["evidence_items"][0][field] = value
    packet["evidence_items"][1][field] = value
    packets = tmp_path / "packets"
    _write_packet(packets, packet)

    with pytest.raises(sqlite3.IntegrityError):
        build_database(
            tmp_path / "duplicate.sqlite3",
            packets_dir=packets,
            minimum_counts=BASELINE,
        )


def test_claim_document_and_precise_span_relationships_are_queryable(
    tmp_path: Path,
) -> None:
    output = _build(tmp_path)
    document_links = _rows(
        output,
        """
        SELECT document_id, span_id, relation
        FROM claim_evidence_links
        WHERE claim_id='C_TEST_SOURCE_00_S1'
        ORDER BY span_id
        """,
    )
    span = _rows(
        output,
        """
        SELECT d.abstract, s.quote_text, s.char_start, s.char_end
        FROM evidence_spans s
        JOIN evidence_documents d ON d.document_id=s.document_id
        WHERE s.span_id='span-fixture-exact-01'
        """,
    )[0]

    assert document_links == [
        ("fixture:doc-00", None, "supports"),
        ("fixture:doc-00", "span-fixture-exact-01", "supports"),
    ]
    abstract, quote_text, start, end = span
    assert abstract[start:end] == quote_text
    assert _rows(output, "SELECT COUNT(*) FROM evidence_spans") == [(1,)]


def test_repeat_build_keeps_ids_content_hashes_and_source_digest_stable(
    tmp_path: Path,
) -> None:
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")

    query = (
        "SELECT document_id, content_hash, document_version "
        "FROM evidence_documents ORDER BY document_id"
    )
    assert _rows(first, query) == _rows(second, query)
    assert _rows(first, "SELECT claim_id FROM claims ORDER BY claim_id") == _rows(
        second, "SELECT claim_id FROM claims ORDER BY claim_id"
    )
    assert _rows(first, "SELECT source_digest FROM schema_meta") == _rows(
        second, "SELECT source_digest FROM schema_meta"
    )


def test_failed_rebuild_does_not_damage_existing_database(tmp_path: Path) -> None:
    output = _build(tmp_path)
    before = output.read_bytes()
    bad_packet = _packet()
    bad_packet["evidence_items"][0]["url"] = "http://example.test/not-https"
    packets = tmp_path / "bad-packets"
    _write_packet(packets, bad_packet)

    with pytest.raises(PacketValidationError):
        build_database(
            output,
            force=True,
            packets_dir=packets,
            minimum_counts=BASELINE,
        )

    assert output.read_bytes() == before
    assert not list(tmp_path.glob(".*.sqlite3-journal"))


def test_count_validation_fails_before_replacing_existing_file(
    tmp_path: Path,
) -> None:
    output = _build(tmp_path)
    before = output.read_bytes()
    packets = tmp_path / "packets-too-small"
    packet = _packet()
    packet["evidence_items"] = packet["evidence_items"][:1]
    _write_packet(packets, packet)

    with pytest.raises(CorpusValidationError):
        build_database(
            output,
            force=True,
            packets_dir=packets,
            minimum_counts=BASELINE,
        )

    assert output.read_bytes() == before


def test_authoritative_corpus_v2_repository_is_read_only(tmp_path: Path) -> None:
    output = _build(tmp_path)
    corpus = AuthoritativeCorpus(output)

    claim = corpus.get_claim("C_TEST_SOURCE_00_S1")
    assert claim is not None
    assert claim["safe_actions"] == ["仅用于自动化测试"]
    assert claim["consumer_ready"] is True
    assert len(corpus.get_claims_by_topic("fixture_topic")) == 33
    assert corpus.get_document("fixture:doc-00")["publication_types"] == [
        "Systematic Review"
    ]
    assert len(corpus.get_documents_by_topic("fixture_topic")) == 10
    assert corpus.get_span("span-fixture-exact-01")["locator"] == "abstract"
    evidence = corpus.get_claim_evidence("C_TEST_SOURCE_00_S1")
    assert evidence[0]["document"]["document_id"] == "fixture:doc-00"
    assert evidence[1]["span"]["quote_text"] == "Test fixture exact quote."
    assert corpus.verify_document_id("fixture:doc-00") is True
    assert corpus.verify_document_id("fixture:missing") is False

    with pytest.raises(CorpusQueryError, match="readonly"):
        with corpus._connection() as connection:
            connection.execute("CREATE TABLE forbidden_write(value TEXT)")


def test_v2_repository_rejects_legacy_schema_explicitly(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(legacy) as connection:
        connection.execute("CREATE TABLE sources(source_id TEXT PRIMARY KEY)")

    with pytest.raises(CorpusSchemaError, match="schema 2.x required"):
        AuthoritativeCorpus(legacy).get_claim("anything")


def test_missing_database_keeps_existing_search_degradation(tmp_path: Path) -> None:
    corpus = AuthoritativeCorpus(tmp_path / "missing.sqlite3")

    assert corpus.search("任何问题") == []
    assert corpus.search_claims("任何问题") == []
    assert corpus.search_literature("anything") == []


def test_v2_search_api_remains_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ensure_verdict_schema(monkeypatch)
    corpus = AuthoritativeCorpus(_build(tmp_path))

    claims = corpus.search_claims(
        "测试支持主张", topic="fixture_topic", limit=4
    )
    literature = corpus.search_literature(
        "sodium evidence", topic="fixture_topic", limit=3
    )

    assert claims
    assert all(item.channel == "curated_database" for item in claims)
    assert any(item.direction == "support" for item in claims)
    assert literature
    assert all(item.source_id.startswith("fixture:") for item in literature)


def test_legacy_search_compatibility_for_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_verdict_schema(monkeypatch)
    legacy = ROOT / "data" / "authoritative_health" / "authoritative_health.sqlite3"
    corpus = AuthoritativeCorpus(legacy)

    claims = corpus.search_claims("地中海饮食", limit=4)
    literature = corpus.search_literature("sodium", limit=3)

    assert claims
    assert literature

