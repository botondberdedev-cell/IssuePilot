-- Investigation context tables (inv_ prefix; this context owns them).
CREATE TABLE inv_reports (
    run_id              TEXT PRIMARY KEY,
    report_id           TEXT NOT NULL,
    commit_sha          TEXT NOT NULL,
    issue_summary       TEXT NOT NULL,
    completeness        TEXT NOT NULL,
    findings            TEXT NOT NULL,
    missing_information TEXT NOT NULL
);

CREATE INDEX idx_inv_reports_commit ON inv_reports (commit_sha);
