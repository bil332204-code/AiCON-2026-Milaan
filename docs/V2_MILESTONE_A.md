# Milaan V2 — Milestone A

Prepared from main `f62a2bf` (PR #2 merged), on `feat/milaan-v2`.
No hosted Sites application, production deployment or matching/allocation rules were changed.

## Reviewed imports

Choose an orders or statement CSV in the existing Import center. A modal opens
before anything is uploaded. Canonical header names are mapped automatically;
other bank column names can be mapped manually. No bank-format guessing or
transaction fabrication occurs. Unknown columns are omitted only through the
visible mapping; inspect it before confirming.

The preview shows accepted/rejected record counts, errors with record numbers,
blank-reference warnings and repeated-credit-reference warnings. Up to 20 normalized
records and 100 issues are displayed; **every record is validated**. Any rejected
row blocks the entire import. Fix the source or mapping and retry; partial saving
and silent row dropping are not supported. Malformed CSV, invalid UTF-8, excessive
rows or oversized data fail before saving. Both original and normalized CSV are
limited to 2,000,000 bytes and 2,000 rows.

Statements require explicit receiving account and start/end coverage in the existing
form. Choose whether coverage is complete and whether sender/receiver references
correspond. The preview requires a separate explicit review confirmation; incomplete
coverage remains incomplete and cannot yield automatic SHIP. Changing mappings or
timezone clears that confirmation. Existing ISO offsets are preserved; timestamps
without offsets use the explicitly displayed Asia/Karachi default or selected UTC.
Bank-specific date formats and debit/credit labels must be normalized explicitly.

Blank reference cells in a mapped reference column remain blank in saved mode;
no identifier is generated. Browser-local mode continues to require nonempty
references and displays an error instead of silently changing that contract.
Cancel or Escape closes the modal without uploading. The original file stays in
browser memory during review. Keep your source evidence privately outside the app.
No PDF extraction or third-party processing is introduced.

## Provenance and security

The same existing authenticated, version-checked import endpoints revalidate and
commit all records atomically. Optional bounded `provenance` JSON records a
**client-declared** SHA-256 of the original file, the chosen column mapping and
source timezone in the private batch audit. The server separately computes the
SHA-256 of the normalized CSV it received. A fingerprint is not source authenticity
or bank verification. Raw originals are not duplicated into server storage; their
financial contents and source metadata are not written to application logs.

No database migration is needed: provenance uses the existing private audit JSON.
Audit events expire with their batches under the existing retention policy.
Formula-like evidence stays unchanged during import; rendered preview cells are
escaped, and existing CSV exports still neutralize formulas. Invalid provenance
cannot bypass validation or create records. Existing ownership, session, revision,
image, uniqueness and retention protections remain active.

## Workspace usability

Results can be searched by customer, order or receipt/candidate transaction reference,
and filtered by verdict plus discrepancy reason code. Existing summaries, evidence
comparison, job progress, human decisions and audit history are retained. Filters
reset when loading another batch. The account-change handler now updates coverage
controls in place instead of replacing the next focused input. The import dialog
supports keyboard dismissal, labeled controls, explicit save enablement, live
summary announcements and a horizontally scrollable table on narrow screens.

## Actual validation

Linux, Python 3.12.14, Node 24.19.0, local Chromium via `/usr/bin/chromium`:

- `cd milaan/backend && ../../.venv/bin/python -m pytest tests matching/tests`:
  **82 passed**, including provenance privacy and atomicity regressions.
- `.venv/bin/python -m pytest tests/test_store_sync.py tests/test_migrations.py`:
  **6 passed**.
- `node --test milaan/frontend/tests/*.test.mjs`: **29 passed**.
- `BROWSER_EXECUTABLE=/usr/bin/chromium npm --prefix tests/browser test`:
  **4 passed** (two workflows each on desktop 1440×1000 and mobile 390×844).
- `.venv/bin/python tests/live_demo_check.py`: all five store scenarios and
  manual confirmation → SHIP → human HOLD → private CSV export passed.
- Frontend syntax, Python compilation, dependency consistency and `git diff --check`
  passed. Earlier schema round-trip regression remains green.

Browser workflows perform actual login (including bad-password errors), batch
creation, reviewed orders and mapped bank imports, receipt upload/manual confirmation,
reconciliation, reference search, discrepancy filtering, HOLD/REVIEW decisions,
private export, audit inspection and logout. They also verify rejected-row blocking,
repeated-reference warnings and Cancel/Escape without saving. The mobile test checks
page overflow. A new browser assertion initially exposed the account/coverage focus
bug; it passes after the handler correction. There are no skipped browser tests.

Existing Starlette/httpx TestClient deprecation warnings remain. GitHub-hosted CI
has been configured but no remote passing run is claimed.

## Genuine screenshots

These are generated by Playwright against the local synthetic test server:

| Desktop | Mobile |
|---|---|
| [Mapped import](screenshots/import-desktop.png) | [Mapped import](screenshots/import-mobile.png) |
| [Reconciliation results](screenshots/results-desktop.png) | [Reconciliation results](screenshots/results-mobile.png) |

They contain synthetic data only. They are not screenshots of the hosted website.

## Reproduce

Install backend dependencies using README_FIRST. Then from repository root:

```sh
npm --cache /tmp/milaan-npm-cache --prefix tests/browser ci
cd tests/browser
npx playwright install chromium
cd ../..
npm --prefix tests/browser test
```

If a compatible system Chromium is installed, use
`BROWSER_EXECUTABLE=/usr/bin/chromium npm --prefix tests/browser test` instead of
downloading a browser. The runner uses root `.venv/bin/python`; set
`MILAAN_TEST_PYTHON=python` for a configured system interpreter (as in CI).
It launches a dedicated server on port 8765, temporary database and upload directory,
and a fixed synthetic-only test operator. It never uses an existing server or user
DB. Reserve that port. Real production credentials are neither needed nor supported
by these tests. Traces retained on failure contain only synthetic test records.

## Remaining scope

Advanced partial/split/combined allocation, under/overpayments, refund/reversal
reasoning and delayed-settlement changes belong to **Milestone B**, a separate PR.
They have not been implemented or claimed here. Native PDF extraction remains
unsupported. UTC/Asia-Karachi defaults and explicit ISO offsets are supported;
arbitrary bank date syntax, saved mapping presets, partial import acceptance and
additional browsers remain future work. Live Gemini, SMTP, PostgreSQL, Windows
and the separately hosted application were not validated in this milestone.

Milestone A is ready for review. Per the requested delivery order, Milestone B must
wait until this milestone's PR has been created. No automatic merge or deployment.
