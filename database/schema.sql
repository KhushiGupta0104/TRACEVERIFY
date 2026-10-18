-- TRACEVERIFY evidence store — baseline schema (migration version 1).
-- Idempotent: safe to run repeatedly. Applied by backend/scripts/init_db.py.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Normalized evidence events (one row per parsed source record)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id             BIGSERIAL PRIMARY KEY,
    ts             BIGINT      NOT NULL,              -- LANL relative time (seconds)
    source_type    VARCHAR(16) NOT NULL,              -- auth | proc | dns | flow | redteam
    event_type     VARCHAR(32) NOT NULL,              -- normalized type, e.g. AUTH_LOGON
    user_name      VARCHAR(128),                      -- primary user (auth srcUser, proc user, redteam user)
    src_computer   VARCHAR(64),                       -- origin host (auth/flow/dns src, proc computer)
    dst_computer   VARCHAR(64),                       -- destination host (auth dst, flow dst, dns resolved)
    attributes     JSONB       NOT NULL DEFAULT '{}', -- source-specific fields
    raw_line       TEXT        NOT NULL,
    source_file    VARCHAR(255) NOT NULL,
    line_no        INTEGER     NOT NULL,
    dataset_label  VARCHAR(80) NOT NULL,              -- provenance label shown in the UI
    dedup_key      CHAR(40)    NOT NULL,              -- makes ingestion idempotent
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_events_dedup UNIQUE (dedup_key),
    CONSTRAINT ck_events_source CHECK (source_type IN ('auth','proc','dns','flow','redteam'))
);
CREATE INDEX IF NOT EXISTS ix_events_ts          ON events (ts);
CREATE INDEX IF NOT EXISTS ix_events_source_ts   ON events (source_type, ts);
CREATE INDEX IF NOT EXISTS ix_events_user        ON events (user_name);
CREATE INDEX IF NOT EXISTS ix_events_src         ON events (src_computer);
CREATE INDEX IF NOT EXISTS ix_events_dst         ON events (dst_computer);

-- ---------------------------------------------------------------------------
-- Investigative entities (users, computers, process names)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entities (
    id            BIGSERIAL PRIMARY KEY,
    entity_type   VARCHAR(16)  NOT NULL,             -- user | computer | process
    value         VARCHAR(128) NOT NULL,
    correlatable  BOOLEAN      NOT NULL DEFAULT TRUE, -- false: machine accounts, anonymous, process names
    CONSTRAINT uq_entities_type_value UNIQUE (entity_type, value),
    CONSTRAINT ck_entities_type CHECK (entity_type IN ('user','computer','process'))
);

CREATE TABLE IF NOT EXISTS event_entities (
    event_id   BIGINT      NOT NULL REFERENCES events(id)   ON DELETE CASCADE,
    entity_id  BIGINT      NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role       VARCHAR(24) NOT NULL,                 -- src_user | dst_user | user | src_computer | ...
    PRIMARY KEY (event_id, entity_id, role)
);
CREATE INDEX IF NOT EXISTS ix_event_entities_entity ON event_entities (entity_id, event_id);

-- ---------------------------------------------------------------------------
-- Correlation rule registry (conditions implemented in backend/app/rules)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS correlation_rules (
    code           VARCHAR(8)   PRIMARY KEY,         -- e.g. R03
    name           VARCHAR(120) NOT NULL,
    from_types     TEXT[]       NOT NULL,
    to_types       TEXT[]       NOT NULL,
    condition_text TEXT         NOT NULL,
    full_score     NUMERIC(4,3) NOT NULL,
    partial_score  NUMERIC(4,3) NOT NULL,
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_rule_scores CHECK (full_score BETWEEN 0 AND 1 AND partial_score BETWEEN 0 AND 1)
);

-- ---------------------------------------------------------------------------
-- Investigations and their evidence relationships
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investigations (
    id             BIGSERIAL PRIMARY KEY,
    seed_event_id  BIGINT      NOT NULL REFERENCES events(id),
    status         VARCHAR(16) NOT NULL DEFAULT 'completed',
    params         JSONB       NOT NULL,
    metrics        JSONB       NOT NULL DEFAULT '{}',
    run_count      INTEGER     NOT NULL DEFAULT 1,
    error          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_investigation_status CHECK (status IN ('completed','failed'))
);
CREATE INDEX IF NOT EXISTS ix_investigations_seed ON investigations (seed_event_id);

CREATE TABLE IF NOT EXISTS relationships (
    id                  BIGSERIAL PRIMARY KEY,
    investigation_id    BIGINT       NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    source_event_id     BIGINT       NOT NULL REFERENCES events(id),
    target_event_id     BIGINT       NOT NULL REFERENCES events(id),
    status              VARCHAR(10)  NOT NULL,       -- accepted | rejected
    is_primary          BOOLEAN      NOT NULL,       -- primary edge defines the target's path to the seed
    hop                 INTEGER      NOT NULL,       -- 1 = direct seed relationship, >1 = multi-hop
    direction           VARCHAR(10)  NOT NULL,       -- forward (target after source) | backward
    time_delta_seconds  BIGINT       NOT NULL,       -- target.ts - source.ts
    shared_entities     JSONB        NOT NULL,
    entity_score        NUMERIC(5,4) NOT NULL,
    temporal_score      NUMERIC(5,4) NOT NULL,
    rule_score          NUMERIC(5,4) NOT NULL,
    final_score         NUMERIC(5,4) NOT NULL,
    matched_rule_code   VARCHAR(8)   REFERENCES correlation_rules(code),
    rule_match          VARCHAR(8),                  -- full | partial | NULL
    explanation         TEXT         NOT NULL,
    CONSTRAINT uq_relationship_edge UNIQUE (investigation_id, source_event_id, target_event_id),
    CONSTRAINT ck_relationship_no_self CHECK (source_event_id <> target_event_id),
    CONSTRAINT ck_relationship_status CHECK (status IN ('accepted','rejected')),
    CONSTRAINT ck_relationship_scores CHECK (
        entity_score   BETWEEN 0 AND 1 AND temporal_score BETWEEN 0 AND 1 AND
        rule_score     BETWEEN 0 AND 1 AND final_score    BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS ix_relationships_investigation ON relationships (investigation_id, status);
CREATE INDEX IF NOT EXISTS ix_relationships_target        ON relationships (target_event_id);

INSERT INTO schema_migrations (version, name) VALUES (1, 'baseline schema')
ON CONFLICT (version) DO NOTHING;
