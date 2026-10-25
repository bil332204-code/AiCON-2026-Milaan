> **Historical V3 design, superseded for current deployment/email:** See [Operations](OPERATIONS_RUNBOOK.md) and [V4 Resend](V4_RESEND_EMAIL.md). V3 SMTP instructions below do not describe today's production email adapter.

# Deploying the integrated Milaan alternative

> Email update: SMTP instructions below are historical. Use
> [V4 Resend HTTPS configuration](V4_RESEND_EMAIL.md) for current email delivery.

> Production storage update: the SQLite/local-disk production path below is superseded
> by [Render + Neon readiness](RENDER_NEON_READINESS.md). Production now requires
> PostgreSQL and HTTPS private S3. Local SQLite remains supported for development.

This is a prepared path for a **separate, approved deployment**. It does not update
the existing Sites website. Do not change its DNS, identity provider or data until
[V3 identity migration](V3_IDENTITY_MIGRATION.md) is proven and approved.

## Local development

Follow README_FIRST.md with Python 3.12 and the tested constraint resolution:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -c milaan/backend/constraints-py312.txt -r milaan/backend/requirements.txt
cd milaan/backend
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

A configured local operator can still use password login. Before password recovery
is available, an existing account must confirm its email in Account & content.
New public signup requires SMTP verification. If SMTP is not configured, use only
the configured local operator or explicitly development-only verification override
with synthetic accounts. Never use that override for a public deployment.

`APP_ENV=development` permits loopback HTTP cookies. Production checks require
HTTPS `PUBLIC_ORIGIN`, secure cookies, email verification and no demo provisioning.
The browser UI uses cookies on the same hostname/scheme. Different-host API mode
retains temporary in-memory bearer login and cannot promise remembered sessions.
Serve UI and API from the same origin for the supported production experience.

## Prepared single-machine HTTPS path

The root Dockerfile contains the real static UI and backend together. The inherited
backend-only Dockerfile is not this deployment entry point. Dependencies are pinned
through `constraints-py312.txt`, and the app runs as uid 10001 with durable data in
`/app/data`. No `.env`, credentials, test SMTP inbox or browser test server is copied
into the image. Production requires a real mail provider; do not deploy the examples
as credentials or claim email delivery has been verified.

1. Provision an approved host with Docker/Compose v2 and a hostname you control.
   Keep it separate from the old website until identity migration is safe.
2. Copy `deploy/production.env.example` to the ignored root `.env.production`.
   Set the intended domain, sender and SMTP host/port/security/user/password securely.
   Set exact production CORS origins and preserve HTTPS/Secure/email-verification
   settings. Do not put demo operator bindings in this file.
3. Back up the database and private uploads together while application writes are
   stopped. Restore only the intended installation's data into the durable volume;
   the new stack will not import hosted data or discover ownership mappings for you.
4. Validate before starting anything:

```sh
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker build -t milaan-v3-review:local .
python scripts/container_smoke.py
```

5. Only after explicit deployment approval, on the intended host:

```sh
docker compose --env-file .env.production -f compose.production.yml up --build -d
```

Startup upgrades schema before serving requests. Stop all old API/worker processes
before migrating existing records; mixed code versions are unsupported. Verify
health, signup mail, legacy email confirmation, reset mail, cookie flags, CSRF,
logout and owned records on the real HTTPS origin before cutover. Test backups and
rollback. Cookie sessions are revoked on downgrade; legacy data/passwords remain.

Caddy is the only public ingress and manages TLS for the configured domain. The API
port is internal and trusts forwarded headers from that isolated proxy network;
never publish the API directly or attach untrusted containers to that network.
Caddy needs the intended DNS and ACME connectivity. It was config-validated here,
not run on a real domain. No production certificates were requested.

SQLite is the tested single-machine path with one in-process worker. PostgreSQL
configuration exists separately, but multi-node runtime/concurrency is not verified
by this release. Layer appropriate edge abuse controls, monitoring, backup, storage
encryption and credential rotation onto any real deployment. The in-app IP limit is
single-instance; persistent account lockouts add a separate protection.

## Build proxies without disabling verification

On managed/enterprise networks the Docker builder may need the same proxy routing
and trusted public CA bundle as its host. `scripts/build_image.py` resolves the
configured proxy hostname and supplies the trusted host CA via an ephemeral BuildKit
secret. It never prints/copies credentials or embeds the bundle in the shipped image.

```sh
DOCKER_CONFIG=/tmp/milaan-docker .venv/bin/python scripts/build_image.py
DOCKER_CONFIG=/tmp/milaan-docker .venv/bin/python scripts/container_smoke.py
```

The temporary Docker config path is only needed where the default home is read-only.
Ordinary hosts can use `docker build` directly. Do not disable TLS verification or
use trusted-host shortcuts to make package installation pass.

## Operational data and recovery

`PUBLIC_ORIGIN` is used in password-reset links and must be the real browser origin,
not an internal container hostname. Reset tokens travel in fragments, expire in
15 minutes and are single use. Access logs must not be extended to log request
bodies, cookies, credentials or email contents. Live SMTP transport requires valid
TLS and provider authentication; resets use a uniform response even if delivery
fails, with only a sanitized operational warning logged.

Normal sessions default to 12 hours; remember-me is finite (30 days). Old users keep
IDs and password access. Their unknown email-verification status must be confirmed
from an authenticated session before recovery is enabled; do not mark all legacy
emails verified as a shortcut. A user who has lost both the old password/session and
unverified email ownership needs a supported operator/provider identity recovery
process, not an email-string database rewrite.

Batch expiry remains seven days by default. This release does not change financial
matching, retained credit budgets or private image ownership. Read PRIVACY.md before
using real data. Account-level deletion was not added; existing batch deletion and
private CSV/image exports remain available.
