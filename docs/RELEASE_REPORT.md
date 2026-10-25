> **Historical report (24 October 2026).** Its “no production deployment” and unverified-provider statements describe that older release session, not the later production launch. See [current operations](OPERATIONS_RUNBOOK.md).

# Release engineering evidence — 24 October 2026

Verdict: **READY FOR REVIEW** for the local kit. No production deployment was made.

## Baseline and scope

Fetched origin main and post-hackathon. Local HEAD and fetched main both began at
`3ea77f34a7e9ee6e7749eed3d798f27e8770d87e`. Ancestry checks confirmed
9cde5cb, d5cc8d1, b0f8c09 and 0f514e5 are included. Work is on
`fix/milaan-release`; original history was not rewritten.

Priority findings: unsafe browser automatic SHIP without payment status; missing
saved-mode status editing; migration/model uniqueness drift; misleading mixing of
hosted claims and local capabilities. These were repaired. Browser CSV byte size
was also corrected to measure UTF-8 bytes rather than UTF-16 character count.

## Actual local checks

Linux, Python 3.12.14, Node 24.19.0, repository virtual environment:

| Command (working directory) | Actual outcome |
|---|---|
| `python3 -m venv .venv`; `.venv/bin/python -m pip install -r milaan/backend/requirements.txt` (root, environment setup) | Passed |
| `../../.venv/bin/python -m pytest tests matching/tests` (backend) | 80 passed |
| `.venv/bin/python -m pytest tests/test_migrations.py tests/test_store_sync.py` (root) | 6 passed |
| `node --test milaan/frontend/tests/*.test.mjs` (root) | 21 passed |
| `npm --prefix milaan/frontend run check` (root) | Passed |
| `.venv/bin/python tests/live_demo_check.py` (root) | Five expected scenario outcomes; manual confirmation → SHIP → saved human HOLD → private CSV export passed |
| `python -m alembic upgrade head`; `python -m alembic check` (backend virtualenv) | Passed; no schema drift |
| Temporary SQLite upgrade → downgrade to 20261010_marketplace → upgrade → check | Passed |
| Migration test with existing synthetic product | Row retained, uniqueness retained for both indexed columns, duplicate SKU rejected |
| `.venv/bin/python -m pip check` (root) | No broken requirements |
| `.venv/bin/python -m compileall -q milaan/backend/app demo-store/server.py tests` (root) | Passed |
| Local HTTP health, HTML, store catalog and status | Passed during setup |
| `git diff --check` | Passed |

Total: **107 automated tests passed**, plus functional HTTP assertions. No skipped
or expected-failure tests in these runs. The new status test was run before the fix
and failed because an undefined status produced SHIP; it passed after correction.
The initial Alembic check failed on legacy uniqueness representation; the new
forward migration resolves that drift without changing historical migrations.
Starlette emits an httpx TestClient deprecation warning; tests still execute.

Existing tests cover ownership and private receipts, session revocation, stale
versions, retained cross-batch credit reuse, idempotency, reset, retention, invalid
uploads and interrupted workers. Extended tests exercise manual reconciliation
after a mocked unavailable provider, import limits, encoding and normalization.
Migration upgrades/downgrades preserve synthetic data; production backups remain
necessary. Tests do not establish PostgreSQL multi-process concurrency behavior.

## Remaining verification and delivery limits

- Hosted Sites source, live hosted behavior, portfolio editing and deployment were
  not accessed or changed. Hosted PDF limits and other claims remain unverified.
- Live Gemini, SMTP, PostgreSQL, Python 3.13 and Windows batch execution remain
  unverified. The Windows setup now selects verified Python 3.12 first.
- Interactive operator configuration was inspected, not driven with a user's
  private login. Synthetic operator login is exercised by live HTTP tests.
- Browser UI changes passed syntax and engine tests, not full browser-driven
  interaction, accessibility or responsive-layout checks.
- GitHub Actions is configured; local equivalents were executed. A remote green
  workflow run is not claimed. No merge or production release is authorized by
  these results alone.
- No bank integration, native local PDF import, hosted ChatGPT authentication or
  guaranteed settlement verification was implemented.

## Documentation and security review

Reviewed application entry points, matcher and parsing rules, job leases and cleanup,
private storage, authentication middleware and existing security/API regression
coverage. No real financial records were used or added. `.env`, databases and
private uploads stay ignored. Authentication rate limiting is single-instance;
public deployments still need HTTPS and appropriate operational controls.

Canonical setup is README_FIRST.md. See IMPORT_CONTRACTS.md, PRIVACY.md,
ARCHITECTURE.md, DEMO.md and PORTFOLIO_CASE_STUDY.md for source-backed scope.
