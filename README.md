# Milaan — payment evidence reconciliation

AiCON 2026 — Build With AI. Milaan helps sellers compare orders, receipt evidence
and receiving-bank exports, producing explainable **SHIP / HOLD / REVIEW**
recommendations. These are operational recommendations based on supplied evidence;
they do not independently confirm bank settlement or execute payments or shipping.

[Hosted workspace](https://milaan-studio.bil332204.chatgpt.site/workspace) ·
[Hosted guide](https://milaan-studio.bil332204.chatgpt.site/guide) ·
[Portfolio](https://bilal-ahmed-builds.cyou/projects/milaan)

## Hosted workspace versus this repository

The Sites application is separately maintained. Hosted capabilities below are
previously documented claims, **not independently verified in this release pass**.
Changing this repository does not update that application.

| Capability | Hosted workspace (unverified claims) | GitHub local kit (source and local tests) |
|---|---|---|
| Authentication | ChatGPT sign-in | Email/password; revocable bearer sessions; SMTP verification or configured demo operator |
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
.venv/bin/python -m pip install -r milaan/backend/requirements.txt
.venv/bin/python setup_admin.py
cd milaan/backend
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from `demo-store`, run
`../.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8090`.
Use your configured operator in both applications. No Node build is required.
Python 3.13 and Windows execution remain unverified.

## Demonstration scenarios

| Synthetic scenario | Expected result |
|---|---|
| Correct payment | SHIP / EXACT_MATCH |
| Missing credit | HOLD / NOT_FOUND |
| Wrong amount | REVIEW / AMOUNT_CONFLICT |
| Reused proof | REVIEW / REUSED_PROOF |
| Pakistani name variation | REVIEW / POSSIBLE_MATCH |

[Five-minute demo](docs/DEMO.md) · [Roman Urdu guide](DEMO_GUIDE_ROMAN_URDU.md).

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
sign-in or process PDF tables natively. Gemini and SMTP need your own configuration;
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
