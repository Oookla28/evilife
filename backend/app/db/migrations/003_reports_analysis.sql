CREATE TABLE reports (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    storage_key TEXT NOT NULL,
    status TEXT NOT NULL,
    retention_until TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(subject_id, sha256)
);

CREATE TABLE lab_items (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    value_text TEXT,
    numeric_value REAL,
    unit TEXT,
    reference_range TEXT,
    observed_at TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0 CHECK(confirmed IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE analysis_runs (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    report_id TEXT REFERENCES reports(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE findings (
    id TEXT PRIMARY KEY,
    analysis_run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload_json)),
    created_at TEXT NOT NULL
);

CREATE TABLE finding_evidence_links (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(finding_id, evidence_id, relation)
);

CREATE TABLE corrections (
    id TEXT PRIMARY KEY,
    lab_item_id TEXT NOT NULL REFERENCES lab_items(id) ON DELETE CASCADE,
    user_id TEXT,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_reports_subject_created ON reports(subject_id, created_at DESC);
CREATE INDEX idx_lab_items_report ON lab_items(report_id);
CREATE INDEX idx_analysis_subject_created ON analysis_runs(subject_id, created_at DESC);
CREATE INDEX idx_findings_run ON findings(analysis_run_id);
