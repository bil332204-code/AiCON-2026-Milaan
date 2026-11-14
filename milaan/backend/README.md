# Milaan backend

FastAPI app that serves the website and the API. Setup, tests and production settings are in the root [README](../../README.md).

| Module | Purpose |
|---|---|
| `app/main.py` | Routes: auth, batches, orders, statements, receipts, jobs, results, decisions, public pages |
| `app/statement_pdf.py` | Reads bank and wallet statement PDFs into rows for the seller to check (nothing is saved until they import) |
| `app/parsing.py` | CSV parsing and validation for orders and statements |
| `app/matcher.py` | SHIP / HOLD / REVIEW rules |
| `app/allocations.py`, `app/allocation_review.py` | One credit can't pay for two orders unless the seller splits it explicitly |
| `app/extraction.py` | Optional Gemini screenshot reading (only when the seller asks) |
| `app/emailer.py` | Verification and password-reset email through Resend |
| `app/storage.py` | Screenshot storage (local in development, private S3 in production) |
| `app/demo.py` | Sample shop batch for signed-in users |
| `migrations/` | Alembic migrations |

API reference: run the server and open `/docs`, or see [docs/API.md](docs/API.md). Statement and order import rules: [docs/IMPORT_CONTRACTS.md](../../docs/IMPORT_CONTRACTS.md).

`POST /api/statements/read-pdf` (signed in) accepts a statement PDF up to 10 MB / 60 pages and returns `rows` (`posted_at`, `direction`, `amount`, `counterparty`, `transaction_id`, `needs_check`), the detected `period`, `account_hint` and `warnings`. The browser shows these to the seller, then imports the confirmed rows through the normal `POST /api/batches/{id}/statement` validation.
