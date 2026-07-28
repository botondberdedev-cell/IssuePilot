-- Manifest entries per snapshot, so an index can be built from a cached
-- snapshot without re-acquiring it (and so a repository map can be answered
-- offline).
CREATE TABLE rep_manifest_files (
    commit_sha       TEXT NOT NULL,
    path             TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    language         TEXT,
    included         INTEGER NOT NULL,
    exclusion_reason TEXT,
    PRIMARY KEY (commit_sha, path)
);

CREATE INDEX idx_rep_manifest_included ON rep_manifest_files (commit_sha, included);
