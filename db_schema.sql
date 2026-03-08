-- Macro Economics Tracker
-- Production-oriented PostgreSQL schema
-- Target stack: PostgreSQL 16+, pgvector, pgcrypto, citext, pg_trgm
-- Focus: track-first monitoring, episode-centric UX, evidence-first verification

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS app;

-- -----------------------------------------------------------------------------
-- 1. Types
-- -----------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE app.source_type AS ENUM (
        'official',
        'newswire',
        'publisher',
        'research',
        'market_data',
        'internal'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.document_type AS ENUM (
        'news_article',
        'press_release',
        'speech',
        'transcript',
        'calendar_event',
        'research_note',
        'filing',
        'brief',
        'system_note',
        'market_reaction_note'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.entity_type AS ENUM (
        'country',
        'region',
        'organization',
        'person',
        'asset',
        'instrument',
        'currency',
        'commodity',
        'index',
        'theme',
        'metric',
        'policy_body',
        'location',
        'facility',
        'sector'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.track_mode AS ENUM (
        'scheduled_release',
        'policy_communication',
        'breaking_shock',
        'slow_burn_theme',
        'watchlist_exposure',
        'custom'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.track_state AS ENUM (
        'draft',
        'active',
        'paused',
        'archived'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.story_state AS ENUM (
        'emerging',
        'developing',
        'confirmed',
        'contested',
        'cooling',
        'closed'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.episode_type AS ENUM (
        'new_signal',
        'official_release',
        'speaker_comment',
        'media_wave',
        'market_reaction',
        'contradiction',
        'follow_up',
        'resolution',
        'digest'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.claim_support_status AS ENUM (
        'supported',
        'weak',
        'inferred',
        'contradicted',
        'unknown'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.relation_type AS ENUM (
        'same_as',
        'mentions',
        'affects',
        'causes',
        'corroborates',
        'contradicts',
        'belongs_to',
        'precedes',
        'follows',
        'exposes'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.notification_channel AS ENUM (
        'in_app',
        'email',
        'slack',
        'webhook'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.notification_reason AS ENUM (
        'story_created',
        'story_state_changed',
        'official_confirmation_added',
        'market_reaction_confirmed',
        'contradiction_increased',
        'track_priority_upgraded',
        'scheduled_event_soon',
        'scheduled_event_released',
        'daily_digest'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.job_status AS ENUM (
        'queued',
        'running',
        'completed',
        'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.assignment_method AS ENUM (
        'rule',
        'embedding',
        'llm',
        'manual'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE app.note_scope AS ENUM (
        'track',
        'story',
        'episode',
        'document',
        'evidence'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- -----------------------------------------------------------------------------
-- 2. Helper functions
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app.set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Multi-tenant core
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.users (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email               citext NOT NULL UNIQUE,
    display_name        text NOT NULL,
    avatar_url          text,
    timezone            text NOT NULL DEFAULT 'Asia/Singapore',
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.workspaces (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                text NOT NULL,
    slug                citext NOT NULL UNIQUE,
    created_by          uuid REFERENCES app.users(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.workspace_members (
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    user_id             uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    role                text NOT NULL DEFAULT 'member',
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- -----------------------------------------------------------------------------
-- 4. Sources & ingestion
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.sources (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key          citext NOT NULL UNIQUE,
    display_name        text NOT NULL,
    source_type         app.source_type NOT NULL,
    base_url            text,
    rss_url             text,
    default_language    text,
    trust_score         numeric(5,2) NOT NULL DEFAULT 0.50 CHECK (trust_score >= 0 AND trust_score <= 1),
    is_active           boolean NOT NULL DEFAULT true,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.ingestion_cursors (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           uuid NOT NULL REFERENCES app.sources(id) ON DELETE CASCADE,
    cursor_key          text NOT NULL,
    cursor_value        text,
    etag                text,
    last_published_at   timestamptz,
    last_success_at     timestamptz,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_id, cursor_key)
);

CREATE TABLE IF NOT EXISTS app.ingestion_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           uuid REFERENCES app.sources(id) ON DELETE SET NULL,
    status              app.job_status NOT NULL,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    discovered_count    integer NOT NULL DEFAULT 0,
    inserted_count      integer NOT NULL DEFAULT 0,
    updated_count       integer NOT NULL DEFAULT 0,
    failed_count        integer NOT NULL DEFAULT 0,
    error_text          text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS app.raw_documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           uuid NOT NULL REFERENCES app.sources(id) ON DELETE RESTRICT,
    ingestion_run_id    uuid REFERENCES app.ingestion_runs(id) ON DELETE SET NULL,
    external_id         text,
    url                 text NOT NULL,
    title_raw           text,
    body_raw            text,
    author_raw          text,
    published_at        timestamptz,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    language            text,
    content_hash        text NOT NULL,
    raw_payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, url),
    UNIQUE (source_id, external_id),
    UNIQUE (source_id, content_hash)
);

CREATE TABLE IF NOT EXISTS app.documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_url       text,
    canonical_url_hash  text,
    source_id           uuid NOT NULL REFERENCES app.sources(id) ON DELETE RESTRICT,
    primary_raw_document_id uuid REFERENCES app.raw_documents(id) ON DELETE SET NULL,
    document_type       app.document_type NOT NULL,
    title               text NOT NULL,
    subtitle            text,
    body_text           text,
    teaser_text         text,
    author_name         text,
    published_at        timestamptz,
    first_seen_at       timestamptz NOT NULL DEFAULT now(),
    language            text,
    source_priority     integer NOT NULL DEFAULT 100,
    dedup_hash          text NOT NULL UNIQUE,
    search_tsv          tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body_text, ''))
    ) STORED,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (canonical_url_hash)
);

CREATE TABLE IF NOT EXISTS app.document_chunks (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    chunk_index         integer NOT NULL,
    text                text NOT NULL,
    token_count         integer,
    char_start          integer,
    char_end            integer,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS app.document_embeddings (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         uuid REFERENCES app.documents(id) ON DELETE CASCADE,
    chunk_id            uuid REFERENCES app.document_chunks(id) ON DELETE CASCADE,
    embedding_model     text NOT NULL,
    embedding_version   text,
    embedding           vector(1536) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK ((document_id IS NOT NULL) OR (chunk_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS app.evidence_spans (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    chunk_id            uuid REFERENCES app.document_chunks(id) ON DELETE SET NULL,
    quote_text          text NOT NULL,
    char_start          integer,
    char_end            integer,
    sentence_start      integer,
    sentence_end        integer,
    page_number         integer,
    speaker             text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 5. Entities, aliases, relations
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.entities (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         app.entity_type NOT NULL,
    canonical_name      text NOT NULL,
    slug                citext NOT NULL UNIQUE,
    description         text,
    homepage_url        text,
    country_code        text,
    attributes          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, canonical_name)
);

CREATE TABLE IF NOT EXISTS app.entity_aliases (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    alias               text NOT NULL,
    normalized_alias    citext NOT NULL,
    language            text,
    is_primary          boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_id, normalized_alias),
    UNIQUE (normalized_alias, entity_id)
);

CREATE TABLE IF NOT EXISTS app.entity_relations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id    uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    target_entity_id    uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    relation_type       app.relation_type NOT NULL,
    confidence          numeric(5,2) NOT NULL DEFAULT 0.50 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_summary    text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_entity_id, target_entity_id, relation_type)
);

CREATE TABLE IF NOT EXISTS app.document_entities (
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    entity_id           uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    salience_score      numeric(5,2) NOT NULL DEFAULT 0.50 CHECK (salience_score >= 0 AND salience_score <= 1),
    mention_count       integer NOT NULL DEFAULT 1,
    sentiment_score     numeric(6,3),
    first_char_start    integer,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, entity_id)
);

-- -----------------------------------------------------------------------------
-- 6. Tracks (stateful monitoring objects)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.tracks (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    owner_user_id       uuid REFERENCES app.users(id) ON DELETE SET NULL,
    name                text NOT NULL,
    slug                citext NOT NULL,
    description         text,
    mode                app.track_mode NOT NULL,
    state               app.track_state NOT NULL DEFAULT 'draft',
    alert_policy        jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_policy     jsonb NOT NULL DEFAULT '{"strict": true}'::jsonb,
    memory_window_days  integer NOT NULL DEFAULT 30 CHECK (memory_window_days > 0),
    config              jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, slug)
);

CREATE TABLE IF NOT EXISTS app.track_entities (
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    entity_id           uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    role                text NOT NULL DEFAULT 'focus',
    weight              numeric(5,2) NOT NULL DEFAULT 1.00,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (track_id, entity_id, role)
);

CREATE TABLE IF NOT EXISTS app.track_filters (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    filter_type         text NOT NULL,
    filter_value        text NOT NULL,
    operator            text NOT NULL DEFAULT 'equals',
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (track_id, filter_type, filter_value, operator)
);

CREATE TABLE IF NOT EXISTS app.track_snapshots (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    snapshot_at         timestamptz NOT NULL DEFAULT now(),
    summary_text        text,
    summary_json        jsonb NOT NULL DEFAULT '{}'::jsonb,
    metrics_json        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by_agent    text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (track_id, snapshot_at)
);

CREATE TABLE IF NOT EXISTS app.user_track_preferences (
    user_id             uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    pinned_view         text,
    digest_mode         text,
    muted               boolean NOT NULL DEFAULT false,
    last_seen_at        timestamptz,
    view_state          jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (user_id, track_id)
);

-- -----------------------------------------------------------------------------
-- 7. Stories & episodes
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.stories (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    dominant_mode       app.track_mode NOT NULL DEFAULT 'custom',
    title               text NOT NULL,
    slug                citext NOT NULL,
    summary_text        text,
    summary_json        jsonb NOT NULL DEFAULT '{}'::jsonb,
    story_state         app.story_state NOT NULL DEFAULT 'emerging',
    first_seen_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at        timestamptz NOT NULL DEFAULT now(),
    state_changed_at    timestamptz NOT NULL DEFAULT now(),
    hotness_score       numeric(6,3) NOT NULL DEFAULT 0,
    novelty_score       numeric(6,3) NOT NULL DEFAULT 0,
    contradiction_score numeric(6,3) NOT NULL DEFAULT 0,
    confidence_score    numeric(6,3) NOT NULL DEFAULT 0,
    source_diversity_score numeric(6,3) NOT NULL DEFAULT 0,
    official_confirmation_at timestamptz,
    market_reaction_at  timestamptz,
    story_embedding     vector(1536),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, slug)
);

CREATE TABLE IF NOT EXISTS app.story_entities (
    story_id            uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    entity_id           uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    role                text NOT NULL DEFAULT 'mentioned',
    salience_score      numeric(5,2) NOT NULL DEFAULT 0.50 CHECK (salience_score >= 0 AND salience_score <= 1),
    first_seen_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (story_id, entity_id, role)
);

CREATE TABLE IF NOT EXISTS app.story_documents (
    story_id            uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    assignment_score    numeric(6,3) NOT NULL DEFAULT 0,
    assignment_method   app.assignment_method NOT NULL,
    is_primary          boolean NOT NULL DEFAULT false,
    assigned_at         timestamptz NOT NULL DEFAULT now(),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (story_id, document_id)
);

CREATE TABLE IF NOT EXISTS app.story_links (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_story_id     uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    target_story_id     uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    relation_type       app.relation_type NOT NULL,
    confidence          numeric(5,2) NOT NULL DEFAULT 0.50 CHECK (confidence >= 0 AND confidence <= 1),
    evidence_summary    text,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_story_id, target_story_id, relation_type)
);

CREATE TABLE IF NOT EXISTS app.track_stories (
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    story_id            uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    relevance_score     numeric(6,3) NOT NULL DEFAULT 0,
    priority_score      numeric(6,3) NOT NULL DEFAULT 0,
    reason              text,
    added_at            timestamptz NOT NULL DEFAULT now(),
    removed_at          timestamptz,
    PRIMARY KEY (track_id, story_id)
);

CREATE TABLE IF NOT EXISTS app.episodes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id            uuid NOT NULL REFERENCES app.stories(id) ON DELETE CASCADE,
    episode_type        app.episode_type NOT NULL,
    headline            text NOT NULL,
    state_from          text,
    state_to            text,
    what_changed        text,
    why_it_matters      text,
    what_to_watch       text,
    significance_score  numeric(6,3) NOT NULL DEFAULT 0,
    confidence_score    numeric(6,3) NOT NULL DEFAULT 0,
    contradiction_score numeric(6,3) NOT NULL DEFAULT 0,
    started_at          timestamptz NOT NULL DEFAULT now(),
    ended_at            timestamptz,
    created_by_agent    text,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.episode_documents (
    episode_id          uuid NOT NULL REFERENCES app.episodes(id) ON DELETE CASCADE,
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    role                text NOT NULL DEFAULT 'supporting',
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, document_id, role)
);

-- -----------------------------------------------------------------------------
-- 8. Events, claims, evidence lineage
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.events (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         uuid NOT NULL REFERENCES app.documents(id) ON DELETE CASCADE,
    story_id            uuid REFERENCES app.stories(id) ON DELETE SET NULL,
    event_type          text NOT NULL,
    actor_entity_id     uuid REFERENCES app.entities(id) ON DELETE SET NULL,
    action_verb         text NOT NULL,
    object_entity_id    uuid REFERENCES app.entities(id) ON DELETE SET NULL,
    object_text         text,
    location_entity_id  uuid REFERENCES app.entities(id) ON DELETE SET NULL,
    event_time_start    timestamptz,
    event_time_end      timestamptz,
    polarity            text,
    confidence_score    numeric(6,3) NOT NULL DEFAULT 0,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.event_evidence (
    event_id            uuid NOT NULL REFERENCES app.events(id) ON DELETE CASCADE,
    evidence_span_id    uuid NOT NULL REFERENCES app.evidence_spans(id) ON DELETE CASCADE,
    support_status      app.claim_support_status NOT NULL DEFAULT 'supported',
    score               numeric(6,3) NOT NULL DEFAULT 0,
    PRIMARY KEY (event_id, evidence_span_id)
);

CREATE TABLE IF NOT EXISTS app.claims (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id            uuid REFERENCES app.stories(id) ON DELETE SET NULL,
    episode_id          uuid REFERENCES app.episodes(id) ON DELETE SET NULL,
    document_id         uuid REFERENCES app.documents(id) ON DELETE SET NULL,
    subject_entity_id   uuid REFERENCES app.entities(id) ON DELETE SET NULL,
    predicate           text NOT NULL,
    object_entity_id    uuid REFERENCES app.entities(id) ON DELETE SET NULL,
    object_text         text,
    claim_text          text NOT NULL,
    support_status      app.claim_support_status NOT NULL DEFAULT 'unknown',
    confidence_score    numeric(6,3) NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.claim_evidence (
    claim_id            uuid NOT NULL REFERENCES app.claims(id) ON DELETE CASCADE,
    evidence_span_id    uuid NOT NULL REFERENCES app.evidence_spans(id) ON DELETE CASCADE,
    support_status      app.claim_support_status NOT NULL,
    score               numeric(6,3) NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, evidence_span_id)
);

CREATE TABLE IF NOT EXISTS app.generated_sentences (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id            uuid REFERENCES app.stories(id) ON DELETE CASCADE,
    episode_id          uuid REFERENCES app.episodes(id) ON DELETE CASCADE,
    sentence_order      integer NOT NULL,
    sentence_text       text NOT NULL,
    verdict             app.claim_support_status NOT NULL DEFAULT 'unknown',
    model_name          text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (episode_id, sentence_order)
);

CREATE TABLE IF NOT EXISTS app.generated_sentence_evidence (
    generated_sentence_id uuid NOT NULL REFERENCES app.generated_sentences(id) ON DELETE CASCADE,
    evidence_span_id      uuid NOT NULL REFERENCES app.evidence_spans(id) ON DELETE CASCADE,
    support_status        app.claim_support_status NOT NULL,
    PRIMARY KEY (generated_sentence_id, evidence_span_id)
);

-- -----------------------------------------------------------------------------
-- 9. Notes, annotations, watchlists, market reactions
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.notes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    author_user_id      uuid REFERENCES app.users(id) ON DELETE SET NULL,
    scope               app.note_scope NOT NULL,
    track_id            uuid REFERENCES app.tracks(id) ON DELETE CASCADE,
    story_id            uuid REFERENCES app.stories(id) ON DELETE CASCADE,
    episode_id          uuid REFERENCES app.episodes(id) ON DELETE CASCADE,
    document_id         uuid REFERENCES app.documents(id) ON DELETE CASCADE,
    evidence_span_id    uuid REFERENCES app.evidence_spans(id) ON DELETE CASCADE,
    body_md             text NOT NULL,
    pinned              boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.watchlist_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id            uuid NOT NULL REFERENCES app.tracks(id) ON DELETE CASCADE,
    entity_id           uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    label               text,
    weight              numeric(8,4),
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (track_id, entity_id)
);

CREATE TABLE IF NOT EXISTS app.market_reactions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id            uuid REFERENCES app.stories(id) ON DELETE CASCADE,
    episode_id          uuid REFERENCES app.episodes(id) ON DELETE CASCADE,
    instrument_entity_id uuid NOT NULL REFERENCES app.entities(id) ON DELETE CASCADE,
    metric_name         text NOT NULL,
    direction           text,
    value_numeric       numeric(18,6),
    unit                text,
    observed_at         timestamptz NOT NULL,
    source_id           uuid REFERENCES app.sources(id) ON DELETE SET NULL,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 10. Alerts, inbox, event outbox
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.notifications (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    user_id             uuid REFERENCES app.users(id) ON DELETE CASCADE,
    track_id            uuid REFERENCES app.tracks(id) ON DELETE CASCADE,
    story_id            uuid REFERENCES app.stories(id) ON DELETE CASCADE,
    episode_id          uuid REFERENCES app.episodes(id) ON DELETE CASCADE,
    reason              app.notification_reason NOT NULL,
    channel             app.notification_channel NOT NULL,
    dedup_key           text NOT NULL,
    title               text NOT NULL,
    body_text           text,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    scheduled_for       timestamptz,
    sent_at             timestamptz,
    read_at             timestamptz,
    UNIQUE (channel, dedup_key)
);

CREATE TABLE IF NOT EXISTS app.event_outbox (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    event_type          text NOT NULL,
    aggregate_type      text NOT NULL,
    aggregate_id        uuid NOT NULL,
    payload             jsonb NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    delivered_at        timestamptz
);

-- -----------------------------------------------------------------------------
-- 11. Agent runs, jobs, audit log
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app.pipeline_jobs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type            text NOT NULL,
    status              app.job_status NOT NULL,
    priority            integer NOT NULL DEFAULT 100,
    source_object_type  text,
    source_object_id    uuid,
    input_json          jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_json         jsonb,
    error_text          text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    finished_at         timestamptz
);

CREATE TABLE IF NOT EXISTS app.agent_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name          text NOT NULL,
    model_name          text,
    status              app.job_status NOT NULL,
    input_json          jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_json         jsonb,
    cost_estimate_usd   numeric(12,6),
    latency_ms          integer,
    source_object_type  text,
    source_object_id    uuid,
    created_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    error_text          text
);

CREATE TABLE IF NOT EXISTS app.audit_log (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id       uuid REFERENCES app.users(id) ON DELETE SET NULL,
    action              text NOT NULL,
    target_type         text NOT NULL,
    target_id           uuid,
    before_json         jsonb,
    after_json          jsonb,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 12. Views for UX read-models
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW app.v_story_latest_episode AS
SELECT
    s.id AS story_id,
    s.workspace_id,
    s.title AS story_title,
    s.story_state,
    s.hotness_score,
    s.novelty_score,
    s.contradiction_score,
    s.confidence_score,
    s.source_diversity_score,
    e.id AS latest_episode_id,
    e.episode_type,
    e.headline,
    e.what_changed,
    e.why_it_matters,
    e.what_to_watch,
    e.significance_score,
    e.created_at AS episode_created_at
FROM app.stories s
LEFT JOIN LATERAL (
    SELECT e1.*
    FROM app.episodes e1
    WHERE e1.story_id = s.id
    ORDER BY e1.created_at DESC
    LIMIT 1
) e ON true;

CREATE OR REPLACE VIEW app.v_track_live_board AS
SELECT
    ts.track_id,
    t.workspace_id,
    t.name AS track_name,
    t.mode,
    ts.story_id,
    s.title AS story_title,
    ts.relevance_score,
    ts.priority_score,
    s.story_state,
    s.hotness_score,
    s.contradiction_score,
    s.confidence_score,
    s.last_seen_at,
    le.latest_episode_id,
    le.episode_type,
    le.headline,
    le.what_changed,
    le.why_it_matters,
    le.what_to_watch,
    le.episode_created_at
FROM app.track_stories ts
JOIN app.tracks t ON t.id = ts.track_id
JOIN app.stories s ON s.id = ts.story_id
LEFT JOIN app.v_story_latest_episode le ON le.story_id = s.id
WHERE ts.removed_at IS NULL;

-- -----------------------------------------------------------------------------
-- 13. Indexes
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_users_updated_at ON app.users(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON app.workspace_members(user_id);

CREATE INDEX IF NOT EXISTS idx_sources_active ON app.sources(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_started ON app.ingestion_runs(source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_documents_published_at ON app.raw_documents(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_documents_url_trgm ON app.raw_documents USING gin (url gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_documents_published_at ON app.documents(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_source_published_at ON app.documents(source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_type_published_at ON app.documents(document_type, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_search_tsv ON app.documents USING gin (search_tsv);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin ON app.documents USING gin (metadata);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON app.document_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_evidence_document_id ON app.evidence_spans(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_document_id ON app.document_embeddings(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_chunk_id ON app.document_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_hnsw ON app.document_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_entities_type_name ON app.entities(entity_type, canonical_name);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized ON app.entity_aliases(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_entity_rel_source ON app.entity_relations(source_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_document_entities_entity ON app.document_entities(entity_id);

CREATE INDEX IF NOT EXISTS idx_tracks_workspace_state ON app.tracks(workspace_id, state, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_entities_entity ON app.track_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_track_snapshots_track_time ON app.track_snapshots(track_id, snapshot_at DESC);

CREATE INDEX IF NOT EXISTS idx_stories_workspace_last_seen ON app.stories(workspace_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_stories_state ON app.stories(story_state, state_changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_stories_hotness ON app.stories(hotness_score DESC, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_stories_embedding_hnsw ON app.stories USING hnsw (story_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_story_documents_document ON app.story_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_track_stories_track_priority ON app.track_stories(track_id, priority_score DESC, added_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_stories_story ON app.track_stories(story_id);

CREATE INDEX IF NOT EXISTS idx_episodes_story_created ON app.episodes(story_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_type_created ON app.episodes(episode_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_episode_documents_doc ON app.episode_documents(document_id);

CREATE INDEX IF NOT EXISTS idx_events_story_id ON app.events(story_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_story_episode ON app.claims(story_id, episode_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generated_sentences_episode ON app.generated_sentences(episode_id, sentence_order);

CREATE INDEX IF NOT EXISTS idx_notes_track_story ON app.notes(track_id, story_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_reactions_story_time ON app.market_reactions(story_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON app.notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON app.notifications(user_id, read_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_outbox_undelivered ON app.event_outbox(delivered_at) WHERE delivered_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status_priority ON app.pipeline_jobs(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_runs_source_object ON app.agent_runs(source_object_type, source_object_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON app.audit_log(target_type, target_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- 14. Triggers
-- -----------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_users_updated_at ON app.users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON app.users
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_workspaces_updated_at ON app.workspaces;
CREATE TRIGGER trg_workspaces_updated_at
BEFORE UPDATE ON app.workspaces
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_sources_updated_at ON app.sources;
CREATE TRIGGER trg_sources_updated_at
BEFORE UPDATE ON app.sources
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_documents_updated_at ON app.documents;
CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON app.documents
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_entities_updated_at ON app.entities;
CREATE TRIGGER trg_entities_updated_at
BEFORE UPDATE ON app.entities
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_tracks_updated_at ON app.tracks;
CREATE TRIGGER trg_tracks_updated_at
BEFORE UPDATE ON app.tracks
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_stories_updated_at ON app.stories;
CREATE TRIGGER trg_stories_updated_at
BEFORE UPDATE ON app.stories
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_episodes_updated_at ON app.episodes;
CREATE TRIGGER trg_episodes_updated_at
BEFORE UPDATE ON app.episodes
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS trg_notes_updated_at ON app.notes;
CREATE TRIGGER trg_notes_updated_at
BEFORE UPDATE ON app.notes
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- -----------------------------------------------------------------------------
-- 15. Recommended operational notes
-- -----------------------------------------------------------------------------
-- 1) Keep ingestion idempotent with source/url/content_hash constraints.
-- 2) Partition raw_documents and documents by published_at once data volume grows.
-- 3) Use pgvector HNSW for candidate retrieval; exact verification still happens in SQL/LLM.
-- 4) Secrets for APIs should live outside the DB.
-- 5) For production auth, add RLS policies by workspace.
-- 6) Use app.event_outbox to fan out SSE notifications reliably.
-- 7) Keep all agent inputs/outputs as typed JSON and store them in app.agent_runs.

COMMIT;
