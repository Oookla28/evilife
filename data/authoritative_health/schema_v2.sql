PRAGMA foreign_keys = ON;

CREATE TABLE schema_meta (
    schema_version TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    built_at TEXT NOT NULL,
    builder_version TEXT NOT NULL,
    source_digest TEXT NOT NULL
        CHECK(length(source_digest) = 64)
        CHECK(source_digest NOT GLOB '*[^0-9a-f]*')
);

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    organization TEXT NOT NULL CHECK(length(trim(organization)) > 0),
    source_type TEXT NOT NULL CHECK(length(trim(source_type)) > 0),
    base_url TEXT NOT NULL CHECK(base_url LIKE 'https://%'),
    access_policy TEXT NOT NULL
        CHECK(access_policy IN ('open', 'metadata_only', 'licensed')),
    review_status TEXT NOT NULL CHECK(length(trim(review_status)) > 0)
);

CREATE TABLE evidence_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    external_id TEXT NOT NULL CHECK(length(trim(external_id)) > 0),
    pmid TEXT CHECK(
        pmid IS NULL
        OR (pmid GLOB '[1-9]*' AND pmid NOT GLOB '*[^0-9]*')
    ),
    doi TEXT CHECK(doi IS NULL OR (doi LIKE '10.%/%' AND doi = lower(doi))),
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    abstract TEXT,
    year INTEGER CHECK(year IS NULL OR year BETWEEN 1000 AND 9999),
    publication_types_json TEXT NOT NULL
        CHECK(json_valid(publication_types_json))
        CHECK(json_type(publication_types_json) = 'array'),
    evidence_tier TEXT NOT NULL CHECK(length(trim(evidence_tier)) > 0),
    landing_url TEXT NOT NULL CHECK(landing_url LIKE 'https://%'),
    content_hash TEXT NOT NULL
        CHECK(length(content_hash) = 64)
        CHECK(content_hash NOT GLOB '*[^0-9a-f]*'),
    document_version TEXT NOT NULL CHECK(length(trim(document_version)) > 0),
    retrieved_at TEXT,
    review_status TEXT NOT NULL CHECK(length(trim(review_status)) > 0)
);

CREATE UNIQUE INDEX uq_evidence_documents_pmid
    ON evidence_documents(pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX uq_evidence_documents_doi
    ON evidence_documents(doi) WHERE doi IS NOT NULL;
CREATE INDEX idx_evidence_documents_source
    ON evidence_documents(source_id);
CREATE INDEX idx_evidence_documents_landing_url
    ON evidence_documents(landing_url);

CREATE TABLE topics (
    topic_id TEXT PRIMARY KEY,
    title_zh TEXT NOT NULL CHECK(length(trim(title_zh)) > 0),
    title_en TEXT,
    aliases_json TEXT NOT NULL
        CHECK(json_valid(aliases_json))
        CHECK(json_type(aliases_json) = 'array'),
    status TEXT NOT NULL CHECK(length(trim(status)) > 0)
);

CREATE INDEX idx_topics_status ON topics(status);

CREATE TABLE document_topics (
    document_id TEXT NOT NULL REFERENCES evidence_documents(document_id),
    topic_id TEXT NOT NULL REFERENCES topics(topic_id),
    relevance REAL CHECK(relevance IS NULL OR relevance BETWEEN 0.0 AND 1.0),
    PRIMARY KEY (document_id, topic_id)
);

CREATE INDEX idx_document_topics_topic
    ON document_topics(topic_id, document_id);

CREATE TABLE evidence_spans (
    span_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES evidence_documents(document_id),
    locator TEXT NOT NULL CHECK(length(trim(locator)) > 0),
    quote_text TEXT NOT NULL CHECK(length(trim(quote_text)) > 0),
    char_start INTEGER CHECK(char_start IS NULL OR char_start >= 0),
    char_end INTEGER CHECK(char_end IS NULL OR char_end >= 0),
    content_hash TEXT NOT NULL
        CHECK(length(content_hash) = 64)
        CHECK(content_hash NOT GLOB '*[^0-9a-f]*'),
    review_status TEXT NOT NULL CHECK(length(trim(review_status)) > 0),
    CHECK(
        (char_start IS NULL AND char_end IS NULL)
        OR (char_start IS NOT NULL AND char_end IS NOT NULL AND char_end > char_start)
    ),
    UNIQUE (span_id, document_id)
);

CREATE INDEX idx_evidence_spans_document
    ON evidence_spans(document_id, locator);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(topic_id),
    claim_text_zh TEXT NOT NULL CHECK(length(trim(claim_text_zh)) > 0),
    direction TEXT NOT NULL
        CHECK(direction IN ('support', 'boundary', 'mixed', 'context')),
    population TEXT,
    finding TEXT NOT NULL CHECK(length(trim(finding)) > 0),
    limitations TEXT,
    evidence_strength TEXT,
    safe_actions_json TEXT NOT NULL
        CHECK(json_valid(safe_actions_json))
        CHECK(json_type(safe_actions_json) = 'array'),
    does_not_support_json TEXT NOT NULL
        CHECK(json_valid(does_not_support_json))
        CHECK(json_type(does_not_support_json) = 'array'),
    review_status TEXT NOT NULL CHECK(length(trim(review_status)) > 0),
    consumer_ready INTEGER NOT NULL CHECK(consumer_ready IN (0, 1))
);

CREATE INDEX idx_claims_topic ON claims(topic_id, claim_id);
CREATE INDEX idx_claims_direction ON claims(direction, claim_id);

CREATE TABLE claim_evidence_links (
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    document_id TEXT NOT NULL REFERENCES evidence_documents(document_id),
    span_id TEXT,
    relation TEXT NOT NULL
        CHECK(relation IN ('supports', 'refutes', 'context', 'boundary')),
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
    note TEXT,
    PRIMARY KEY (claim_id, document_id, span_id),
    FOREIGN KEY (span_id, document_id)
        REFERENCES evidence_spans(span_id, document_id)
);

-- SQLite permits more than one NULL in a composite key. This partial unique
-- index makes the document-only relationship genuinely unique as intended.
CREATE UNIQUE INDEX uq_claim_document_without_span
    ON claim_evidence_links(claim_id, document_id)
    WHERE span_id IS NULL;
CREATE INDEX idx_claim_evidence_links_claim
    ON claim_evidence_links(claim_id, is_primary DESC, document_id);
CREATE INDEX idx_claim_evidence_links_document
    ON claim_evidence_links(document_id, claim_id);
CREATE INDEX idx_claim_evidence_links_span
    ON claim_evidence_links(span_id) WHERE span_id IS NOT NULL;

