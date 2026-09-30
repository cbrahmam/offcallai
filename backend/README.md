# OffCall AI backend

FastAPI application. See the [root README](../README.md) for the full picture.

## Running it

Python 3.11 — 3.12 works, 3.13 cannot build the pinned `pydantic-core` and
`asyncpg` wheels.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # fill in DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Interactive API docs are at <http://localhost:8000/docs> while `DEBUG=true`;
they are removed when it is false.

## Layout

```
app/
  main.py              app construction, middleware, WebSocket, startup checks
  api/v1/__init__.py   router registry (every router in a try/except ImportError)
  api/v1/endpoints/    47 routers
  services/            56 service modules — business logic lives here
  models/              40 SQLAlchemy models
  schemas/             pydantic request/response models
  core/                config, security, deps, GDPR helpers
  workers/, background/  periodic asyncio loops
alembic/               migrations (single baseline: 0001_initial_schema)
clickhouse/            time-series schema + listen config
scripts/               seeding and ClickHouse bootstrap
tests/                 75 tests
```

## Tests

The models use PostgreSQL-specific types (`JSONB`, `UUID`) and cannot run on
SQLite, so the fixtures need a real database:

```bash
createdb offcall_test
export TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/offcall_test
pytest
```

Integration tests **skip** rather than fail when that database is unreachable,
so check the skip count before believing a green run.

```bash
ruff check app          # narrow, defect-focused rule set (see ruff.toml)
```

## Migrations

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
```

Always read the generated file: autogenerate misses renames and usually gets
enum changes wrong. CI fails if the models and the baseline disagree.

## Seeding

```bash
python scripts/seed_dev_data.py                      # org, admin, sample data
python scripts/seed_dev_data.py --email me@example.com --password 'S3cret!'
python scripts/init_clickhouse.py                    # apply the ClickHouse schema
python scripts/seed_clickhouse_data.py               # sample metrics/logs/traces
python scripts/seed_alert_rules.py                   # a starter set of alert rules
```

## Two things that will bite you

**Enum columns store member names.** SQLAlchemy persists `Enum` columns by
member name, so the database holds `OPEN`, not `open`. In queries compare
against the enum member (`Incident.status == IncidentStatus.OPEN`); comparing a
loaded attribute to `"open"` in Python is fine, since these are `str` enums.

**`default=` is client-side.** Column defaults are applied by SQLAlchemy when it
builds an INSERT, not by PostgreSQL. Raw-SQL inserts must set those columns
explicitly, or they are NULL and response validation then fails.
