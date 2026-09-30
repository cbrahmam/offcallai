# OffCall AI - working notes

Open-source incident response and observability platform. See README.md for
setup and docs/architecture.md for how the pieces fit together.

## Build and test commands

| Component | Commands |
|---|---|
| Backend | `cd backend && uvicorn app.main:app --reload` · `pytest` · `ruff check app` |
| Frontend | `cd frontend/oncall-frontend && npm start` · `npm run build` |
| Agent | `cd agent && go build ./... && go test ./...` |
| Whole stack | `docker compose up -d` |

Backend needs Python 3.11 or 3.12 (3.13 cannot build the pinned
`pydantic-core`/`asyncpg`). Frontend needs Node 20+.

Backend tests need a real PostgreSQL — the models use `JSONB`/`UUID` and cannot
run on SQLite. Set `TEST_DATABASE_URL`; tests skip silently without it, so
check the skip count.

## Things to know before changing code

**Enum columns store member names.** SQLAlchemy persists `Enum` columns by
member name, so PostgreSQL holds `OPEN` while the Python value is `"open"`.
Query with the enum member (`Incident.status == IncidentStatus.OPEN`), not the
string, or PostgreSQL raises `InvalidTextRepresentationError`.

**`default=` is client-side.** Column defaults apply only when the ORM builds
the INSERT. Raw-SQL inserts (the seed script, `agent_api_keys`, a few services)
must set those columns explicitly or they land NULL and response validation
fails.

**Route order matters.** FastAPI matches in declaration order, so static paths
must be declared before parameterized ones. `/alerts/health-check` declared
after `/alerts/{alert_id}` is unreachable.

**Multi-tenancy is enforced in queries.** Rows carry `organization_id` and
isolation depends on every query filtering by
`current_user.organization_id`. A missing filter is a cross-tenant leak — check
this first when reviewing an endpoint.

**Config lists.** `CORS_ORIGINS` and `ALLOWED_HOSTS` are stored as raw strings
and parsed in a property, because pydantic-settings JSON-decodes complex field
types before validators run. Both comma-separated and JSON array forms work.

**One migration baseline.** `alembic/versions/` holds a single
`0001_initial_schema`. Autogenerate new revisions on top of it and read them
before committing; CI fails if models and migrations disagree.

**ClickHouse is optional but gated everywhere.** Metrics, logs, traces, RUM and
profiling need it (`CLICKHOUSE_ENABLED`). Its JSON output serializes 64-bit
integers as strings, so coerce counts with the `_as_int`/`_as_float` helpers in
`clickhouse_service.py` before comparing or dividing.

## Conventions

- Business logic goes in `app/services/`, not in endpoint functions.
- Frontend styling follows the dark palette in `src/index.css`: transparent
  cards, `border-white/[0.06]`, `text-[13px] text-zinc-400` body text. No
  gradients, shadows or glows.
- No component library on the frontend — the primitives in
  `src/components/ui/` are local implementations.
- Never commit a filled-in `.env`, a Kubernetes Secret with real values, or a
  database dump. `.gitignore` covers these; keep it that way.
