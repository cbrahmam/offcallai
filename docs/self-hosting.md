# Self-hosting notes

Operational detail beyond the README's quick start.

## Secrets

Two values must be generated per install and never shared between environments:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"   # ENCRYPTION_KEY
```

`SECRET_KEY` signs JWTs — rotating it invalidates every session.
`ENCRYPTION_KEY` encrypts stored integration credentials, so **rotating it makes
existing stored credentials unreadable**; re-enter them afterwards.

Also set `WEBHOOK_SECRET` before exposing `/api/v1/webhooks/*`, or anyone who
learns the URL can create alerts.

## TLS

The backend serves plain HTTP and the frontend image serves plain HTTP through
nginx. Terminate TLS in front of both — an ingress controller, a load balancer,
or Caddy/nginx on the host.

Once TLS is on, set `API_URL` and `FRONTEND_URL` to the `https://` URLs. They
are not cosmetic: Slack message links, email links, the Sentry DSN shown in the
UI, the agent install snippet and the redirect allow-list are all derived from
them.

`frontend/oncall-frontend/nginx-security.conf` has a hardened server block
(HSTS, CSP, frame options) you can adapt for a host-level nginx.

## Sizing

The API process is mostly IO-bound. A small install (a few dozen hosts, a
handful of engineers) is comfortable in:

| Component | CPU | Memory | Disk |
|---|---|---|---|
| Backend | 0.5 core | 1 GB | — |
| Frontend | 0.1 core | 128 MB | — |
| PostgreSQL | 1 core | 2 GB | 20 GB |
| Redis | 0.1 core | 256 MB | — |
| ClickHouse | 1 core | 4 GB | see below |

ClickHouse dominates disk. The default retention is 90 days of metrics, 30 of
logs, 14 of traces. As a rough guide each agent sends on the order of 200
metric samples per collection interval; at the default 10s that is ~1.7 M
samples per host per day, which compresses to a few tens of MB. Logs and traces
depend entirely on your application volume — measure with one host before
extrapolating.

To change retention, edit the `TTL` clauses in
`backend/clickhouse/schema.sql` before first start, or `ALTER TABLE ... MODIFY
TTL` afterwards.

## Scaling

- **Backend** — stateless, so run several replicas behind a load balancer. Two
  caveats: the WebSocket endpoint holds connections in process memory, so
  notifications only reach clients attached to the same replica (use sticky
  sessions, or accept that the UI also polls); and the background workers run
  inside every replica, so periodic jobs execute once per replica. For more
  than a couple of replicas, run one replica with workers and the rest with
  them disabled, or split the workers out.
- **PostgreSQL** — normal tuning applies. The schema has indexes on the hot
  filters (`organization_id`, timestamps, status).
- **ClickHouse** — vertical scaling goes a long way. Watch merge performance
  and part counts before considering a cluster.

## Backups

PostgreSQL holds everything you cannot reconstruct — incidents, schedules,
runbooks, post-mortems, integration credentials:

```bash
docker compose exec -T postgres pg_dump -U offcall offcall_ai | gzip > offcall-$(date +%F).sql.gz
```

Store it encrypted: it contains credential ciphertext, and it is useless
without the matching `ENCRYPTION_KEY`, so back that key up separately and
somewhere else.

ClickHouse data is observability history. It is large and self-expiring, and
most operators accept losing it rather than paying to back it up. If you do
want it, use `BACKUP TABLE ... TO Disk(...)` or snapshot the volume.

Restore:

```bash
gunzip -c offcall-2026-01-01.sql.gz | docker compose exec -T postgres psql -U offcall offcall_ai
```

## Upgrading

1. Read the release notes for migration or configuration changes.
2. Back up PostgreSQL.
3. Pull the new images.
4. Run `alembic upgrade head` — the compose backend does this on start, and the
   Kubernetes manifests do it in an initContainer.
5. Restart.

Migrations are forward-only; there are no tested downgrade paths. Restore the
backup to roll back.

## Monitoring the monitor

Watch `GET /health` — it reports database connectivity, table count and which
critical tables exist. The compose and Kubernetes definitions already use it as
a healthcheck/probe.

You can also point OffCall at itself: set `OFFCALL_APM_API_KEY` after
`pip install ./sdk/python` to trace the backend, and run the agent on the host
running OffCall. Useful, but don't rely solely on it to tell you it is down.

## Hardening checklist

- `ENVIRONMENT=production`, `DEBUG=false` (this also removes `/docs`).
- `ALLOWED_HOSTS` and `CORS_ORIGINS` limited to hosts you serve.
- `SUPER_ADMIN_EMAILS` set deliberately — those accounts see cross-organization
  analytics. Admin endpoints return 503 while it is empty.
- `WEBHOOK_SECRET` set.
- Database and Redis not published to the internet. The compose file publishes
  5432, 6379 and 8123 for local convenience — drop those `ports:` entries on a
  shared host.
- Rotate agent ingest keys if a node is compromised
  (`DELETE /api/v1/hosts/api-keys/{id}`).
