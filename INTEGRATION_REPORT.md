> **Historical integration report.** Windows launch was subsequently tested in CI and the Resend HTTPS mail adapter was exercised via a staged inbox test. Earlier “not verified” statements remain dated observations. See [README](README.md).

# Integration report — separate demo kit

## Completed

- Restored the original cinematic receipt-checking frontend from the backup inside the supplied Hackathon archive.
- Removed public store, marketplace, cart, checkout and product routes from Milaan's API. Product tables/migration history remain to avoid breaking existing schema history; no marketplace UI is served by Milaan.
- Kept core authentication, email verification logic, CSV uploads, private receipt storage, extraction, background reconciliation, review decisions, audit trail and results export.
- Preserved the uploaded AiCON `matching` source and its Pakistani-name similarity integration. Heavy ML imports are lazy so the active name matcher does not depend on an unused training stack.
- Displayed AiCON name-similarity evidence in Milaan's order review and in the separate store results.
- Added a separate FastAPI demo shop with its own SQLite database, seller connection, server-calculated product totals, generated marked demo receipts, simulated bank CSVs, and authenticated API synchronization.
- Added fixture mode and receipt-reading mode. Fixture mode explicitly provides known receipt fields; receipt mode waits for Gemini/manual checking.
- Added Windows setup/start scripts and private operator configuration. Removed shared default operator credentials.
- Used one same-origin Milaan service for API and frontend, plus a separate store service. No frontend compilation required.

## Verified here

Environment: Linux, Python 3.12.14. Core dependency versions are recorded in `milaan/backend/requirements.txt`.

| Check | Result |
| --- | --- |
| Core backend tests | 43 passed |
| Preserved AiCON name/rule tests | 25 passed |
| Frontend engine/state tests | 19 passed |
| Interrupted-sync recovery tests | 5 passed (lost responses after orders, statement, receipt, confirmation and job submission) |
| All Milaan frontend scripts + store JS syntax | Passed |
| Fresh Alembic database migration | Passed |
| Live HTTP test: correct payment | Ship / EXACT_MATCH |
| Live HTTP test: missing credit | Hold / NOT_FOUND |
| Live HTTP test: amount mismatch | Review / AMOUNT_CONFLICT |
| Live HTTP test: reused receipt | Both orders Review / REUSED_PROOF |
| Live HTTP test: Pakistani name variant | Review / POSSIBLE_MATCH with AiCON evidence |
| Receipt-reading mode | Upload → human confirmation → reconciliation → SHIP verified over live HTTP; no premature result |
| Unauthenticated store receipt access | Rejected (401) |
| Milaan frontend served by its API process | HTTP 200 |

Live integration tests use fresh temporary databases and launch two real HTTP servers. They do not use your credentials, SMTP or Gemini account.

Reproduce from an activated environment:

```sh
cd milaan/backend
python -m pytest tests matching/tests
cd ../..
python tests/live_demo_check.py
node --test milaan/frontend/tests/*.test.mjs
```

## Boundaries

- Payment and bank records are simulated; the store-to-Milaan API connection and reconciliation are real.
- Gemini API calls, SMTP delivery, Windows batch execution, Python 3.13 runtime, and full visual browser interaction were not verified in this environment.
- AiCON's **name similarity** is active. The uploaded ML training/scoring source is preserved but is not the production reconciliation decision engine. Binary model artifacts are not included or loaded; other teammates' modules still need integration.
- This delivery does not claim full Module 4 split/combined payment, subset-sum, refund/reversal or delayed settlement support. It restores the requested separation and provides a test harness for the currently active matching logic.
- Manual review continues to use Milaan's existing audit workflow; no new ML feedback trainer is activated.
- The store is a localhost demonstration harness. It is not hardened public ecommerce hosting; no payment collection, shipping or real-bank integration is present.
- No domain or public deployment was changed. Local files and database start fresh; your original uploaded archive is preserved.
- Existing inherited docs in subfolders describe the older standalone backend/frontend. Follow the root README_FIRST.md for this kit.

## Next modules / deployment

Keep new matching modules under the Milaan backend. Give them normalized order, statement and checked-claim inputs; return recommendations/evidence without bypassing allocation and ownership checks. The store should continue calling the same API boundary.

For domain deployment, run Milaan and the demo store as separate services with persistent volumes, TLS and explicit environment configuration. Milaan's existing deployment notes cover the core API; the new store needs secure cookies, deployment access controls and a deployed smoke test before public exposure. Purchase/connect the domain during the planned deployment stage.

## 12 October stabilization

- Retry interrupted store sync in the original batch; inspect committed remote stages before uploading, and reuse the reconciliation idempotency key.
- Show a Retry sync button after an interrupted upload, including after a store restart.
- Missing or unrecognized receipt payment status requires Review instead of automatic Ship.
- Backend connection failures return a clear retryable error.
- Original hackathon history is retained on main; this corrected kit is published on post-hackathon.
