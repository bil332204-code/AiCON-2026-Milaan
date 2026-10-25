# API contract

Base URL: `http://127.0.0.1:8000`. Interactive requests: `/docs`. Machine-readable contract: `/openapi.json` and the bundled `docs/openapi.json`.

All endpoints except health, registration, login, and documentation require `Authorization: Bearer <access_token>`. Session lifetime defaults to 12 hours. Logout revokes the current session. There are no default passwords or seeded user accounts.

## Endpoint map

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Process/database health |
| POST | `/api/auth/register` | Create account and session |
| POST | `/api/auth/login` | Create session |
| GET | `/api/auth/me` | Current account |
| POST | `/api/auth/logout` | Revoke current session |
| GET | `/api/integrations/status` | Provider configuration status; never keys |
| GET | `/api/content` | Branding, workspace, messages, FAQ |
| PUT | `/api/content/{key}` | Replace one owner's versioned content value |
| GET / POST | `/api/batches` | List / create batch |
| POST | `/api/batches/demo` | Create a synthetic 12-order dataset |
| GET / DELETE | `/api/batches/{id}` | Read / delete a batch and its data |
| POST | `/api/batches/{id}/reset` | Unlock inputs and release current allocations |
| GET / POST | `/api/batches/{id}/orders` | List / upload orders CSV |
| POST | `/api/batches/{id}/orders/item` | Add one order as JSON |
| PATCH | `/api/orders/{id}` | Edit one order |
| GET | `/api/batches/{id}/statements` | List imported statements |
| POST | `/api/batches/{id}/statement` | Import one account's statement CSV |
| GET | `/api/statements/{id}/lines` | Paginated statement rows |
| DELETE | `/api/statements/{id}` | Remove statement before reconciliation/reset |
| GET / POST | `/api/batches/{id}/claims` | List / upload linked receipt image |
| PATCH / DELETE | `/api/claims/{id}` | Correct fields / delete receipt |
| GET | `/api/claims/{id}/image` | Authorized image bytes |
| POST | `/api/claims/{id}/retry-extraction` | Mark one uploaded claim pending again |
| POST | `/api/batches/{id}/extract` | Queue Gemini extraction with consent |
| POST | `/api/batches/{id}/reconcile` | Queue deterministic matching |
| GET | `/api/jobs/{id}` | Poll progress and state |
| GET | `/api/batches/{id}/results` | Current rows, candidates, evidence, counts |
| POST | `/api/matches/{id}/decision` | Persist reviewer decision |
| GET | `/api/batches/{id}/export.csv` | Download final results |
| GET | `/api/batches/{id}/audit` | Paginated batch audit events |

List pagination uses `limit` and `offset` where offered. Batch limit is 100 per request; statement lines and audit events allow up to 500. Orders/claims are bounded by batch limits instead.

## Authentication and content

`POST /api/auth/register`:

```json
{"email":"you@example.com","password":"choose-a-long-private-password","display_name":"Bilal"}
```

Response contains `access_token`, `token_type`, `expires_at`, and `user`. Login requires `email` and `password`. Passwords preserve their exact whitespace. Do not log credentials or tokens.

`GET /api/content` returns each key as `{ "value": {...}, "version": 0 }` until it is saved. `PUT /api/content/branding`:

```json
{"expected_version":0,"value":{"product_name":"Milaan","tagline":"Every payment, in its place."}}
```

PUT replaces the whole value; merge with the previous value in the client if editing only one field. These APIs are private per-account settings, not public CMS endpoints. Render untrusted content as text, not raw HTML.

## Orders

`POST /api/batches` accepts `{"name":"Friday orders"}` and returns a batch with `id` and `revision`.

CSV import uses multipart form fields `file` and `expected_revision`:

```csv
order_ref,customer_name,amount_due,account_id,currency
ORDER-01,Ali,3500.00,wallet-main,PKR
```

For one JSON order, call `/orders/item` with those same field names and a string amount. The response is `{ "batch": {...}, "order": {...} }`. Orders CSV returns `items` instead of `order`. PATCH requires all order fields plus `expected_revision`. Editing an order also invalidates confirmation of its linked receipts.

Keep the returned batch revision after each input mutation. A stale revision returns 409; fetch current state before retrying. Orders CSV import is initial-only. Subsequent additions use `/orders/item`; edits use PATCH. There is no per-order delete endpoint in this version—remove the batch and recreate it if needed.

## Statement import

CSV columns:

```csv
posted_at,direction,amount,counterparty,transaction_id,account_id,currency
2026-10-09T14:22:00+05:00,CREDIT,3500.00,Ali,TXN123456,wallet-main,PKR
```

Required columns are `posted_at,direction,amount,counterparty,transaction_id`. `account_id` and `currency` may be omitted when the form's account and PKR apply. Empty references are allowed, but cannot auto-Ship. Use positive amounts with explicit CREDIT/DEBIT. Duplicate source rows are rejected. A reference reused by different credit rows forces Review.

Send multipart form:

| Field | Example | Meaning |
|---|---|---|
| `file` | `statement.csv` | UTF-8 normalized CSV |
| `expected_revision` | `2` | Current batch revision |
| `account_id` | `wallet-main` | Stable receiving-account alias |
| `coverage_start` | `2026-10-09T08:00:00+05:00` | Declared period start |
| `coverage_end` | `2026-10-09T20:00:00+05:00` | Declared period end |
| `complete` | `true` | Seller confirms full period/account coverage |
| `references_verified` | `true` | Seller has verified sender/receiver reference correspondence |
| `provider_pair` | `wallet-to-wallet-tested-profile` | Descriptive profile label |

The two flags default to false. Do not silently set them true in a frontend. They require factual confirmation for that imported source. Only one statement per account per batch is supported; delete/reimport before reconciliation, or reset first if results exist.

## Receipts and extraction

Receipt upload is multipart: `file`, `order_id`, `expected_revision`. Accepted formats: JPEG, PNG, WebP. The API checks decoded pixels, removes EXIF metadata, resizes to at most 2400 pixels per edge, and stores a JPEG privately. Limits: 10 MiB image, 25 million pixels, 100 receipts per batch; total HTTP request limit 12 MiB. CSV files are limited to 2 MB and 2,000 rows.

To save manually checked receipt fields:

```json
{
  "expected_version":1,
  "confirmed":true,
  "fields":{
    "is_payment_receipt":true,
    "provider_app":"SYNTHETIC SAMPLE",
    "amount_pkr":"3500.00",
    "datetime_local":"2026-10-09T14:22:00+05:00",
    "transaction_id":"TXN123456",
    "sender_name":"Ali",
    "receiver_hint":"wallet-main",
    "status_text":"Successful",
    "unreadable_fields":[]
  }
}
```

Claim versions are separate from batch revisions. `confirmed: false` saves uncertain fields without allowing automatic matching. No confidence percentage is invented.

`POST /api/batches/{id}/extract` needs:

```http
Idempotency-Key: extraction-attempt-0001
Content-Type: application/json
```

```json
{"consent_to_cloud":true}
```

Provider configuration is required. Extraction queues only `pending` claims. To retry a failed image, call `/api/claims/{id}/retry-extraction` with `{"expected_version":2}`, then enqueue extraction with a new key and consent. Inspect each claim's two reads and status after completion. Synthetic claims have no image and cannot be sent for extraction.

## Jobs and reconciliation

`POST /api/batches/{id}/reconcile` requires `Idempotency-Key` (8–100 characters), with no JSON body. It needs orders and at least one statement row. Poll the returned job ID until `status` is `done` or `failed`. States: `queued`, `running`, `done`, `failed`. The job exposes `progress`, `total`, and a sanitized `error`.

Network retry of the same submission must reuse its key. A new operation needs a new key. Keys are scoped to batch + job kind. A repeated completed key returns its original job even after a later reset. It does not create a new reconciliation.

Results return:

```json
{"batch":{"id":"...","revision":5},"summary":{"orders":1,"ship":1,"hold":0,"review":0},"items":[]}
```

Each actual item includes the order, claim, machine verdict, final status, reason code/text, evidence, candidates with `available`, selected line ID, and match version. Render `final_status` as the current operational decision while preserving `machine_verdict` for explanation.

Human decision request:

```json
{"expected_version":1,"decision":"ship","statement_line_id":"candidate-credit-id","reason":"Compared full reference and amount with original statement"}
```

Ship requires a valid candidate with the right account/amount and no existing allocation. Hold or Review can omit `statement_line_id`. A reviewer cannot overwrite a newer decision: stale versions return 409. After any decision, reload results to refresh candidate availability and counts.

## Errors

| Status | Meaning / client action |
|---|---|
| 401 | Sign in again; session missing, expired, or revoked |
| 403 | Feature disabled by server settings |
| 404 | Object absent, expired, or not owned by this user |
| 409 | Stale version, active job, locked results, duplicate key, or allocation conflict; reload |
| 413 | HTTP request exceeds limit |
| 422 | Invalid input; show returned detail |
| 429 | Per-process login/registration rate limit reached |
| 503 | Gemini not configured for an extraction request |

Validation errors contain field locations/messages without echoing raw request values. Provider errors do not expose keys or receipt payloads.


## V3 browser sessions and recovery

Existing bearer clients remain supported; login/register/verify-email default to
`session_mode: "bearer"`. The integrated browser explicitly selects `"cookie"`.
Cookie replies omit `access_token`, set an HttpOnly host cookie, and return CSRF
material. `GET /api/auth/session` restores the current user and CSRF material after
refresh. Send credentials and `X-CSRF-Token` for unsafe cookie-authenticated requests.
Same-origin HTTPS is the recommended production path; do not persist credentials
in localStorage. `POST /api/auth/logout-all` revokes every user session.

`POST /api/auth/request-password-reset` accepts email and returns a uniform message.
Only verified emails are eligible. `POST /api/auth/reset-password` accepts a one-time
`token` and new `password`; success revokes all sessions and requires login again.
Legacy local accounts retain password access and may confirm their email using
`POST /api/auth/verify-account-email/start` followed by authenticated
`POST /api/auth/verify-account-email` with challenge_id/code. Guest verification
cannot consume an authenticated-account challenge. Source schema and ownership
remain unchanged. Read the [V3 deployment guide](../../../docs/V3_DEPLOYMENT.md)
for cookies, migrations and the separately hosted identity boundary.

Transactional email now uses Resend HTTPS with server-only `RESEND_API_KEY` and
`EMAIL_FROM`. Production registration requires explicit `EMAIL_DELIVERY_VERIFIED=true`
after authorized live delivery checks; keep `ALLOW_REGISTRATION=false` meanwhile.
Provider failures never expose response bodies; recovery retains its generic response.
See [V4 Resend email](../../../docs/V4_RESEND_EMAIL.md).
