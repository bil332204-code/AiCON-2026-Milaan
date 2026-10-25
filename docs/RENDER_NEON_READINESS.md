# PostgreSQL and private receipt storage — review and deployment procedure

25 October 2026. Implementation branch: `feat/milaan-postgres-private-storage`.
This document is a preparation artifact. No Render service, Neon project/branch,
bucket policy, hosted-user mapping or production record was changed by this work.
The frontend and design are unchanged.

## Intended existing resources

- Neon project: `autumn-truth-83338737`.
- Branch: `br-plain-thunder-azzkcek5`.
- Project region: `aws-ap-southeast-1` (Singapore).
- Private bucket: `milaan-private-receipts`.

Use the existing branch's connection and storage panels. These IDs do not identify
the actual PostgreSQL hostname, database, role, S3 endpoint or access key. No guessed
provider endpoint is embedded in the code. The project region suggests signing
region `ap-southeast-1`; confirm the storage panel's exact signing region and
addressing style before use. The application accepts both path and virtual style.
No credentials were provided here, so Neon runtime behavior, its S3 implementation,
provider IAM policy, TLS and bucket versioning semantics remain unverified.

## Implementation and data boundaries

`DATABASE_URL` is the pooled **runtime** connection; `MIGRATION_DATABASE_URL` is the
**direct** connection to the same branch/database. Provider `postgres://` and
`postgresql://` schemes select psycopg 3 automatically. Runtime pooling defaults to
five connections, no overflow, ten-second pool wait, pre-ping and 300-second recycle.
Automatic prepared statements are disabled for transaction-mode poolers. Each
transaction sets local 30-second statement, ten-second lock and 60-second idle
transaction limits. They do not rely on persistent pooled session state. Alembic
uses the direct URL and NullPool. Neon `-pooler` migration endpoints are rejected;
custom pooler hosts must also be avoided manually. Settings cannot prove that two
different hosts address the same database; verify in the console before migration.
Production requires certificate-verifying PostgreSQL TLS (`sslmode=verify-full`
recommended, with `sslrootcert=system` for the packaged libpq 17 trust store), private S3 configured over HTTPS, secure session cookies and email
verification. Missing bindings fail startup rather than fall back to local disk.

Receipt images are normalized in memory and uploaded with server-side SigV4
credentials. PostgreSQL stores only opaque UUID receipt keys. Authenticated,
owner-scoped API downloads proxy bytes from storage; the app returns no public or
presigned receipt URL and sets no-store. Extractions read the same storage adapter.
No public bucket ACL or bucket policy is changed. No SDK disk cache is used.
Starlette's multipart spool threshold exceeds the bounded accepted request body,
so accepted receipt, orders CSV and statement CSV uploads remain in memory rather
than spilling into Render's temporary filesystem. Request size remains 12 MiB,
raw images 10 MiB and decoded images 25 megapixels; bound service concurrency to
available memory. Infrastructure swap/crash dump/log policy must also be reviewed.

Claim/batch deletion and expiry atomically enqueue receipt deletion in PostgreSQL.
A separate retry table survives financial-row cascades; storage failure does not
restore access to a deleted claim. Deletes are idempotent and retry with bounded
backoff. The worker processes up to 100 pending erasures per sweep, with one remote
operation per database transaction; a failed operation stops that sweep to avoid
multiplying outage timeouts. API requests attempt at most one queued erasure; the
worker drains the rest. Queue rows include a hash of the storage
namespace so changing credentials does not redirect pending erasures elsewhere.
Changing the endpoint, bucket or prefix strands old references/retries: **never
change the namespace in place**. Preserve old bindings until a separately approved,
verified copy/migration has completed. Deletion failure does not block queued
reconciliation work. Monitor sanitized cleanup errors, overdue `next_attempt_at` and retry counts;
alert when attempts reach five or an erasure is overdue by the agreed SLA. Expiry is eventual physical
erasure, while API access ends immediately at the batch expiry time.

The worker also scans only the dedicated configured prefix for crash-created orphan
UUID JPEG objects older than one hour, checks current database references, then
enqueues erasure. Do not share that prefix with another deployment, test harness or
unrelated data. Required permissions are PutObject, GetObject, DeleteObject for this
prefix and ListBucket restricted to this prefix. It must not have public ACL/policy
permissions. Browser access never needs S3 credentials or S3 CORS permissions.
A versioned bucket can retain older versions/delete markers after DeleteObject;
confirm versioning and approved noncurrent-version deletion policy with Neon before
claiming physical erasure. No bucket lifecycle/policy was applied by this work.

Existing SQLite databases, local receipt UUID filenames, UTC-naive timestamp
semantics, integer paisa, authentication and reconciliation behavior are retained.
SQLite/local storage is development-only; production now refuses it. The historical
marketplace migration uses portable SQLAlchemy Boolean defaults so fresh PostgreSQL
installations can replay the existing history. The new additive
`20261025_receipt_deletions` migration creates only the erasure queue. Its downgrade
refuses to drop pending deletion records. No SQLite-to-Neon financial-data copy or
hosted-identity linking was attempted. See `V3_IDENTITY_MIGRATION.md` for that separate
ownership-sensitive operation.

## Exact Render configuration to prepare, not apply yet

Use [the environment template](../deploy/render-neon.env.example). Enter secrets in
Render's secret environment UI or approved secret manager, never a committed file,
frontend variable, shell command argument, screenshot or chat message. URL-encode
passwords in URLs. Keep runtime and migration roles separate if available; grant
runtime only required table DML/sequence access, and migration role the required
DDL permissions. Migration-created tables must be owned/granted appropriately for
the runtime role (including future-table default privileges). Do not use the
superuser credentials from local synthetic tests in production.

The template specifies each application variable. Replace PUBLIC_ORIGIN and
CORS_ORIGINS with the same approved HTTPS Render/custom origin, with no path or
wildcard. Keep ALLOW_REGISTRATION=false and ENABLE_DEMO=false; clear both demo seller
bindings. No production account is auto-provisioned. Configure Resend HTTPS using RESEND_API_KEY and EMAIL_FROM before testing
verification/recovery; see [V4 email delivery](V4_RESEND_EMAIL.md). Manual extraction is the default; no
bank image is sent to an AI provider unless separately configured and explicitly
consented to. Keep one API process/instance with RUN_WORKER_IN_API=true initially;
multiple processes multiply the pool budget and the in-process IP rate limiter is
not distributed. A future dedicated worker uses `python -m app.worker` with identical
DB/storage bindings and API RUN_WORKER_IN_API=false; arrange continuous expiry
cleanup even when web instances sleep. A suspended free-tier service is not an
erasure scheduler. Paid always-on worker or approved scheduled
`python -m app.worker --cleanup` is required for a retention SLA.

For the existing repository Dockerfile, the proposed Render settings are:

| Field | Prepared value |
|---|---|
| Runtime | Docker, repository root, `Dockerfile` |
| Pre-deploy command (if plan supports it) | `cd /app/milaan/backend && python -m alembic upgrade head` |
| Docker command override | `sh -c 'cd /app/milaan/backend && exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --no-proxy-headers --limit-concurrency 2'` |
| Health check | `/api/health` (database SELECT 1; not an S3 write test) |
| Disk | No real bank records on temporary filesystem; PostgreSQL + S3 required |
| Auto-deploy | Keep disabled until the owner approves the release |

The override intentionally separates migration from API startup; the Dockerfile's
existing default auto-migration command remains for development compatibility.
If Render lacks pre-deploy support, use one approved controlled migration job
against the direct URL before starting the app; do not run simultaneous DDL from
every replica. Do not expose the direct migration URL to the browser.
`--no-proxy-headers` prevents unverified forwarded IP spoofing. Behind Render this
may group callers under a proxy IP and conservatively share the rate-limit budget.
Before public traffic, verify Render's trusted proxy/header contract and explicitly
configure trusted proxy handling plus shared rate limiting. Do not blindly trust
arbitrary forwarded headers. This release keeps registration closed.

## Safe checklist for a later approved deployment

1. Review and approve the feature PR. Confirm existing Render configuration, current
   database/users, running release SHA and rollback image without printing secrets.
   Snapshot/backup existing data and prove restoration in an isolated environment.
2. Verify the exact existing Neon branch and roles; record direct/pooled hosts and
   database match without exposing passwords. Confirm private bucket access,
   dedicated namespace, TLS, region, least privilege, versioning/erasure and provider
   backup/PITR policies. Keep the existing hosted identity system available.
3. Prepare secrets in Render securely from the template. Leave registration and
   demo provisioning closed. No real records or credentials go into `/tmp`, source,
   application logs or build arguments. Confirm the Resend sender and inbox delivery independently.
4. With explicit owner approval, first run migrations in a disposable test branch
   or database and repeat synthetic integration/smoke checks against the provider.
   Confirm Alembic head and `alembic check`, runtime-role grants, pooled connection
   recovery and authenticated S3 put/get/delete/list. Verify unsigned object GET is
   denied and no public URL or filesystem receipt remains. Synthetic fixtures only.
5. Approve a maintenance/release window. Take final verified backups; run the single
   direct-connection pre-deploy migration, then start the pinned candidate image.
   Do not migrate hosted users or copy real bank records under this change.
6. Use an explicitly authorized private test operator. Public signup must still
   return 403. If a fresh database needs a private operator, establish an approved
   provisioning procedure separately; never temporarily open registration or set
   production demo seller variables. Test login/CSRF, verification/recovery, restart,
   ownership isolation, receipt upload/download, reconciliation/manual review and
   exports with synthetic records.
7. Delete and expire synthetic batches. Check queue retries with a controlled
   storage failure, confirm all synthetic objects/versions are erased, and verify
   worker scheduling, no upload spooling, pool/memory limits, health and alerting.
8. If validation fails, stop writes, preserve the queue/namespace, roll back to the
   previous compatible image and restore only from verified coordinated backups.
   Do not automatically downgrade schema or discard pending erasures. Restoring an
   old DB backup can revive deleted references: reconcile erasures before reopening.
9. Hosted-user migration, public registration, Render service changes and production
   deployment remain separately authorized operations. None occurred during this task.

## Reproduce local validation

Install pinned backend requirements with `constraints-py312.txt`. Run backend and
root suites normally for SQLite. Run `python scripts/test_postgres_s3.py` from the
repository root with Docker available for the PostgreSQL/S3 suite. It generates
throwaway credentials, creates a local PostgreSQL 17 container and Moto S3 HTTP
service, binds ports only to loopback, isolates each test schema/prefix and removes
containers/volumes afterward. It does not read Neon credentials or create Neon
resources. Moto emulates S3 behavior; it is not evidence of Neon compatibility or
provider IAM/signature enforcement. SDK request signing/error handling is checked
separately. Container images and dependency versions are pinned in the runner.

## Executed validation for this change

All application data was synthetic. Final results:

| Check | Result |
|---|---|
| Backend and matching suites, SQLite/local storage | 147 passed; 3 PostgreSQL-only tests skipped |
| Same suites, PostgreSQL 17 + authenticated S3 HTTP adapter | 150 passed; none skipped |
| Focused PostgreSQL/S3 storage and migration checks after final deletion timeout cap | 15 passed; 135 deselected |
| Focused SQLite API/storage checks after that cap | 21 passed |
| Root store and SQLite migration suites | 8 passed |
| Frontend unit regressions, unchanged frontend | 36 passed |
| Playwright desktop/mobile, SQLite/local storage | 12 passed |
| Live HTTP demo checks | Five original scenarios, confirmed receipt, saved human review, private export passed |
| Updated Docker image build and ephemeral container smoke | Passed: non-root, UI assets, CSRF, data/session persistence after restart, logout revocation |
| Updated Compose configuration validation | Passed; configuration only, no services started |
| Dependency consistency, Python compilation and whitespace checks | Passed |

PostgreSQL-specific tests replay the actual Alembic history, preserve a legacy user
and bearer session across upgrade/downgrade, prove direct migration URL selection
while runtime URL is unreachable, reject a downgrade with pending erasures, check
schema drift, verify transaction-local timeouts/prepared statement configuration,
exercise SKIP LOCKED job claiming and competing batch revisions. Existing allocation,
authentication, recovery, isolation and reconciliation regressions also run on
PostgreSQL. Storage coverage includes signed requests, default-private anonymous GET
rejection in the emulator, owner-only reads, app-instance refresh, missing/provider
errors, partial-PUT rollback cleanup, retry persistence, namespace isolation,
deduplication, expiry/orphans, extraction and >1 MiB uploads without disk spooling.

The existing Starlette/httpx TestClient deprecation warning remains. Local service
images were PostgreSQL `17-alpine` and Moto `5.1.15`; no MinIO or Neon test success
is claimed. This does not test a real Neon pooler, provider signatures/IAM, production
TLS, role grants, storage version deletion, real Resend inbox delivery, Render limits or live load.
The browser screenshots regenerated during regression testing were restored; no
frontend/design/screenshot changes are included in this branch. CI has been updated
to reproduce the isolated integration suite, but no remote CI success is claimed.
