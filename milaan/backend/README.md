> **Historical component reference:** Current production email integration uses Resend HTTPS, not SMTP. See [canonical root guide](../../README.md) and [V4 email documentation](../../docs/V4_RESEND_EMAIL.md). Follow this page only for legacy/local setup details.

> Inherited component reference. For this repository, follow [canonical local setup](../../README_FIRST.md); root instructions take precedence. Hosted features are separately maintained and unverified here.

> October 10 update: read UPDATE_GUIDE.md first. New signups now require email verification and SMTP configuration by default. Existing accounts remain usable.

# Milaan backend

A runnable Python backend for matching customer payment screenshots to seller-uploaded statements and orders. It stores accounts, content, batches, receipts, jobs, results, review decisions, and audit events in a real database.

**Start here:** Windows users can run `start.bat`. For a simple Roman Urdu explanation, read [QUICKSTART_ROMAN_URDU.md](QUICKSTART_ROMAN_URDU.md).

## What is included

| Part | Implementation |
|---|---|
| API | FastAPI, interactive `/docs`, exported OpenAPI schema |
| Accounts | Registration, login, logout, hashed passwords, revocable bearer sessions |
| Database | SQLite for local use; PostgreSQL configuration and Docker Compose; Alembic migrations |
| Content APIs | Seller-specific branding, workspace settings, messages, and FAQ JSON |
| Imports | Orders CSV, account-specific statement CSV, JPEG/PNG/WebP receipt uploads |
| Receipt reading | Manual confirmation, or server-side Gemini vision adapter with two reads |
| Background work | Persistent database queue, progress polling, restart recovery |
| Matching | Deterministic rules, evidence, candidate credits, Ship/Hold/Review |
| Review | Version-checked decisions, required reason, atomic credit allocation |
| Export | CSV with both machine verdict and final human decision |
| Data lifecycle | Private image endpoints, explicit deletion, configurable expiry, audit events |
| Integration | Browser JavaScript client, working integration console, endpoint guide, samples |
| Verification | Automated API, access-control, matching, parsing, provider-mock tests |

## Run locally

Tested on **Python 3.12**. Install that version for the most direct setup. Internet is needed once to install packages; manual mode and sample data then run locally.

### Windows

Extract the ZIP, open the `milaan-backend` folder, and run:

```bat
start.bat
```

Or run the same steps in PowerShell without activating the virtual environment:

```powershell
py -3.12 -m venv .venv
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Copy `.env.example` only on the first setup. Keep your configured `.env` on later runs.

### macOS / Linux

```sh
sh start.sh
```

The script creates a virtual environment, installs the pinned dependencies, initializes the schema, and starts the API. It preserves an existing `.env` and database. Use Ctrl+C to stop. Start it again to load saved data.

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health
- ReDoc: http://127.0.0.1:8000/redoc

## See a complete workflow in two minutes

Keep the API terminal open. In a second terminal, from the project folder:

```sh
python -m http.server 8080 --directory integration
```

On Windows, use `py -3.12` instead of `python` if needed. Open **http://localhost:8080**, create an account, then click **Create + reconcile sample**. You should see **12 orders: 5 Ship, 2 Hold, 5 Review**. The console can reload saved batches and download CSV. Demo records are clearly marked synthetic and make no external AI calls.

Alternatively use `/docs`: register, copy `access_token`, click **Authorize**, paste the token without the `Bearer ` prefix, create a demo batch, call reconcile with an `Idempotency-Key` such as `demo-run-0001`, poll the returned job, then load results.

## Connect Gemini for actual image reading

Set these values in the **backend's `.env`** and restart the API:

```dotenv
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=your-own-key
GEMINI_MODEL=your-available-image-and-structured-output-model-id
```

Choose a model available to your Google account that supports image input and structured JSON. The model ID is deliberately configurable. No key is included in this ZIP. The adapter's request/response handling was tested with mocks; a live provider call has not been verified with your account.

For real data: create a batch, import orders and statement, upload each screenshot against its order, then call `/extract` with `consent_to_cloud: true`. Only that explicit call sends images to Google. Poll the job, inspect `extraction_status`, correct uncertain fields, and then reconcile. `done` means the job finished; individual receipts can still be `failed` or `needs_review`.

Without a key, the backend still works: enter the receipt fields through `PATCH /api/claims/{id}` and set `confirmed: true` after checking them. No cloud request is made in manual mode.

Two matching model reads are a consistency check, not proof that the model read the image correctly. The deterministic engine matches those fields against your uploaded statement; it does not consult a bank.

## Connect the existing website

Read [docs/FRONTEND.md](docs/FRONTEND.md). Copy `integration/milaan-api.js` into the frontend and set its backend URL. Replace the browser-local import, extraction, reconciliation, and decision handlers with the documented API calls. The website is not automatically connected simply by running this ZIP.

The hosted frontend will need an **HTTPS backend reachable from the browser** and its exact origin in `CORS_ORIGINS`. A cloud-hosted page cannot use your laptop's private localhost as a shared backend. This package does not deploy the server.

## Data formats

- Monetary API outputs use integer **paisa**: `350000` means PKR `3500.00`. Input amounts are decimal strings.
- Input timestamps require a complete date and time. An absent timezone means `Asia/Karachi`. Responses use UTC with `Z`.
- Only PKR is supported in this version.
- Use one stable `account_id` for the same receiving bank/wallet account across batches. Changing the alias defeats cross-batch credit deduplication.
- Statement CSV must be normalized to the included template. Arbitrary bank PDF layouts and every institution's CSV format are not automatically parsed.
- One screenshot must be explicitly linked to its order. The system does not guess that relationship.

Exact CSV formats and request examples are in [docs/API.md](docs/API.md). Synthetic input files are in `samples/`.

## PostgreSQL and Docker

Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` to a long random string using letters and digits. Then:

```sh
docker compose up --build -d
docker compose logs -f api
```

Compose runs PostgreSQL and the API, with separate persistent database and receipt volumes. The API initializes migrations and runs one background worker thread. Port 8000 binds to localhost; put an HTTPS reverse proxy in front when deploying. Do not run `docker compose down -v` unless you intend to delete the stored database and images.

Alternatively set `DATABASE_URL=postgresql+psycopg://user:password@host:5432/milaan`, percent-encoding special characters in credentials. Run `python -m alembic upgrade head` before starting the API. Docker/PostgreSQL runtime execution was not available in the build environment; SQLite migrations and the application flow were executed. PostgreSQL schema compilation is included in validation.

## Worker and concurrency

For a local demo, `RUN_WORKER_IN_API=true` is enough. For a server with a separate worker:

```dotenv
RUN_WORKER_IN_API=false
```

Run two processes against the **same database and receipt storage**:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.worker
```

Jobs survive a process restart. A running job without a heartbeat for five minutes can be reclaimed. Receipt extraction saves progress after each image. Mutating batch inputs is blocked while a job is active. Credit allocations have database uniqueness constraints: concurrent attempts cannot assign one retained credit twice. A conflicting job can fail safely and be retried with a new idempotency key.

SQLite is intended for a single-machine setup. Use PostgreSQL for multiple processes or a shared deployment. All workers must share the private receipt directory; local files alone do not work across unrelated hosts.

## Retention and decisions

**Default expiry is seven days after batch creation.** `BATCH_RETENTION_HOURS` changes it for new batches. The worker removes expired batches, receipts, jobs, results, allocations, and batch audit records. Accounts and content remain. Expired batches become inaccessible even if the cleanup worker is stopped. This is a configurable working-data store, not a permanent ledger.

Credit reuse protection applies to the seller's **retained** allocations. Explicitly deleting/resetting a batch or letting it expire releases those allocations. Export what you need before expiry; choose an appropriate retention policy before real use.

After reconciliation, input records are locked. To change source data, call `/reset` with the current batch revision and a reason. It releases that batch's allocations and clears current results while retaining the prior run/audit history until deletion or expiry. Reconcile again with a new idempotency key.

## Tests and project layout

```sh
python -m pytest
python -m alembic check
```

Run these using the project virtual environment. `docs/VALIDATION.md` records the checks actually executed for this deliverable.

| Path | Purpose |
|---|---|
| `app/main.py` | Routes, authorization, validation, ownership checks |
| `app/models.py` | Persistent entities and uniqueness constraints |
| `app/jobs.py`, `app/worker.py` | Background queue and expiry cleanup |
| `app/matcher.py` | Explainable matching rules |
| `app/extraction.py` | Server-side Gemini REST adapter |
| `app/parsing.py`, `app/storage.py` | CSV, money, dates, safe image decoding |
| `migrations/` | Versioned database schema |
| `integration/` | Browser client and working API console |
| `docs/` | Architecture, endpoints, frontend wiring, deployment, validation |
| `tests/` | API and rules tests |

## Scope of this delivery

This is a working backend code package for integration and a controlled pilot. Bank/wallet live access, NADRA, payment execution, email/password recovery, multi-member shared workspaces, public CMS publishing, and production hosting are not included. The content API is private and scoped to each seller account. Do not describe Ship as bank verification or Hold as proof of fraud. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the concrete deployment settings and remaining service work.
