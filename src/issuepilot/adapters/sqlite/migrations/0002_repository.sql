-- Repository context tables (rep_ prefix; this context owns them).
CREATE TABLE rep_snapshots (
    snapshot_id          TEXT PRIMARY KEY,
    locator_fingerprint  TEXT NOT NULL,
    requested_ref        TEXT NOT NULL,
    commit_sha           TEXT NOT NULL,
    root_path            TEXT NOT NULL
);

-- Lookup path for "have we already materialized this exact commit?".
CREATE INDEX idx_rep_snapshots_commit
    ON rep_snapshots (locator_fingerprint, commit_sha);
