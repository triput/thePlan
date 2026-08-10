-- 001_baseline.sql
-- thePlan — PostgreSQL baseline schema
-- Apply via: psql -f 001_baseline.sql
-- Alembic migrations should reproduce this baseline.

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- ENUM types
-- ---------------------------------------------------------------------------
CREATE TYPE task_priority AS ENUM ('p1', 'p2', 'p3', 'p4');

CREATE TYPE schedule_status AS ENUM (
    'unscheduled',
    'scheduled',
    'pinned',
    'completed',
    'cancelled',
    'overbooked'
);

CREATE TYPE calendar_provider AS ENUM ('google', 'microsoft');

CREATE TYPE reminder_channel AS ENUM ('in_app', 'browser');

-- ---------------------------------------------------------------------------
-- Users & settings
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255),          -- nullable for local-only MVP / Access-only
    display_name    VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_settings (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id                    UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    timezone                    VARCHAR(64) NOT NULL DEFAULT 'UTC',
    locale                      VARCHAR(16) NOT NULL DEFAULT 'en-US',
    workday_minutes             INT NOT NULL DEFAULT 480 CHECK (workday_minutes > 0),
    workweek_days               INT NOT NULL DEFAULT 5 CHECK (workweek_days BETWEEN 1 AND 7),
    inter_block_buffer_minutes  INT NOT NULL DEFAULT 5 CHECK (inter_block_buffer_minutes >= 0),
    ups_weights                 JSONB NOT NULL DEFAULT '{"Wp": 0.35, "Wu": 0.40, "Wd": 0.15, "We": 0.10, "k": 0.5}'::jsonb,
    upcoming_horizon_days       INT NOT NULL DEFAULT 7 CHECK (upcoming_horizon_days > 0),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Hierarchy: epics, projects, sections
-- ---------------------------------------------------------------------------
CREATE TABLE epics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    color_hex       VARCHAR(7) NOT NULL DEFAULT '#6D3FC9',  -- violet (Synesis amethyst)
    start_date      DATE,
    target_date     DATE,
    sort_order      INT NOT NULL DEFAULT 0,
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    epic_id         UUID REFERENCES epics(id) ON DELETE SET NULL,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    color_hex       VARCHAR(7) NOT NULL DEFAULT '#0A8558',  -- emerald (Synesis/Phronesis)
    sort_order      INT NOT NULL DEFAULT 0,
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Focus windows (Time Maps) — used W2; table present from baseline
-- ---------------------------------------------------------------------------
CREATE TABLE focus_windows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    start_time      TIME NOT NULL,         -- local time
    end_time        TIME NOT NULL,
    days_of_week    SMALLINT NOT NULL DEFAULT 31,  -- bitset Mon=1,Tue=2,...,Sun=64; 31 = Mon-Fri
    is_hard         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT focus_window_time_order CHECK (end_time > start_time)
);

-- ---------------------------------------------------------------------------
-- Tasks
-- ---------------------------------------------------------------------------
CREATE TABLE tasks (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id                    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id                  UUID REFERENCES projects(id) ON DELETE CASCADE,
    section_id                  UUID REFERENCES sections(id) ON DELETE SET NULL,
    parent_task_id              UUID REFERENCES tasks(id) ON DELETE CASCADE,

    title                       VARCHAR(500) NOT NULL,
    description                 TEXT,
    priority                    task_priority NOT NULL DEFAULT 'p4',

    nesting_level               INT NOT NULL DEFAULT 0 CHECK (nesting_level BETWEEN 0 AND 2),
    sort_order                  INT NOT NULL DEFAULT 0,

    estimated_duration_minutes  INT NOT NULL DEFAULT 30 CHECK (estimated_duration_minutes > 0),
    min_block_duration_minutes  INT NOT NULL DEFAULT 15 CHECK (min_block_duration_minutes > 0),
    max_block_duration_minutes  INT NOT NULL DEFAULT 120 CHECK (max_block_duration_minutes >= min_block_duration_minutes),

    due_at                      TIMESTAMPTZ,
    deadline_at                 TIMESTAMPTZ,       -- hard commit; UI W2
    soft_target_at              TIMESTAMPTZ,       -- Plan-bound soft target; UI W2

    preferred_time_window_id    UUID REFERENCES focus_windows(id) ON DELETE SET NULL,

    status                      schedule_status NOT NULL DEFAULT 'unscheduled',
    is_completed                BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at                TIMESTAMPTZ,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT task_section_project_consistency CHECK (
        section_id IS NULL OR project_id IS NOT NULL
    )
);

-- ---------------------------------------------------------------------------
-- Labels
-- ---------------------------------------------------------------------------
CREATE TABLE labels (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    color_hex       VARCHAR(7) NOT NULL DEFAULT '#635F75',  -- charcoal (Synesis muted)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT labels_owner_name_unique UNIQUE (owner_id, name),
    CONSTRAINT labels_name_lowercase CHECK (name = lower(name)),
    CONSTRAINT labels_name_nonempty CHECK (length(trim(name)) > 0)
);

CREATE TABLE task_labels (
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    label_id        UUID NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, label_id)
);

-- ---------------------------------------------------------------------------
-- Task dependencies
-- ---------------------------------------------------------------------------
CREATE TABLE task_dependencies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocking_task_id    UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependent_task_id   UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_dependency UNIQUE (blocking_task_id, dependent_task_id),
    CONSTRAINT no_self_dependency CHECK (blocking_task_id <> dependent_task_id)
);

-- ---------------------------------------------------------------------------
-- Scheduled blocks
-- ---------------------------------------------------------------------------
CREATE TABLE scheduled_blocks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    is_pinned       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT scheduled_block_time_order CHECK (end_time > start_time)
);

-- ---------------------------------------------------------------------------
-- Recurrence (stub — engine W1.5)
-- ---------------------------------------------------------------------------
CREATE TABLE recurrence_rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         UUID NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
    rrule           TEXT NOT NULL,               -- iCal RRULE string or equivalent
    is_fixed        BOOLEAN NOT NULL DEFAULT FALSE, -- every! semantics
    timezone        VARCHAR(64) NOT NULL DEFAULT 'UTC',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Reminders (stub — engine W1.5)
-- ---------------------------------------------------------------------------
CREATE TABLE reminders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    fire_at         TIMESTAMPTZ NOT NULL,
    channel         reminder_channel NOT NULL DEFAULT 'in_app',
    is_fired        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Saved filters / smart views
-- ---------------------------------------------------------------------------
CREATE TABLE saved_filters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    predicate_json  JSONB NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT saved_filters_owner_slug_unique UNIQUE (owner_id, slug)
);

-- ---------------------------------------------------------------------------
-- Calendar accounts & external events (W2 sync)
-- ---------------------------------------------------------------------------
CREATE TABLE calendar_accounts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            calendar_provider NOT NULL,
    account_email       VARCHAR(255),
    access_token_enc    TEXT,
    refresh_token_enc   TEXT,
    token_expires_at    TIMESTAMPTZ,
    sync_cursor         TEXT,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT calendar_accounts_owner_provider_unique UNIQUE (owner_id, provider, account_email)
);

CREATE TABLE external_calendar_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calendar_account_id UUID NOT NULL REFERENCES calendar_accounts(id) ON DELETE CASCADE,
    task_id             UUID REFERENCES tasks(id) ON DELETE SET NULL,
    scheduled_block_id  UUID REFERENCES scheduled_blocks(id) ON DELETE SET NULL,
    provider            calendar_provider NOT NULL,
    external_event_id   VARCHAR(255) NOT NULL,
    calendar_id         VARCHAR(255) NOT NULL,
    title               VARCHAR(500),
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    is_all_day          BOOLEAN NOT NULL DEFAULT FALSE,
    sync_hash           VARCHAR(64),
    last_synced_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_external_event UNIQUE (provider, external_event_id)
);

-- ---------------------------------------------------------------------------
-- Schedule runs (W2 worker audit)
-- ---------------------------------------------------------------------------
CREATE TABLE schedule_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(32) NOT NULL DEFAULT 'running',
    tasks_scheduled INT NOT NULL DEFAULT 0,
    blocks_created  INT NOT NULL DEFAULT 0,
    overbooked_count INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    stats_json      JSONB
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_epics_owner ON epics(owner_id);
CREATE INDEX idx_epics_owner_archived ON epics(owner_id, is_archived);

CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_epic ON projects(epic_id);
CREATE INDEX idx_projects_owner_archived ON projects(owner_id, is_archived);

CREATE INDEX idx_sections_project ON sections(project_id);
CREATE INDEX idx_sections_owner ON sections(owner_id);

CREATE INDEX idx_tasks_owner ON tasks(owner_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_section ON tasks(section_id);
CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);
CREATE INDEX idx_tasks_nesting ON tasks(nesting_level);
CREATE INDEX idx_tasks_owner_due_at ON tasks(owner_id, due_at);
CREATE INDEX idx_tasks_owner_deadline_at ON tasks(owner_id, deadline_at);
CREATE INDEX idx_tasks_owner_is_completed ON tasks(owner_id, is_completed);
CREATE INDEX idx_tasks_owner_project_sort ON tasks(owner_id, project_id, sort_order);

CREATE INDEX idx_labels_owner ON labels(owner_id);

CREATE INDEX idx_task_labels_label ON task_labels(label_id);
CREATE INDEX idx_task_labels_task ON task_labels(task_id);

CREATE INDEX idx_task_dependencies_blocking ON task_dependencies(blocking_task_id);
CREATE INDEX idx_task_dependencies_dependent ON task_dependencies(dependent_task_id);

CREATE INDEX idx_scheduled_blocks_task ON scheduled_blocks(task_id);
CREATE INDEX idx_scheduled_blocks_owner ON scheduled_blocks(owner_id);
CREATE INDEX idx_scheduled_blocks_time ON scheduled_blocks(start_time, end_time);
CREATE INDEX idx_scheduled_blocks_owner_time ON scheduled_blocks(owner_id, start_time, end_time);

CREATE INDEX idx_reminders_task ON reminders(task_id);
CREATE INDEX idx_reminders_fire_at ON reminders(owner_id, fire_at) WHERE is_fired = FALSE;

CREATE INDEX idx_saved_filters_owner ON saved_filters(owner_id);

CREATE INDEX idx_external_events_account ON external_calendar_events(calendar_account_id);
CREATE INDEX idx_external_events_time ON external_calendar_events(start_time, end_time);

CREATE INDEX idx_schedule_runs_owner ON schedule_runs(owner_id, started_at DESC);

-- ---------------------------------------------------------------------------
-- Seed: bootstrap user, settings, system smart views
-- (Run after first user creation in app bootstrap; included here for reference)
-- ---------------------------------------------------------------------------

-- Example seed (commented — application bootstrap should insert actual owner_id):
--
-- INSERT INTO users (id, email, display_name) VALUES
--   ('00000000-0000-0000-0000-000000000001', 'local@localhost', 'Local User');
--
-- INSERT INTO user_settings (owner_id) VALUES
--   ('00000000-0000-0000-0000-000000000001');
--
-- INSERT INTO saved_filters (owner_id, name, slug, predicate_json, is_system, sort_order) VALUES
--   ('00000000-0000-0000-0000-000000000001', 'Inbox', 'inbox',
--    '{"op":"and","clauses":[{"field":"project_id","op":"is_null"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
--    TRUE, 1),
--   ('00000000-0000-0000-0000-000000000001', 'Today', 'today',
--    '{"op":"and","clauses":[{"field":"due_at","op":"is_today"},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
--    TRUE, 2),
--   ('00000000-0000-0000-0000-000000000001', 'Upcoming', 'upcoming',
--    '{"op":"and","clauses":[{"field":"due_at","op":"within_days","value":7},{"field":"is_completed","op":"eq","value":false}]}'::jsonb,
--    TRUE, 3);

COMMIT;
