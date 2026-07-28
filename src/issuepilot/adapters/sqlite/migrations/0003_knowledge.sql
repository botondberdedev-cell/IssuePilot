-- Knowledge context tables (knw_ prefix; this context owns them).
CREATE TABLE knw_chunks (
    chunk_id     TEXT PRIMARY KEY,
    commit_sha   TEXT NOT NULL,
    path         TEXT NOT NULL,
    start_line   INTEGER NOT NULL,
    end_line     INTEGER NOT NULL,
    text         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    symbol       TEXT,
    language     TEXT
);

CREATE INDEX idx_knw_chunks_commit ON knw_chunks (commit_sha);
CREATE INDEX idx_knw_chunks_path ON knw_chunks (commit_sha, path);

-- Lexical search. Contentless-adjacent design: the chunk row is the source of
-- truth and the FTS table carries only what must be searchable. Identifiers in
-- code are frequently snake_case or dotted, so the tokenizer keeps '_' as part
-- of a token and splits on the rest.
CREATE VIRTUAL TABLE knw_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    commit_sha UNINDEXED,
    text,
    symbol,
    path,
    tokenize = "unicode61 tokenchars '_'"
);

CREATE INDEX idx_knw_chunks_hash ON knw_chunks (content_hash);
