# Architecture

## Shape of the system

Four processes and three data stores.

```
   ┌─────────────────────────────────────────────────────────────┐
   │  React SPA (CRA, TypeScript, Tailwind)                      │
   │  hand-rolled router in App.tsx; no react-router             │
   └───────────────┬─────────────────────────────────────────────┘
                   │  REST /api/v1  +  WebSocket /api/v1/ws/notifications
   ┌───────────────▼─────────────────────────────────────────────┐
   │  FastAPI backend                                            │
   │    app/api/v1/endpoints/   47 routers, ~470 routes          │
   │    app/services/           56 service modules               │
   │    app/models/             40 SQLAlchemy models             │
   │    app/workers/            background loops                 │
   └───┬──────────────────┬──────────────────┬───────────────────┘
       │                  │                  │
  ┌────▼─────┐      ┌─────▼──────┐    ┌──────▼──────┐
  │ Postgres │      │ ClickHouse │    │    Redis    │
  │ 88 tables│      │  7 tables  │    │ cache, rate │
  │          │      │            │    │   limits    │
  └──────────┘      └────────────┘    └─────────────┘

  Ingest paths into the backend:
    Go agent      → /api/v1/metrics/ingest, /logs/ingest, /traces/ingest
    SDKs          → /api/v1/errors/..., /api/v1/rum/ingest/batch
    Sentry SDKs   → /api/v1/api/sentry/{project_id}/envelope
    monitoring    → /api/v1/webhooks/{source}
```

## Why two databases

They store different shapes of data and the split is not optional.

**PostgreSQL** holds the relational, mutable, transactional state: organizations
and users, incidents, alerts, escalation policies, on-call schedules and shifts,
runbooks and executions, maintenance windows, post-mortems, status pages,
service catalog and SLOs, dashboards, integrations, API keys, audit logs.
88 tables, created by a single Alembic baseline.

**ClickHouse** holds append-only time series, where the row counts are orders of
magnitude larger and retention is enforced by `TTL`:

| Table | Contents | Retention |
|---|---|---|
| `metrics` | host and container metric samples | 90 days |
| `logs` | log lines | 30 days |
| `spans` | distributed trace spans | 14 days |
| `service_metrics` | pre-aggregated service stats | 90 days |
| `rum_events` | browser telemetry | 30 days |
| `network_flows` | network flow records | 7 days |
| `profiles` | continuous profiling samples | 7 days |

Plus materialized views that roll metrics up per minute and logs per hour.

`CLICKHOUSE_ENABLED` gates every consumer, so the product runs without it —
you lose metrics, logs, traces, RUM and profiling, and keep everything else.
There is no PostgreSQL fallback for metric samples (those endpoints return 503);
logs and traces do have one, against the `log_entries` and `traces` tables.

**Redis** is cache, rate-limit counters and transient state. Nothing durable.

## Request path

`app/main.py` builds the app, then mounts `app/api/v1/__init__.py`, which
registers every router inside `try`/`except ImportError` blocks — a router
whose optional dependency is missing is skipped with a log line rather than
taking the process down.

Two things about routing worth knowing:

- FastAPI matches in **declaration order**, so a static path declared after a
  parameterized one is unreachable. `/alerts/health-check` was being captured
  by `/alerts/{alert_id}` until the routes were reordered.
- Authentication is a dependency: `Depends(get_current_user)` resolves the
  bearer token to a `User` and, through it, an `organization_id`. Almost every
  query is scoped by that id — this is how tenants are isolated.

Ingest endpoints authenticate differently. The agent and the error/RUM SDKs
present a key from `agent_api_keys`, of which only a SHA-256 hash is stored; the
Sentry-compatible endpoint takes the same key out of the DSN.

## Data model notes

Two sharp edges that cause real bugs:

**Enum columns store member names.** `IncidentStatus.OPEN = "open"` is declared
with the lowercase value, but SQLAlchemy persists `Enum` columns by member name,
so PostgreSQL holds `OPEN`. Comparing a column to `"open"` in a query raises
`InvalidTextRepresentationError`. Compare against the enum member instead.
Comparing a loaded attribute to `"open"` in Python *is* fine, because these are
`str` enums.

**`default=` is client-side.** SQLAlchemy column defaults are applied when the
ORM builds an INSERT, not by the database. Raw-SQL inserts — the seed script,
`agent_api_keys` writes, several service methods — must set those columns
explicitly or they end up NULL and the response schema then rejects the row.

## Background work

`app/workers/background_tasks.py` and `app/background/worker.py` run periodic
loops as asyncio tasks inside the API process: evaluating alert rules, running
escalations, executing synthetic checks, polling database monitors, and
cleaning up expired data. Retention for time-series data is *not* one of them —
ClickHouse `TTL` handles that.

Because they share the API process, they scale with it. Splitting them into a
separate worker deployment is the obvious next step for a large install.

## Frontend

Create React App with TypeScript and Tailwind. There is no component library:
the 17 primitives under `src/components/ui/` are local implementations, and all
Radix and `class-variance-authority` dependencies were removed.

Routing is hand-rolled in `App.tsx` — a `Page` union, a `PAGE_PATHS` table, and
a `resolvePath` function shared by the initial load and `popstate`. State comes
from three contexts: `AuthContext` (token, user, login/logout),
`NotificationContext` (toasts and unread count), and the sidebar preference
hook. Data fetching is `fetch` against `API_URL` with a bearer token; there is
no query cache.

`REACT_APP_API_URL` is baked in at build time, so the image must be rebuilt to
point at a different API.

## Agent

A single Go binary (`agent/`) that registers itself, collects on an interval,
buffers to disk when the backend is unreachable, and posts batches. Collectors:
CPU, memory, disk, network, processes, Docker, and optionally Kubernetes
(cluster/node/pod/deployment state via the API server) plus log tailing and
profiling.

Configuration is a YAML file, environment variables, or both — the file is
optional, and environment variables always win, which is how the container and
DaemonSet deployments are configured.

## AI integration

`app/services/ai_service.py` and `ai_rca_service.py` call whichever providers
have keys — Anthropic, OpenAI or Gemini — using keys from the organization's
settings or the deployment-wide environment. With two or more configured, the
responses are merged into a consensus; with one, that provider's answer is used
directly. No provider is required, and nothing is sent anywhere unless a key is
configured.

## Multi-tenancy

One deployment serves many organizations. Users belong to exactly one
organization, and rows carry `organization_id`. Isolation is enforced in
application queries rather than by row-level security in the database, so new
queries must filter by `current_user.organization_id` — a missing filter is a
cross-tenant data leak, and it is the single most important thing to check when
reviewing a new endpoint.
