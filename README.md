# Macro Economic Tracker

Production-oriented scaffold for the Track-first macro intelligence platform described in:

- `macro_economics_tracker_prd.md`
- `tracking_ux_wireframes.md`
- `db_schema.sql`

## Included

- `apps/api`: FastAPI service with health checks, track/story APIs, and SSE outbox streaming
- `apps/web`: Next.js app for Home / Inbox, Track detail, Story detail, and Track creation
- `docker-compose.yml`: local Postgres, Redis, API, and Web containers
- `db_schema.sql`: source-of-truth schema used by the migration runner
- `Makefile`: shortcuts for migrate / seed / test / lint

## Quick Start

1. Copy `.env.example` to `.env`.
2. Start infrastructure with `docker compose up --build`.
3. Seed demo data with `docker compose run --rm api python -m app.scripts.seed_demo`.
4. Open `http://localhost:3000`.
5. Sign in with `analyst@macrotracker.local` / `macro-demo-pass`.
6. The API will be available at `http://localhost:8000`.

## Local Development

### API

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e apps/api[dev]
PYTHONPATH=apps/api python3 -m app.scripts.migrate
PYTHONPATH=apps/api python3 -m app.scripts.seed_demo
uvicorn app.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

## Ingestion

Public source ingestion is now wired for these no-key sources:

- `fed_press`
- `fed_speeches`
- `ecb_press`
- `bls_calendar`

List sources:

```bash
TOKEN=$(curl -s http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@macrotracker.local","password":"macro-demo-pass"}' | jq -r .accessToken)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ingestion/sources
```

Pull one source:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/ingestion/pull/fed_press?limit=10"
```

This will:

- fetch the live feed
- upsert `sources`, `ingestion_runs`, `raw_documents`, and `documents`
- match active tracks by keyword overlap
- materialize `stories`, `episodes`, evidence rows, and `event_outbox`

Start the scheduled worker locally:

```bash
make ingestion-worker
```

Or with Docker Compose:

```bash
docker compose up worker
```

Operational endpoints:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ingestion/status
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/notifications/recent
```

## API Keys

No API key is required for the public feeds above.

The production-beta scaffold now reads these keys when available:

- `OPENAI_API_KEY`: LLM summarization / clustering / drafting
- `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`: object storage for exports or raw archives
- `SENTRY_DSN`: backend exception capture

## Auth and Workspaces

- The web app is now the public entrypoint, with Auth.js-backed sessions on the Next.js side.
- The API expects bearer-token auth for every non-health route.
- `POST /api/v1/auth/login` returns the bearer token used by direct API clients.
- Invite-only workspace onboarding is available through `POST /api/v1/auth/accept-invite`.
- Workspace membership and role changes are available under `/api/v1/workspaces/{workspaceId}/members`.

## Migrations

- `db_schema.sql` should be treated as the frozen base schema.
- New schema changes belong in additive SQL files under `migrations/`.
- The current production-beta auth/session migration is `migrations/20260310_production_beta.sql`.

## Current Scope

The current implementation is a production-beta scaffold with authenticated surfaces:

- Authenticated Home / Inbox
- Track list, creation wizard, and mode-aware track detail canvas
- Story detail with contradiction and evidence views
- Workspace member management and invite flow
- Track notes, snapshots, and alert-center actions
- Postgres-backed read APIs
- Postgres-backed write APIs for tracks, notes, and alert policy
- Public-feed ingestion for Fed / ECB / BLS
- Snapshot artifact generation with inline fallback and optional S3 upload
- Session-backed API auth and workspace RBAC
- Scheduled ingestion worker
- Source health and recent in-app notifications on the home screen
- SSE endpoint over `app.event_outbox`
- Migration runner and deterministic demo seed

OpenAI-backed enrichment, S3-backed artifact storage, and Sentry capture are wired as optional integrations and activate when credentials are present.
