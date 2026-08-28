CREATE TABLE users (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL UNIQUE REFERENCES subjects(id) ON DELETE RESTRICT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_algorithm TEXT NOT NULL DEFAULT 'argon2id',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE auth_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE CHECK(length(token_hash) = 64),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT,
    user_agent TEXT
);

CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id, expires_at DESC);
CREATE INDEX idx_auth_sessions_token ON auth_sessions(token_hash);

CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'life' CHECK(mode IN ('life', 'professional')),
    messages_json TEXT NOT NULL CHECK(json_valid(messages_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, session_id)
);

CREATE INDEX idx_conversations_user_updated
    ON conversations(user_id, updated_at DESC);
