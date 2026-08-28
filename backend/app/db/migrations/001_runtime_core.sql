CREATE TABLE subjects (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE health_connections (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL,
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    scopes_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(scopes_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_id, connector_id, external_id)
);

CREATE TABLE health_sync_runs (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    connector_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
    received INTEGER NOT NULL DEFAULT 0 CHECK(received >= 0),
    accepted INTEGER NOT NULL DEFAULT 0 CHECK(accepted >= 0),
    skipped INTEGER NOT NULL DEFAULT 0 CHECK(skipped >= 0),
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE health_daily_metrics (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    sync_run_id TEXT REFERENCES health_sync_runs(id) ON DELETE SET NULL,
    metric_date TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(subject_id, metric_date, metric_type, source)
);

CREATE INDEX idx_health_metrics_subject_date
    ON health_daily_metrics(subject_id, metric_date DESC, metric_type);
CREATE INDEX idx_health_sync_subject_started
    ON health_sync_runs(subject_id, started_at DESC);
