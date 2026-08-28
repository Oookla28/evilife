CREATE TABLE fasts (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    start_at TEXT NOT NULL,
    end_at TEXT,
    goal_hours REAL NOT NULL CHECK(goal_hours BETWEEN 1 AND 24),
    status TEXT NOT NULL CHECK(status IN ('active', 'completed')),
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX uq_active_fast_per_subject
    ON fasts(subject_id) WHERE status = 'active';
CREATE INDEX idx_fasts_subject_started ON fasts(subject_id, start_at DESC);

CREATE TABLE meals (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    calories_low INTEGER NOT NULL CHECK(calories_low >= 0),
    calories_high INTEGER NOT NULL CHECK(calories_high >= calories_low),
    calories_center INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    UNIQUE(subject_id, action_id)
);

CREATE TABLE meal_items (
    id TEXT PRIMARY KEY,
    meal_id TEXT NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    portion TEXT NOT NULL,
    portion_grams_low INTEGER,
    portion_grams_high INTEGER,
    calories_low INTEGER NOT NULL,
    calories_high INTEGER NOT NULL,
    calories_center INTEGER NOT NULL,
    confidence TEXT,
    reference_basis TEXT,
    uncertainty TEXT,
    CHECK(portion_grams_low IS NULL OR portion_grams_low > 0),
    CHECK(portion_grams_high IS NULL OR portion_grams_high >= portion_grams_low),
    CHECK(calories_low >= 0 AND calories_high >= calories_low),
    CHECK(calories_center BETWEEN calories_low AND calories_high)
);

CREATE INDEX idx_meals_subject_created ON meals(subject_id, created_at DESC);
CREATE INDEX idx_meal_items_meal ON meal_items(meal_id);

CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    value REAL,
    note TEXT,
    source TEXT NOT NULL CHECK(source IN ('self_report', 'device', 'ai_estimate')),
    observed_at TEXT NOT NULL,
    connector_id TEXT,
    external_id TEXT,
    created_at TEXT NOT NULL,
    CHECK((kind = 'note' AND note IS NOT NULL) OR (kind <> 'note' AND value IS NOT NULL))
);

CREATE UNIQUE INDEX uq_observation_external
    ON observations(subject_id, connector_id, external_id)
    WHERE connector_id IS NOT NULL AND external_id IS NOT NULL;
CREATE INDEX idx_observations_subject_time
    ON observations(subject_id, observed_at DESC);
CREATE INDEX idx_observations_subject_kind_time
    ON observations(subject_id, kind, observed_at DESC);
