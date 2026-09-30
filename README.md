# OffCall AI

Open-source incident response and observability. Collect metrics, logs and
traces from your infrastructure, turn alerts into incidents, page whoever is
on call, and use an LLM to help work out what broke.

Self-hosted, MIT licensed, no per-seat pricing.

```
                 ┌──────────────┐
                 │  React SPA   │
                 └──────┬───────┘
                        │ REST + WebSocket
                 ┌──────▼───────┐        ┌────────────┐
   Go agent ────►│   FastAPI    │◄──────►│ PostgreSQL │  incidents, alerts,
   SDKs     ────►│              │        └────────────┘  schedules, runbooks
   webhooks ────►│              │        ┌────────────┐
                 │              │◄──────►│ ClickHouse │  metrics, logs, traces,
                 │              │        └────────────┘  RUM, profiles
                 └──────┬───────┘        ┌────────────┐
                        └───────────────►│   Redis    │  cache, rate limits
                                         └────────────┘
```

## What's in the box

**Incident response** — incidents with severity and status, acknowledge and
resolve flows, timeline and comments, on-call schedules with rotations,
escalation policies, maintenance windows that suppress alerting, post-mortems
with action items, and public status pages.

**Observability** — host metrics from a Go agent, logs, distributed traces and
a service dependency map, container and Kubernetes monitoring, database
monitoring, error tracking (with a Sentry-compatible ingest endpoint), browser
RUM, continuous profiling, and synthetic checks.

**Alerting** — inbound webhooks from Prometheus, Grafana, Datadog and friends,
threshold alert rules over your own metrics, anomaly detection, and alert
correlation and enrichment.

**AI assistance** — root-cause analysis over an incident and its surrounding
telemetry, a chat interface scoped to one incident, natural-language querying,
and runbook suggestions. Bring your own Anthropic, OpenAI or Gemini key;
configure two or more and the analyses are merged into a consensus.

**Notifications** — Slack (messages and slash commands) and email.

## Quick start

Requires Docker and about 4 GB of free memory.

```bash
git clone https://github.com/cbrahmam/offcallai.git
cd offcallai

# 1. Create the backend config and generate the two required keys.
cp backend/.env.example backend/.env
python3 - <<'PY'
import pathlib, secrets
p = pathlib.Path("backend/.env")
s = p.read_text()
s = s.replace("SECRET_KEY=\n", f"SECRET_KEY={secrets.token_urlsafe(32)}\n")
s = s.replace("ENCRYPTION_KEY=\n", f"ENCRYPTION_KEY={secrets.token_urlsafe(32)}\n")
p.write_text(s)
PY

# 2. Bring everything up. Migrations run automatically.
docker compose up -d

# 3. Load sample incidents, alerts, hosts, runbooks and schedules.
docker compose exec backend python scripts/seed_dev_data.py
```

Open <http://localhost:3000> and sign in with `admin@example.com` /
`ChangeMe123!` (override with `--email` / `--password` on the seed script).

The API is on <http://localhost:8000>, with interactive docs at
<http://localhost:8000/docs> and a health summary at
<http://localhost:8000/health>.

To start without ClickHouse — incidents, alerts, on-call, runbooks and status
pages all work; metrics, logs, traces, RUM and profiling do not — set
`CLICKHOUSE_ENABLED=false` in the backend environment and skip that service.

### Send it some data

Metrics come from the Go agent. Create an ingest key under **Infrastructure →
Install Agent** (or `POST /api/v1/hosts/api-keys`), then:

```bash
cd agent
go build -o offcall-agent ./cmd/agent
OFFCALL_API_KEY=oai_xxx \
OFFCALL_API_ENDPOINT=http://localhost:8000/api/v1/metrics/ingest \
  ./offcall-agent
```

Within a few seconds the host appears under **Infrastructure** with CPU,
memory, disk, network, process and Docker metrics.

Application errors and traces come from the SDKs in [`sdk/`](sdk/) — Python,
JavaScript/Node and Go. Alerts from existing monitoring arrive over
`POST /api/v1/webhooks/{source}`.

## Running without Docker

Backend (Python 3.11 — 3.13 cannot build the pinned `pydantic-core` and
`asyncpg` wheels):

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # then fill in DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend (Node 20+):

```bash
cd frontend/oncall-frontend
cp .env.example .env
npm ci
npm start                     # dev server on :3000
npm run build                 # production bundle into build/
```

You need PostgreSQL 15+ and Redis 7+ reachable, plus ClickHouse if you want the
telemetry features.

## Configuration

Everything is environment-driven. [`backend/.env.example`](backend/.env.example)
documents every key; the essentials:

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL, `postgresql+asyncpg://` driver |
| `SECRET_KEY` | yes | JWT signing. `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ENCRYPTION_KEY` | yes | Encrypts stored integration credentials. Generate the same way |
| `REDIS_URL` | — | Defaults to `redis://localhost:6379` |
| `API_URL`, `FRONTEND_URL` | — | Public URLs of this install. Links in Slack and email, and the agent install snippet, are built from these |
| `CORS_ORIGINS`, `ALLOWED_HOSTS` | — | Comma-separated or a JSON array |
| `CLICKHOUSE_ENABLED` + `CLICKHOUSE_*` | — | Required for metrics, logs, traces, RUM, profiling |
| `SUPER_ADMIN_EMAILS` | — | Who may call `/api/v1/admin/*`. Those routes return 503 until set |
| `SMTP_HOST` and friends | — | Email notifications and password resets |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | — | AI features. Organizations can also add keys in Settings |
| `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` | — | Slack notifications and slash commands |
| `WEBHOOK_SECRET` | — | Verifies signatures on inbound alert webhooks. Set this in production |

The frontend reads `REACT_APP_API_URL` **at build time**, so rebuild the image
after changing it.

## Deploying

[`k8s/`](k8s/) holds registry-agnostic manifests — namespace, ConfigMap, Secret
template, backend Deployment (migrations run in an initContainer), frontend,
an example Ingress, and the agent DaemonSet. Replace `ghcr.io/cbrahmam/...` with
your own images and the `example.com` hosts with yours:

```bash
kubectl apply -f k8s/00-namespace.yaml
cp k8s/01-secrets.example.yaml k8s/secrets.yaml   # fill in, do not commit
kubectl apply -f k8s/secrets.yaml -f k8s/02-config.yaml
kubectl apply -f k8s/10-backend.yaml -f k8s/11-frontend.yaml
```

See [docs/self-hosting.md](docs/self-hosting.md) for TLS, backups, scaling and
ClickHouse sizing.

## Repository layout

```
backend/        FastAPI app — 47 routers, 56 services, 40 models, 88 tables
  app/api/v1/   HTTP endpoints
  app/services/ business logic
  app/models/   SQLAlchemy models
  alembic/      migrations (one baseline)
  clickhouse/   time-series schema
  scripts/      seeding and ClickHouse bootstrap
frontend/       React + TypeScript SPA, Tailwind, custom UI primitives
agent/          Go host agent — metrics, logs, Docker, Kubernetes
cli/            Python CLI (`offcall`)
sdk/            error/trace SDKs for Python, JavaScript and Go
k8s/            Kubernetes manifests
docs/           architecture and self-hosting notes
```

## Development

```bash
cd backend  && pytest && ruff check app     # 75 tests
cd agent    && go test ./... && go vet ./...
cd frontend/oncall-frontend && npm run build
```

CI runs all of the above plus a check that the migration baseline still matches
the models.

### Known rough edges

Honest notes, since you'd find these anyway:

- **Frontend lint backlog.** ~130 unused imports and 13 `react-hooks/
  exhaustive-deps` warnings. `npm run build` passes (it does not treat warnings
  as errors); clearing them is a good first contribution.
- **Backend lint scope.** `backend/ruff.toml` deliberately selects only
  defect-catching rules. The default rule set reports several thousand
  formatting findings, best dealt with in its own pass.
- **Alert enrichment is manual.** The enrichment and correlation endpoints work,
  but nothing triggers enrichment automatically when an alert is ingested; the
  code that was meant to do it was an unfinished stub and has been removed.
- **Metrics need ClickHouse.** There is no PostgreSQL fallback for metric
  samples; those endpoints return 503 when ClickHouse is disabled. Logs and
  traces do have a PostgreSQL path.
- **Uneven test coverage.** 75 tests concentrated on auth, security, incident
  collaboration and a few end-to-end flows. Most services have none.
- **Resolution steps are template-generated.** The resolution workflow asks the
  API for AI-generated steps and falls back to built-in templates when that
  endpoint is absent, which it currently is. The fallback is what you will see.
- **No ad-hoc command execution, by design.** Running a command supplied by the
  browser would be remote code execution on the backend host, so there is no
  endpoint for it; the workflow marks those steps for you to run manually.
  Runbooks have a sanctioned, server-defined execution path
  (`POST /runbooks/{id}/execute`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and PRs welcome; please run
the checks above first.

## Security

Please don't open public issues for vulnerabilities — see
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
