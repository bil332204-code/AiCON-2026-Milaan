# Deployment and operations

## Supported starting point

One API process + its built-in worker + local SQLite is the tested local configuration. For a server, the package includes PostgreSQL and persistent-volume Docker configuration. Run migrations once per release before serving traffic. The Docker command does this automatically for the single API container in `compose.yaml`.

To scale API processes, disable their built-in workers and run a dedicated `python -m app.worker` process against the same PostgreSQL database and protected receipt volume. The queue is SQL-backed; Redis is not required. Multiple hosts need genuinely shared storage. No S3 service or cloud account is provisioned by this ZIP.

## Required deployment settings

1. Terminate HTTPS at your hosting platform or reverse proxy. The included local bind avoids exposing an unsecured development server directly.
2. Keep `.env`, database credentials, and Gemini keys server-side. Use hosting secrets for a deployed environment.
3. Set exact `CORS_ORIGINS` to the frontend domain(s). No wildcard.
4. Set `BATCH_RETENTION_HOURS` deliberately. It affects new batches. Account/content retention is separate.
5. Run a worker continuously so extraction, matching, and expiry cleanup execute. `python -m app.worker --cleanup` performs one cleanup pass.
6. Set `ALLOW_REGISTRATION=false` after pilot accounts are created if public self-registration is unwanted. `ENABLE_DEMO=false` disables synthetic batch creation.
7. Back up database and receipt files together if retained data must survive host loss. Keep backup expiry aligned with your actual retention commitments.

## Controls implemented

Passwords are salted and hashed with scrypt; session tokens are random and stored only as hashes. Private API paths check owner and expiry. Uploaded receipts are decoded, metadata-stripped, capped in size/pixels, and served only after authentication. The application does not publish the receipt directory. Input errors and provider failures are sanitized.

Money uses integer paisa, never floats for matching. Imported account/currency/coverage declarations are validated. Stale writes require reloading. Credit allocation is transactional with uniqueness constraints. Exports escape spreadsheet formula prefixes. CORS is explicit and responses use no-store caching headers. Login/registration have a basic 15 requests per minute per-process IP limit.

## Work needed before a public multi-tenant service

Email verification and password recovery are not implemented. There is one owner per account, with no invitations or roles. The included auth limiter is process-local and does not trust forwarded IP headers; a deployment behind a proxy should use a correctly configured shared edge rate limiter. Add global traffic/provider-cost quotas, monitoring, tested backup restoration, and an authentication/session design suited to your hosting setup.

The activity log is an application audit trail; a database administrator can edit it. It is not an immutable compliance ledger. SQLite files and receipt files are not encrypted by this application; use protected encrypted storage if required by the deployment.

Gemini is an optional external processor. Display the actual data-sharing behavior before extraction and configure provider retention/terms appropriately for your use. Two reads cost roughly twice one extraction, and retries can add calls. Provider pricing and quotas come from your own account.

This backend cannot assert that an uploaded statement or screenshot is authentic. It performs reconciliation on supplied records. A human can deliberately override Review after inspecting evidence; that decision and reason are retained.

## Troubleshooting

| Symptom | Fix |
|---|---|
| “Database is not migrated” | Run `python -m alembic upgrade head` with the project environment |
| Browser fetch blocked | Verify backend URL, HTTPS compatibility, exact origin in CORS, then restart |
| 401 | Log in again; do not keep using an expired token |
| 409 on an input edit | Wait for active job; if results exist, reset explicitly; fetch current version |
| Job remains queued | Start the built-in or standalone worker |
| Interrupted job stays running briefly | Lease recovery occurs after five minutes |
| Extraction returns 503 | Set provider, API key, and supported model ID on the server |
| Job done but unreadable receipt | Inspect claim status/reads; manually correct or request retry |
| Several screenshots fail provider calls | Check your account's model access, quota, and outbound HTTPS connection |
| PostgreSQL URL parsing error | Percent-encode special characters in credentials; Compose example recommends alphanumeric password |
| Upload reaches 413 | Reduce file/request size; each image is uploaded separately |

## Implementation references

- FastAPI documentation: https://fastapi.tiangolo.com/
- SQLAlchemy sessions: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- Alembic migrations: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Gemini generateContent REST: https://ai.google.dev/api/generate-content
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
