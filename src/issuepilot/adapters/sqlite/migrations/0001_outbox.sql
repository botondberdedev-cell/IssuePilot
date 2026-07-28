-- Outbox for domain events: every published event is recorded here, in the
-- same transaction as the publishing context's state change when one is open.
CREATE TABLE outbox_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    occurred_at  TEXT NOT NULL,
    payload      TEXT NOT NULL
);

CREATE INDEX idx_outbox_events_occurred_at ON outbox_events (occurred_at);
CREATE INDEX idx_outbox_events_aggregate ON outbox_events (aggregate_id);
