# Contributing

Thanks for taking a look. Bug reports, fixes and features are all welcome.

## Getting set up

Follow the Quick start in the [README](README.md) — `docker compose up -d` plus
the seed script gives you a working install with sample data. For iterating on
code, run the backend and frontend natively (see "Running without Docker") so
you get reload on save.

## Before opening a pull request

Run what CI runs:

```bash
cd backend && pytest && ruff check app
cd agent && gofmt -l . && go build ./... && go vet ./... && go test ./...
cd frontend/oncall-frontend && npm run build
```

Backend tests need PostgreSQL, because the models use `JSONB` and `UUID` and
cannot run on SQLite. Point `TEST_DATABASE_URL` at a throwaway database:

```bash
createdb offcall_test
export TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/offcall_test
```

Tests that need it skip cleanly when it is unreachable, so a bare `pytest` will
look like it passed when it merely skipped. Check the skip count.

## Database changes

There is a single migration baseline. When you change a model:

```bash
cd backend
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

Read the generated file before committing — autogenerate misses table and
column renames, and enum changes usually need hand-editing. CI fails if the
models and migrations disagree.

Two things to know about this schema:

- `Enum` columns are stored by member **name** (uppercase), so query with the
  enum member, not the lowercase value: `Incident.status == IncidentStatus.OPEN`.
- Raw-SQL inserts must set every column your response schema requires.
  SQLAlchemy `default=` is applied client-side only, so a raw insert leaves
  those columns NULL and the API then fails validation.

## Style

Match the file you are editing. Beyond that:

- **Backend** — `ruff check app` must pass. The selected rule set is narrow on
  purpose (see `backend/ruff.toml`); widening it is welcome as its own PR.
- **Frontend** — the build must pass. There is a backlog of unused-import and
  `exhaustive-deps` warnings; clearing some is a nice first contribution.
- **Agent** — `gofmt` and `go vet` clean.

## Routing gotcha

FastAPI matches routes in declaration order, so static paths must be declared
before parameterized ones. `@router.get("/health-check")` after
`@router.get("/{alert_id}")` is unreachable — this has bitten this codebase
more than once.

## Commits

Explain why, not just what. If you fixed a bug, say how it manifested.
