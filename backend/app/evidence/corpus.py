"""Read-only access to the authoritative medical evidence corpus.

V2 exposes stable Document, Claim, Topic, Span, and Claim-Evidence interfaces.
The existing curated search API remains available and can temporarily read the
legacy V1 tables during rollout. Nothing in this module writes to SQLite,
calls a model, or accesses the network.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import quote


TOPIC_ALIASES: dict[str, str] = {
    "sodium_and_hypertension": "sodium_hypertension",
    "mediterranean_diet_and_cardiovascular_risk": "mediterranean_cvd",
    "time_restricted_eating_and_weight": "time_restricted_eating",
    "time_restricted_eating": "time_restricted_eating",
    "sodium_hypertension": "sodium_hypertension",
    "mediterranean_cvd": "mediterranean_cvd",
}

_STOPWORDS = {
    "health",
    "healthy",
    "question",
    "what",
    "how",
    "why",
    "when",
    "diet",
    "disease",
    "effect",
    "benefit",
    "study",
    "review",
    "information",
    "general",
    "about",
    "with",
    "from",
    "that",
    "this",
    "and",
    "or",
}

_LITERATURE_AGAINST = re.compile(
    r"\b(no benefit|no effect|no difference|not superior|no association|"
    r"no significant|did not reduce|did not lower|failed to|adverse|harmful|"
    r"conflicting|inconsistent|no mortality benefit)\b",
    re.IGNORECASE,
)
_LITERATURE_SUPPORT = re.compile(
    r"\b(reduced|lowered|decreased|associated with lower|beneficial|"
    r"improved|effective|significant reduction|significant decrease)\b",
    re.IGNORECASE,
)

_TIER_RANK = {
    "T1_guideline": 5,
    "T2_evidence_synthesis": 4,
    "T3_randomized_trial": 3,
    "T5_review": 2,
    "T6_other_pubmed": 1,
    "ungraded": 0,
}
_TIER_RELIABILITY = {
    "T1_guideline": 0.94,
    "T2_evidence_synthesis": 0.92,
    "T3_randomized_trial": 0.88,
    "T5_review": 0.84,
    "T6_other_pubmed": 0.76,
    "ungraded": 0.70,
}
_DIRECTION_RELIABILITY = {
    "support": 0.95,
    "boundary": 0.93,
    "mixed": 0.90,
    "context": 0.85,
}
_DIRECTION_MAP = {
    "support": "support",
    "boundary": "context",
    "mixed": "mixed",
    "context": "context",
}


class CorpusError(RuntimeError):
    """Base class for authoritative corpus failures."""


class CorpusUnavailableError(CorpusError):
    """Raised when the authoritative corpus database cannot be opened."""


class CorpusSchemaError(CorpusError):
    """Raised when a V2 repository call sees an incompatible schema."""


class CorpusQueryError(CorpusError):
    """Raised when a read-only corpus query fails."""


def _verdict_item(**values: Any) -> Any:
    # Deferred import keeps low-level repository tools usable without loading
    # the API schema graph. In the application this resolves to the existing
    # Pydantic model and preserves its validation behavior.
    from ..schemas import VerdictEvidenceItem

    return VerdictEvidenceItem(**values)


def _decode_json_array(value: Any, field: str) -> list[Any]:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CorpusSchemaError(f"invalid JSON in corpus field {field}") from exc
    if not isinstance(decoded, list):
        raise CorpusSchemaError(f"corpus field {field} must contain a JSON array")
    return decoded


class AuthoritativeCorpus:
    """Short-lived, read-only SQLite repository for curated evidence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or self._default_path()

    @classmethod
    def from_env(cls) -> "AuthoritativeCorpus | None":
        configured = os.getenv("EVILIFE_CORPUS_DB", "").strip()
        candidate = Path(configured) if configured else cls._default_path()
        return cls(candidate) if candidate.is_file() else None

    @staticmethod
    def _default_path() -> Path:
        frontend_root = Path(__file__).resolve().parents[3]
        candidates = [
            frontend_root.parent
            / "data"
            / "authoritative_health"
            / "authoritative_health.sqlite3",
            frontend_root
            / "data"
            / "authoritative_health"
            / "authoritative_health.sqlite3",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not self.db_path.is_file():
            raise CorpusUnavailableError(
                f"authoritative corpus not found: {self.db_path}"
            )
        encoded_path = quote(str(self.db_path.resolve()), safe="/")
        uri = f"file:{encoded_path}?mode=ro"
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        except CorpusError:
            raise
        except sqlite3.Error as exc:
            raise CorpusQueryError(
                f"authoritative corpus query failed for {self.db_path}: {exc}"
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    def _fetch(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def _fetch_one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> dict[str, Any] | None:
        rows = self._fetch(sql, params)
        return rows[0] if rows else None

    def _schema_version(self) -> str | None:
        table = self._fetch_one(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='schema_meta'"
        )
        if table is None:
            return None
        rows = self._fetch("SELECT schema_version FROM schema_meta")
        if len(rows) != 1 or not isinstance(rows[0].get("schema_version"), str):
            raise CorpusSchemaError(
                "authoritative corpus schema_meta must contain exactly one row"
            )
        return str(rows[0]["schema_version"])

    def _require_v2(self) -> None:
        version = self._schema_version()
        if version is None or not version.startswith("2."):
            rendered = version if version is not None else "legacy/unversioned"
            raise CorpusSchemaError(
                f"authoritative corpus schema 2.x required; found {rendered}"
            )

    def close(self) -> None:
        """No persistent connection to close; retained for compatibility."""

    # ------------------------------------------------------------------
    # Stable V2 repository API
    # ------------------------------------------------------------------

    @staticmethod
    def _claim_dict(row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["safe_actions"] = _decode_json_array(
            result.pop("safe_actions_json"), "safe_actions_json"
        )
        result["does_not_support"] = _decode_json_array(
            result.pop("does_not_support_json"), "does_not_support_json"
        )
        result["consumer_ready"] = bool(result["consumer_ready"])
        return result

    @staticmethod
    def _document_dict(row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["publication_types"] = _decode_json_array(
            result.pop("publication_types_json"), "publication_types_json"
        )
        return result

    def get_claim(self, claim_id: str) -> dict[str, Any] | None:
        self._require_v2()
        row = self._fetch_one(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        )
        return self._claim_dict(row) if row is not None else None

    def get_claims_by_topic(self, topic_id: str) -> list[dict[str, Any]]:
        self._require_v2()
        canonical = TOPIC_ALIASES.get(topic_id, topic_id)
        rows = self._fetch(
            "SELECT * FROM claims WHERE topic_id = ? ORDER BY claim_id",
            (canonical,),
        )
        return [self._claim_dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        self._require_v2()
        row = self._fetch_one(
            """
            SELECT d.*, s.organization, s.source_type, s.base_url,
                   s.access_policy, s.review_status AS source_review_status
            FROM evidence_documents d
            JOIN sources s ON s.source_id = d.source_id
            WHERE d.document_id = ?
            """,
            (document_id,),
        )
        return self._document_dict(row) if row is not None else None

    def get_documents_by_topic(self, topic_id: str) -> list[dict[str, Any]]:
        self._require_v2()
        canonical = TOPIC_ALIASES.get(topic_id, topic_id)
        rows = self._fetch(
            """
            SELECT d.*, s.organization, s.source_type, s.base_url,
                   s.access_policy, s.review_status AS source_review_status,
                   dt.relevance
            FROM document_topics dt
            JOIN evidence_documents d ON d.document_id = dt.document_id
            JOIN sources s ON s.source_id = d.source_id
            WHERE dt.topic_id = ?
            ORDER BY dt.relevance DESC, d.document_id
            """,
            (canonical,),
        )
        return [self._document_dict(row) for row in rows]

    def get_span(self, span_id: str) -> dict[str, Any] | None:
        self._require_v2()
        return self._fetch_one(
            "SELECT * FROM evidence_spans WHERE span_id = ?", (span_id,)
        )

    def get_claim_evidence(self, claim_id: str) -> list[dict[str, Any]]:
        self._require_v2()
        rows = self._fetch(
            """
            SELECT l.relation, l.is_primary, l.note,
                   d.document_id, d.source_id, d.external_id, d.pmid, d.doi,
                   d.title, d.abstract, d.year, d.publication_types_json,
                   d.evidence_tier, d.landing_url, d.content_hash,
                   d.document_version, d.retrieved_at,
                   d.review_status AS document_review_status,
                   s.organization, s.source_type,
                   sp.span_id, sp.locator, sp.quote_text, sp.char_start,
                   sp.char_end, sp.content_hash AS span_content_hash,
                   sp.review_status AS span_review_status
            FROM claim_evidence_links l
            JOIN evidence_documents d ON d.document_id = l.document_id
            JOIN sources s ON s.source_id = d.source_id
            LEFT JOIN evidence_spans sp ON sp.span_id = l.span_id
            WHERE l.claim_id = ?
            ORDER BY l.is_primary DESC, d.document_id, sp.span_id
            """,
            (claim_id,),
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            document = {
                key: row[key]
                for key in (
                    "document_id",
                    "source_id",
                    "external_id",
                    "pmid",
                    "doi",
                    "title",
                    "abstract",
                    "year",
                    "publication_types_json",
                    "evidence_tier",
                    "landing_url",
                    "content_hash",
                    "document_version",
                    "retrieved_at",
                    "document_review_status",
                    "organization",
                    "source_type",
                )
            }
            document["review_status"] = document.pop(
                "document_review_status"
            )
            document = self._document_dict(document)
            span = None
            if row["span_id"] is not None:
                span = {
                    "span_id": row["span_id"],
                    "document_id": row["document_id"],
                    "locator": row["locator"],
                    "quote_text": row["quote_text"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "content_hash": row["span_content_hash"],
                    "review_status": row["span_review_status"],
                }
            result.append(
                {
                    "relation": row["relation"],
                    "is_primary": bool(row["is_primary"]),
                    "note": row["note"],
                    "document": document,
                    "span": span,
                }
            )
        return result

    def verify_document_id(self, document_id: str) -> bool:
        self._require_v2()
        return (
            self._fetch_one(
                "SELECT 1 AS found FROM evidence_documents "
                "WHERE document_id = ?",
                (document_id,),
            )
            is not None
        )

    # ------------------------------------------------------------------
    # Existing curated retrieval API
    # ------------------------------------------------------------------

    @staticmethod
    def _claim_search_columns(v2: bool) -> tuple[str, str]:
        if v2:
            select = (
                "SELECT c.claim_id, c.topic_id, c.claim_text_zh, c.direction, "
                "c.population, c.finding, c.limitations, c.evidence_strength, "
                "c.review_status, c.consumer_ready, d.document_id, d.title, "
                "d.year, s.source_type, s.organization, d.landing_url "
                "FROM claims c "
                "JOIN claim_evidence_links l ON l.claim_id = c.claim_id "
                "AND l.span_id IS NULL "
                "AND l.document_id = ("
                "SELECT l2.document_id FROM claim_evidence_links l2 "
                "WHERE l2.claim_id = c.claim_id AND l2.span_id IS NULL "
                "ORDER BY l2.is_primary DESC, l2.document_id LIMIT 1) "
                "JOIN evidence_documents d ON d.document_id = l.document_id "
                "JOIN sources s ON s.source_id = d.source_id "
            )
            return select, "c.topic_id"
        select = (
            "SELECT c.claim_id, c.source_id, c.topic_id, c.claim_text_zh, "
            "c.direction, c.population, c.finding, c.limitations, "
            "c.evidence_strength, c.review_status, c.consumer_ready, "
            "s.title, s.year, s.source_type, s.organization, s.landing_url "
            "FROM evidence_claims c JOIN sources s ON s.source_id = c.source_id "
        )
        return select, "c.topic_id"

    @staticmethod
    def _claim_items(rows: Sequence[Mapping[str, Any]], *, v2: bool) -> list[Any]:
        results = []
        for row in rows:
            raw_direction = str(row["direction"])
            source_id = row["document_id"] if v2 else row["source_id"]
            results.append(
                _verdict_item(
                    evidence_id=row["claim_id"],
                    source_id=source_id,
                    title=row["title"] or row["claim_text_zh"],
                    year=row["year"],
                    source_type=row["source_type"] or "人工审核主张",
                    organization=row["organization"] or "权威来源",
                    direction=_DIRECTION_MAP.get(raw_direction, "context"),
                    finding=row["finding"] or row["claim_text_zh"],
                    url=row["landing_url"] or "",
                    channel="curated_database",
                    reliability_score=_DIRECTION_RELIABILITY.get(
                        raw_direction, 0.85
                    ),
                )
            )
        return results

    def search_claims(
        self,
        query: str,
        *,
        topic: str | None = None,
        limit: int = 4,
    ) -> list[Any]:
        tokens = self._tokens(query)
        if not tokens or limit <= 0:
            return []
        try:
            version = self._schema_version()
            if version is not None and not version.startswith("2."):
                raise CorpusSchemaError(
                    f"unsupported authoritative corpus schema: {version}"
                )
            v2 = version is not None
            select, topic_column = self._claim_search_columns(v2)
            clauses = [
                "(c.claim_text_zh LIKE ? OR c.finding LIKE ? "
                "OR c.population LIKE ?)"
                for _ in tokens
            ]
            params: list[Any] = []
            for token in tokens:
                params.extend([f"%{token}%", f"%{token}%", f"%{token}%"])
            where = " OR ".join(clauses)
            corpus_topic = TOPIC_ALIASES.get(topic or "", topic)
            if corpus_topic:
                where = f"({where}) AND {topic_column} = ?"
                params.append(corpus_topic)
            sql = (
                select
                + f"WHERE {where} "
                + "ORDER BY c.consumer_ready DESC, c.claim_id LIMIT ?"
            )
            params.append(limit)
            rows = self._fetch(sql, params)
            results = self._claim_items(rows, v2=v2)
            if not results and corpus_topic:
                results = self._claims_by_topic(
                    corpus_topic, limit=limit, v2=v2
                )
            return results
        except CorpusUnavailableError:
            return []

    def _claims_by_topic(
        self, corpus_topic: str, *, limit: int, v2: bool
    ) -> list[Any]:
        select, topic_column = self._claim_search_columns(v2)
        rows = self._fetch(
            select
            + f"WHERE {topic_column} = ? "
            + "ORDER BY c.consumer_ready DESC, c.claim_id LIMIT ?",
            (corpus_topic, limit),
        )
        return self._claim_items(rows, v2=v2)

    def search_literature(
        self,
        query: str,
        *,
        topic: str | None = None,
        limit: int = 4,
    ) -> list[Any]:
        tokens = self._tokens(query)
        if not tokens or limit <= 0:
            return []
        tokens = [
            token
            for token in tokens
            if len(token) < 4
            or not token.isascii()
            or token.lower() not in _STOPWORDS
        ]
        if not tokens:
            return []
        try:
            version = self._schema_version()
            if version is not None and not version.startswith("2."):
                raise CorpusSchemaError(
                    f"unsupported authoritative corpus schema: {version}"
                )
            v2 = version is not None
            corpus_topic = TOPIC_ALIASES.get(topic or "", topic)
            if v2:
                clauses = [
                    "("
                    "d.title LIKE ? OR COALESCE(d.abstract, '') LIKE ? OR "
                    "EXISTS ("
                    "SELECT 1 FROM document_topics qdt "
                    "JOIN topics qt ON qt.topic_id = qdt.topic_id "
                    "WHERE qdt.document_id = d.document_id AND ("
                    "qt.topic_id LIKE ? OR COALESCE(qt.title_en, '') LIKE ? "
                    "OR qt.title_zh LIKE ? OR qt.aliases_json LIKE ?"
                    ")"
                    ")"
                    ")"
                    for _ in tokens
                ]
                table = "evidence_documents d"
                columns = (
                    "d.document_id, d.pmid, d.doi, d.title, d.abstract, "
                    "s.organization AS journal, d.year, "
                    "d.publication_types_json, d.evidence_tier, "
                    "d.landing_url"
                )
                joins = " JOIN sources s ON s.source_id = d.source_id"
            else:
                clauses = [
                    "(title LIKE ? OR abstract LIKE ?)" for _ in tokens
                ]
                table = "literature_records"
                columns = (
                    "pmid, doi, title, abstract, journal, year, "
                    "publication_types_json, evidence_tier, landing_url"
                )
                joins = ""
            params: list[Any] = []
            for token in tokens:
                pattern = f"%{token}%"
                params.extend([pattern] * (6 if v2 else 2))
            where = " AND ".join(clauses)
            if corpus_topic:
                if v2:
                    where = (
                        f"({where}) AND EXISTS (SELECT 1 FROM document_topics dt "
                        "WHERE dt.document_id=d.document_id AND dt.topic_id=?)"
                    )
                else:
                    where = (
                        f"({where}) AND EXISTS (SELECT 1 FROM literature_topics lt "
                        "WHERE lt.pmid=literature_records.pmid AND lt.topic_id=?)"
                    )
                params.append(corpus_topic)
            candidate_limit = min(max(limit * 12, 48), 96)
            params.append(candidate_limit)
            rows = self._fetch(
                f"SELECT {columns} FROM {table}{joins} WHERE {where} LIMIT ?",
                params,
            )
            rows.sort(
                key=lambda row: self._literature_relevance(row, tokens),
                reverse=True,
            )
            results = []
            for row in rows[:limit]:
                abstract = row["abstract"] or ""
                if _LITERATURE_AGAINST.search(abstract):
                    direction = "against"
                elif _LITERATURE_SUPPORT.search(abstract):
                    direction = "support"
                else:
                    direction = "context"
                tier = row["evidence_tier"] or "ungraded"
                evidence_id = (
                    row["document_id"]
                    if v2
                    else f"L{row['pmid']}"
                )
                results.append(
                    _verdict_item(
                        evidence_id=evidence_id,
                        source_id=evidence_id,
                        title=row["title"] or evidence_id,
                        year=row["year"],
                        source_type=tier.replace("_", " "),
                        organization=row["journal"] or "权威来源",
                        direction=direction,
                        finding=abstract[:1800] if abstract else "无摘要",
                        url=row["landing_url"] or "",
                        channel="curated_database",
                        reliability_score=_TIER_RELIABILITY.get(tier, 0.70),
                    )
                )
            return results
        except CorpusUnavailableError:
            return []

    @staticmethod
    def _literature_relevance(
        row: Mapping[str, Any], tokens: Sequence[str]
    ) -> tuple[int, int]:
        title = str(row["title"] or "").lower()
        abstract = str(row["abstract"] or "").lower()
        literal = sum(5 for token in tokens if token.lower() in title)
        literal += sum(1 for token in tokens if token.lower() in abstract)
        tier = _TIER_RANK.get(str(row["evidence_tier"] or "ungraded"), 0)
        return literal, tier

    def search(
        self,
        query: str,
        *,
        topic: str | None = None,
        claims_limit: int = 4,
        literature_limit: int = 3,
    ) -> list[Any]:
        return [
            *self.search_claims(query, topic=topic, limit=claims_limit),
            *self.search_literature(
                query, topic=topic, limit=literature_limit
            ),
        ]

    @staticmethod
    def _tokens(query: str) -> list[str]:
        normalized = (query or "").strip()
        if not normalized:
            return []
        tokens: list[str] = []
        for part in re.split(r"[\s,，。;；:：!?！？]+|\s+", normalized):
            part = part.strip()
            if not part:
                continue
            cjk_runs = re.findall(r"[\u4e00-\u9fff]+", part)
            if cjk_runs and "".join(cjk_runs) == part:
                if len(part) <= 4:
                    tokens.append(part)
                else:
                    tokens.extend(AuthoritativeCorpus._cjk_windows(part))
            else:
                tokens.extend(
                    token
                    for token in re.split(r"[^A-Za-z0-9\-]+", part)
                    if token
                )
        seen: set[str] = set()
        return [
            token
            for token in tokens
            if not (token in seen or seen.add(token))
        ][:8]

    @staticmethod
    def _cjk_windows(
        text: str, width: int = 4, max_pieces: int = 4
    ) -> list[str]:
        pieces: list[str] = []
        step = max(1, (len(text) - width) // max_pieces)
        for index in range(0, len(text) - width + 1, step):
            piece = text[index : index + width]
            if piece not in pieces:
                pieces.append(piece)
            if len(pieces) >= max_pieces:
                break
        return pieces or [text[:width]]
