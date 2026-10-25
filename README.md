# Milaan — payment evidence reconciliation

AiCON 2026 — Build With AI. Milaan helps sellers compare orders, receipt evidence
and receiving-bank exports, producing explainable **SHIP / HOLD / REVIEW**
recommendations. These are operational recommendations based on supplied evidence;
they do not independently confirm bank settlement or execute payments or shipping.

[Production site: milaan.app](https://milaan.app) ·
[Separate ChatGPT Sites workspace](https://milaan-studio.bil332204.chatgpt.site/workspace) ·
[Separate ChatGPT Sites guide](https://milaan-studio.bil332204.chatgpt.site/guide) ·
[Portfolio](https://bilal-ahmed-builds.cyou/projects/milaan)

## Which website deploys from this repository?

**milaan.app is served from this GitHub repository**, deployed by the separate
Render service `milaan-production-2026`: branch `main`, repository-root
`Dockerfile`, custom domain `milaan.app`. This deployment mapping was
verified against the Render service configuration on 2026-10-25.
Editing another branch or an unmerged PR does not change the production site;
the Render production service currently has automatic deployments disabled.

The older `milaan-studio.bil332204.chatgpt.site` application is a **distinct,
separately maintained ChatGPT Sites workspace**. Editing this repo does not update
that Sites app. The capability comparison below refers to the separate Sites
workspace; its behavior is previously documented but **not independently
verified** in this release pass.

| Capability | Hosted workspace (unverified claims) | GitHub local kit (source and local tests) |
|---|---|---|
| Authentication | ChatGPT sign-in | Email/password; HttpOnly browser cookies and CSRF; native bearer API; verified email and recovery |
| Batch persistence | Hosted saved batches | SQLite; configurable expiry; PostgreSQL configuration available |
| Orders CSV | Supported | Normalized CSV and individual order entry |
| Statement CSV | Supported | Normalized CSV with account and coverage declaration |
| PDF processing | Reviewed extraction; claimed 5 MB / 200 records | No native PDF import; normalize to CSV yourself |
| Receipt extraction | Optional Gemini, user confirmation | Manual confirmation; optional Gemini with explicit consent |
| Reconciliation | Explainable recommendations | Deterministic rules; Pakistani name similarity suggests review candidates |
| Exports | CSV / JSON claimed | Results CSV; authenticated receipt downloads |
| Simulated store | Not verified | Separate authenticated synthetic store and live integration test |

## Workflow and architecture

Sign in → create batch → import orders and receiving statement → upload receipt →
extract or manually confirm fields including payment status → reconcile → inspect
evidence → record human review → export CSV.

FastAPI serves the static JavaScript UI, authentication, private files and API.
SQLAlchemy/Alembic manage persistence; a database-backed worker processes extraction,
matching and expiry. The separate store communicates through authenticated APIs.
[Architecture diagram](docs/ARCHITECTURE.md) ·
[Import and matching contracts](docs/IMPORT_CONTRACTS.md) ·
[Retention and privacy](docs/PRIVACY.md).

Browser-local mode is illustrative and batch-scoped. Saved backend mode persists
records and enforces credit uniqueness across retained batches. Neither mode treats
name similarity as payment confidence. Fixture mode uses known synthetic fields;
it does not demonstrate OCR or AI accuracy.

## Quick start

Use **[README_FIRST.md](README_FIRST.md)** for canonical setup. Python 3.12 is the
verified runtime. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -c milaan/backend/constraints-py312.txt -r milaan/backend/requirements.txt
.venv/bin/python setup_admin.py
cd milaan/backend
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from `demo-store`, run
`../.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8090`.
Use your configured operator in both applications. No Node build is required.
Python 3.13 remains unverified. Root Windows `SETUP.bat` and `START_DEMO.bat` were exercised on `windows-latest` with Python 3.12 and a preconfigured synthetic operator (both localhost services returned HTTP 200); the interactive operator prompt was not tested. See [Windows CI evidence](https://github.com/bil332204-code/AiCON-2026-Milaan/actions/runs/40202954091).

## Demonstration scenarios

| Synthetic scenario | Expected result |
|---|---|
| Correct payment | SHIP / EXACT_MATCH |
| Missing credit | HOLD / NOT_FOUND |
| Wrong amount | REVIEW / AMOUNT_CONFLICT |
| Reused proof | REVIEW / REUSED_PROOF |
| Pakistani name variation | REVIEW / POSSIBLE_MATCH |

[Five-minute demo](docs/DEMO.md) · [Roman Urdu guide](DEMO_GUIDE_ROMAN_URDU.md).

## V3 cinematic interface and independent sign-in

[Implemented V3 build](docs/V3_RELEASE.md) adds a dark cinematic landing page and
workspace, independent cookie-based browser authentication, verified signup,
password recovery, refresh-safe sessions and a tested integrated deployment image.
[Before/after captures](docs/V3_RELEASE.md#genuine-before-and-after-captures) use
synthetic local data. The hosted Sites app remains separate and unchanged;
[identity migration is blocked until authoritative access exists](docs/V3_IDENTITY_MIGRATION.md).
See [deployment requirements](docs/V3_DEPLOYMENT.md) before exposing a new instance.

## V2 development

[Milestone A](docs/V2_MILESTONE_A.md) adds reviewed CSV mapping, private import
provenance, discrepancy filters and desktop/mobile browser tests with genuine
synthetic screenshots. Saved-backend split/combined/partial allocation is implemented in
[Milestone B](docs/V2_MILESTONE_B.md), with explicit human confirmation, retained
credit budgets, a forward migration and additional browser tests.

## Verification

```sh
cd milaan/backend
../../.venv/bin/python -m pytest tests matching/tests
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m alembic check
cd ../..
.venv/bin/python -m pytest tests/test_store_sync.py tests/test_migrations.py
.venv/bin/python tests/live_demo_check.py
node --test milaan/frontend/tests/*.test.mjs
npm --prefix milaan/frontend run check
```

GitHub Actions runs credential-free local checks on Python 3.12 and Node 24.
See [release evidence](docs/RELEASE_REPORT.md) for actual executed results and limits.

## Scope, history and next work

This local kit does not connect to a bank, take payments, implement hosted ChatGPT
sign-in or process PDF tables natively. Gemini and Resend HTTPS email need your own configuration;
live provider calls and PostgreSQL have not been validated here. Financial data
needs operational backups and a retention policy before real use.

Original hackathon history remains intact. Post-hackathon work restored the separate
store, interrupted-sync recovery and receipt-status checks. This release pass adds
browser/backend status consistency, editable payment status, import regression
coverage, schema alignment, CI and accurate capability documentation.

Roadmap: independently validate hosted source and live integrations, exercise
PostgreSQL concurrency, improve distributed abuse controls and add browser-driven
accessibility and responsive-layout checks. These are future work, not supported
claims. [Portfolio case study](docs/PORTFOLIO_CASE_STUDY.md).

Maintained in `bil332204-code/AiCON-2026-Milaan`; consult Git history for contributors.
Contributions should include synthetic regression cases and preserve the distinction
between evidence matching, name assistance and optional AI extraction.

### PostgreSQL and private receipts

Production preparation now supports psycopg 3 PostgreSQL runtime pooling, direct
Alembic migrations and authenticated private S3-compatible receipt storage. SQLite
and local files remain the default for development. No design or hosted service
was changed. See [Render/Neon configuration and deployment checklist](docs/RENDER_NEON_READINESS.md)
and [the secret-free environment template](deploy/render-neon.env.example). Public
registration stays disabled in that configuration; deployment requires owner approval.

Run `.venv/bin/python scripts/test_postgres_s3.py` for isolated PostgreSQL 17 and
S3 HTTP integration tests using synthetic data; Docker is required.

V4 verification and recovery use Resend HTTPS (no SMTP dependency). See
[the Resend configuration and registration gate](docs/V4_RESEND_EMAIL.md).
