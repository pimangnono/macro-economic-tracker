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
5. The API will be available at `http://localhost:8000`.

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
curl http://localhost:8000/api/v1/ingestion/sources
```

Pull one source:

```bash
curl -X POST "http://localhost:8000/api/v1/ingestion/pull/fed_press?limit=10"
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
curl http://localhost:8000/api/v1/ingestion/status
curl http://localhost:8000/api/v1/notifications/recent
```

## API Keys

No API key is required for the public feeds above.

You will need keys later for:

- `OPENAI_API_KEY`: LLM summarization / clustering / drafting
- `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`: object storage for exports or raw archives

## Current Scope

The initial implementation is production-oriented infrastructure and MVP surfaces:

- Home / Inbox live board
- Track detail shell
- Track creation flow
- Story detail shell
- Postgres-backed read APIs
- Postgres-backed write APIs for tracks, notes, and alert policy
- Public-feed ingestion for Fed / ECB / BLS
- Scheduled ingestion worker
- Source health and recent in-app notifications on the home screen
- SSE endpoint over `app.event_outbox`
- Migration runner and deterministic demo seed

Auth and key-backed external enrichments are still left unconfigured until production credentials are available.
