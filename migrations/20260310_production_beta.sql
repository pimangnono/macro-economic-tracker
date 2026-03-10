ALTER TABLE app.users
    ADD COLUMN IF NOT EXISTS password_hash text,
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS last_login_at timestamptz,
    ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;

CREATE TABLE IF NOT EXISTS app.workspace_invites (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
    email               citext NOT NULL,
    role                text NOT NULL DEFAULT 'viewer',
    invite_token        text NOT NULL UNIQUE,
    invited_by_user_id  uuid REFERENCES app.users(id) ON DELETE SET NULL,
    accepted_by_user_id uuid REFERENCES app.users(id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    accepted_at         timestamptz,
    metadata            jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_workspace_invites_workspace_email
    ON app.workspace_invites (workspace_id, email, accepted_at);

CREATE TABLE IF NOT EXISTS app.user_sessions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    token_hash          text NOT NULL UNIQUE,
    user_agent          text,
    ip_address          text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_active
    ON app.user_sessions (user_id, expires_at DESC)
    WHERE revoked_at IS NULL;

ALTER TABLE app.track_snapshots
    ADD COLUMN IF NOT EXISTS artifact_manifest jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE app.pipeline_jobs
    ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_retries integer NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS available_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_available
    ON app.pipeline_jobs (status, available_at, priority, created_at);
