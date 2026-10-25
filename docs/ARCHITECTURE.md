> **Evidence update:** The earlier untested-PostgreSQL statement below is historical: later CI includes isolated PostgreSQL/S3 synthetic integration. See [current operations](OPERATIONS_RUNBOOK.md); hosted database provider behavior is not established by local tests.

# Implemented local architecture

```mermaid
flowchart TD
  UI[Static browser UI] -->|Saved batches / bearer API| API[FastAPI app.main]
  UI -->|Browser-local illustrative mode| JS[engine.js deterministic matcher]
  Store[Separate simulated store :8090] -->|Authenticated API calls| API
  API --> Auth[Password hashing / expiring revocable sessions]
  API --> CSV[Normalized orders and statement CSV]
  API --> Images[Private sanitized receipt images]
  API --> Queue[Persistent jobs / worker lease recovery]
  Queue --> Match[app.matcher deterministic matching]
  Match --> Names[Pakistani name similarity candidates]
  Queue -->|Explicit consent, configured provider| Gemini[Optional Gemini image extraction]
  API --> Review[Versioned human review / CSV export]
  API --> DB[(SQLite local database)]
  Queue --> DB
  Queue --> Retention[Expiry cleanup / private file removal]
```

Canonical entry points: `milaan/backend/app/main.py:app`,
`demo-store/server.py:app`, `milaan/frontend/dist/app.js`.
The active saved matcher is `app/matcher.py`; `matching/names.py` supplies name
similarity. Other matching utilities do not replace the saved engine.
PostgreSQL configuration exists for shared deployments but was not runtime-tested
in this release pass. SQLite is the verified single-machine development path.

The separately hosted Sites workspace has no verified shared database, source,
synchronization or deployment pipeline with this checkout. Repository changes do
not deploy it. Its internal architecture and retention remain unverified.


V2 adds `app/allocation_review.py` for atomic human-confirmed payment shares and
`app/allocations.py` for serialized retained-credit budget checks. The worker and
both decision APIs use the same seller lock protocol. Live allocation rows hold
integer-paisa amounts; private `allocation_reviews` records provide idempotent retry
snapshots. No separate bank connection or shared hosted database was introduced.
See [payment allocation design](V2_MILESTONE_B.md).
