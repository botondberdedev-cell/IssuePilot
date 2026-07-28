-- Governance and feedback tables (gov_ and fbk_ prefixes).
CREATE TABLE gov_configurations (
    configuration_id TEXT PRIMARY KEY,
    task             TEXT NOT NULL,
    model            TEXT NOT NULL,
    role             TEXT NOT NULL,
    dataset_hash     TEXT NOT NULL,
    metrics          TEXT NOT NULL,
    promoted_at      TEXT
);

-- At most one champion per task class, enforced by the database rather than
-- by convention: two champions would make "what shipped" unanswerable.
CREATE UNIQUE INDEX idx_gov_one_champion_per_task
    ON gov_configurations (task) WHERE role = 'champion';

CREATE TABLE fbk_feedback (
    feedback_id TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    note        TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX idx_fbk_run ON fbk_feedback (run_id);
