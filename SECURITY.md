# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for a security vulnerability.

Email **cbrahmam@gmail.com**, or report privately through
[GitHub private vulnerability reporting](https://github.com/cbrahmam/offcallai/security/advisories/new)
(Security -> Report a vulnerability), which keeps the report attached to the
repository.

Please include the affected version or commit, what an attacker can achieve,
and the steps to reproduce. We will acknowledge within a few days and keep you
updated while we work on a fix.

## Scope

This is self-hosted software with no hosted service, so there is no production
environment to test against — please reproduce against your own install.

In scope: authentication and session handling, multi-tenant isolation between
organizations, the webhook and agent ingest paths, stored integration
credentials, and injection of any kind.

Out of scope: findings that require the operator to have misconfigured the
install in ways the documentation warns against (for example running with
`DEBUG=true` in production, or leaving `WEBHOOK_SECRET` unset).

## Operator checklist

The install is only as safe as its configuration:

- Generate fresh `SECRET_KEY` and `ENCRYPTION_KEY` values. Never reuse the
  examples, and never commit a filled-in `.env`.
- Set `WEBHOOK_SECRET` so inbound alert webhooks are signature-verified.
- Set `ENVIRONMENT=production` and `DEBUG=false`. Debug mode exposes
  `/docs` and verbose errors.
- Restrict `ALLOWED_HOSTS` and `CORS_ORIGINS` to the hosts you actually serve.
- Terminate TLS in front of the app; it serves plain HTTP.
- Set `SUPER_ADMIN_EMAILS` deliberately — those accounts can read
  cross-organization analytics.
- Agent ingest keys are shown once and stored only as SHA-256 hashes. Rotate
  them if a node is compromised; revoke via `DELETE /api/v1/hosts/api-keys/{id}`.
