# Validation record

Validated on Python 3.12 with the exact package versions pinned in `requirements.txt`.

## Executed checks

- **29 automated tests passed** using a temporary SQLite database per test fixture.
- Initial Alembic migration executed successfully on a fresh database.
- `alembic check` found no difference between the migrated schema and current models.
- All table definitions compiled successfully for the PostgreSQL dialect.
- The shipped JavaScript API client passed Node syntax checking and was exercised against a real Uvicorn server over HTTP.
- That HTTP workflow covered account creation, login/logout, synthetic batch creation, built-in background-worker execution, job polling, results, content persistence, and CSV export.
- The server was stopped and started again against the same temporary database. Saved account, reconciliation results, and edited content remained available.
- The synthetic demo produced the expected **12 orders: 5 Ship, 2 Hold, 5 Review**.

Automated tests cover owner isolation, authenticated image access, stale edit versions, double-use credit prevention across retained batches, input locking after reconciliation, reset/re-run, formula-safe export, invalid uploads, request size limits, retention deletion, interrupted-job recovery, content versions, strict money/date parsing, conservative matching, extraction consent, provider-output validation, provider timeout handling, and extraction retries.

## Limits of this validation

- No live Gemini key was available. Provider request shape, structured parsing, disagreement handling, and errors were checked using mocked responses. Validate a real model call with your account before relying on cloud extraction.
- Docker and PostgreSQL servers were not available in the build environment. Their configuration and schema compilation are included, but runtime PostgreSQL locking/deployment was not exercised here.
- The existing hosted cinematic website was not modified or connected by this ZIP. Its integration is documented and the included API client was exercised, but its existing visual components still need the described wiring.
- The development console's JavaScript and API flow were checked; no cross-browser visual audit was performed.
- One test dependency emits a deprecation notice about Starlette's `httpx` test adapter. It did not fail any tests; the locked combination executed successfully.

These checks establish a working local backend and integration path. They are not a security certification, provider accuracy benchmark, load test, or bank-connection verification.
