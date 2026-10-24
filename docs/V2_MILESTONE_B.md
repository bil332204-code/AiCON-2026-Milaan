# Milaan V2 — reviewed payment allocation

Milestone B starts from `dab89b3`, the merge of PR #3 (Milestone A), on
`feat/milaan-v2-reconciliation`. This is local-kit development, not a hosted Sites
deployment. Recommendations still depend on supplied evidence and never prove
bank settlement or perform shipping, payments or refunds.

## Working behavior

| Evidence | Machine result | Explicit review workflow |
|---|---|---|
| Single receipt and matching full credit for order total | Existing conservative EXACT_MATCH behavior | Existing individual decision supported |
| Multiple confirmed receipt-linked credits totaling one order | REVIEW / SPLIT_PAYMENT | Select each source receipt, credit and share; only exact full funding can become human SHIP |
| Checked source payment below order total | REVIEW / UNDERPAYMENT | Reserve received shares; outstanding amount remains in REVIEW |
| Receipt-linked credit larger than order | REVIEW / OVERPAYMENT | Allocate at most the order total; leave excess unassigned |
| Larger credit may cover two order totals | REVIEW / COMBINED_PAYMENT proposal | Explicitly confirm shared purpose and per-order amounts in one atomic plan |
| Reversed/refunded receipt status or credit plus same-reference debit | REVIEW / REVERSAL | Resolve evidence first; neither allocation review nor legacy SHIP bypasses this guard |
| Delayed/conflicting posting beyond 24 hours | REVIEW / DATE_CONFLICT | Correct/verify source dates before allocating |
| Missing/incomplete coverage or posting window too narrow | Existing REVIEW / COVERAGE or POSTING_WINDOW | Import sufficient coverage and confirm it |

Split/combined funding is **never automatically approved**. Similar amounts or names
are insufficient. Combined-payment hints consider a credit equal to two order totals;
they are proposals, not inferred ownership. Explicit review can distribute a verified
source among more orders (bounded to 100 orders per plan, 20 parts per order), even
where no pairwise hint exists. The receipt must describe the entire source credit;
each allocation is an explicitly reviewed portion, not a rewritten receipt amount.

In saved results, choose **Review payment allocations**. Select only the orders to
change, select source credits and receipt evidence, enter each allocation amount,
inspect funding totals and provide a reason explaining their relationship. An explicit
confirmation is required. Source and receipt amounts, references, times and status
are shown alongside controls. Unchecked orders are unchanged. Checked orders replace
all their current reservations; an empty parts list releases that order's funds.

A partial reservation remains REVIEW. Full reviewed funding becomes human SHIP while
the original machine verdict, reason code and rule evidence remain unchanged. HOLD
or REVIEW through the older individual decision interface releases all of that order's
reservations; the UI warns about this. Use allocation review to retain partial funds.
Existing inputs stay locked after reconciliation. To import newly arriving payments,
explicitly reset and re-import/reconcile; reset releases existing reservations. A
non-disruptive incremental-payment import workflow remains future work.

## Allocation invariants and migration

`20261024_payment_parts` adds positive integer `amount_paisa` to allocations, backfills
existing whole allocations from their source credits, replaces whole-credit exclusivity
with a unique `(match_id, credit_key)` constraint, and adds private idempotent review
records. Existing allocation IDs and linked records are preserved. No old migration
or source financial record is rewritten. Full-reference checks now count normalized
characters so internal spaces cannot promote a short reference. Historical v1 source
key generation is deliberately retained; tests verify that existing credit identities
do not change when evidence-strength checks improve.

All application allocation writers now serialize per seller before examining retained
credit usage: SQLite uses the existing BEGIN IMMEDIATE write transaction; PostgreSQL
uses a seller-row FOR UPDATE lock. The worker and both human-review endpoints obey
this protocol. Amounts are summed from live allocation rows, so reset, deletion and
expiry cascades cannot leave stale counters. PostgreSQL locking is implemented but
has not been runtime-tested in this environment.

Within the transaction, requested per-credit shares plus retained shares cannot exceed
the original credit, and per-order shares cannot exceed its total. Reimporting a
retained strong reference with a different amount/account is rejected. Positive-share
and per-match/source constraints provide additional database checks; aggregate budget
limits rely on the application transaction/locking protocol. Direct SQL writers must
not bypass it. No claim of a database-only aggregate constraint is made.

Stop API/worker processes and back up the database and uploads together before
migrating existing data. From `milaan/backend`:

```sh
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m alembic check
```

Restart all processes with the new code. Old workers cannot safely operate against
this schema. Downgrade to the earlier whole-allocation model is refused when partial
or shared data cannot fit its constraints; do not delete financial data just to force
a downgrade. Export/backup and choose a deliberate rollback strategy instead.

## API contract

`POST /api/batches/{batch_id}/allocation-review` requires authentication, an
`Idempotency-Key` (8–100 characters) and a body containing:

- `expected_revision`: current batch revision after reconciliation.
- `confirmed_relationships: true` and a 5–1,000-character `reason`.
- `orders`: each current `match_id` and `expected_version`, plus `parts` containing
  `statement_line_id`, `claim_id` and positive decimal PKR `amount_pkr`.

One plan is all-or-nothing. Stale versions, wrong owners, foreign-batch evidence,
insufficient funding capacity, duplicate source records, incomplete/unverified
coverage, unsuccessful/unconfirmed receipts and reversal evidence fail without
changing existing allocations. Source receipts need a full matching reference, an
amount equal to the entire PKR credit, and a timestamp within the covered period and
24 hours of posting. Shared receipts must be explicitly selected from the same batch
and account. Duplicate image uploads must be resolved before review.

An unchanged request retried with the same key returns its original response snapshot
without writing again. A changed body under that key returns 409. A replay after a
reset is rejected because the batch revision changed. Replays do not reapply a plan
that another human later released; GET current results to see current state.

Results now include `allocations`, `allocated_paisa` and `outstanding_paisa`.
`selected_line_id` remains for single-source compatibility and is null for multi-source
funding. Statement lines report current `unallocated_paisa`. Export preserves existing
columns and adds `allocated_pkr`, `outstanding_pkr` and JSON `allocation_parts`.
Private audit events record exact source shares, reviewer reason and result version.
Batch deletion/expiry removes allocation-review retry records along with allocations.

## Actual validation

Python 3.12.14, Node 24.19.0, Linux and local Chromium:

| Executed check | Result |
|---|---|
| Backend `python -m pytest tests matching/tests` | 109 passed |
| Root `python -m pytest tests/test_store_sync.py tests/test_migrations.py` | 7 passed |
| `node --test milaan/frontend/tests/*.test.mjs` | 32 passed |
| `BROWSER_EXECUTABLE=/usr/bin/chromium npm --prefix tests/browser test` | 6 passed: desktop and mobile workflows |
| `python tests/live_demo_check.py` | Five unchanged store scenarios and manual confirmation/review/export passed |
| `npm --prefix milaan/frontend run check` | Passed |
| `python -m alembic upgrade head` and `python -m alembic check` | Passed; no schema drift |
| Python compilation, dependency consistency and `git diff --check` | Passed |

Total: **154 tests passed**, plus live HTTP assertions. No skipped or expected-failure
tests in these runs. The backend tests exercise split, partial, shared and excess
payments; unsafe evidence; private ownership; stale/replayed plans; group rollback;
retained-source inflation; reset/expiry; concurrent conflicting requests, concurrent
identical retries, and an automatic worker racing a human allocation review. Migration tests preserve existing whole allocations, restore their
amounts on upgrade, retain foreign-key integrity and reject a lossy partial downgrade.

All six browser workflows execute against a temporary synthetic database. They cover
the existing complete saved workflow and import rejection/cancellation, plus actual
combined-payment selection, confirmation, persistence and CSV export. Independent
browser projects use independent synthetic references: retained credit reuse is blocked
across batches, including test batches. Screenshots are genuine local captures:

- [Desktop allocation review](screenshots/allocation-desktop.png)
- [Mobile allocation review](screenshots/allocation-mobile.png)

The prior browser suite's import/results screenshots were also regenerated from the
current local app. Starlette's existing httpx TestClient deprecation warning remains.
CI already discovers the new backend/frontend tests and now runs six browser cases;
a remote passing CI run is not claimed.

## Repeatable synthetic demo

1. Use canonical setup and migrate before starting both services. Run the unchanged
   five-scenario demo store to show that existing behavior is retained.
2. In a saved batch, import two orders for PKR 100 and PKR 50, and one synthetic credit
   for PKR 150. Upload and confirm one synthetic receipt for that entire credit.
3. Reconcile: inspect COMBINED_PAYMENT proposals in REVIEW. Open allocation review,
   select both orders, the same source credit and receipt, and shares 100 and 50.
4. Confirm the relationship and reason. Save once; both orders become human SHIP with
   the machine verdict still REVIEW. Export the per-credit allocation details.
5. In another batch use distinct synthetic references with credits 60 and 40 for one
   order of 100. Reconcile: SPLIT_PAYMENT is REVIEW. Reserve only 60 to demonstrate
   partial REVIEW, then replace the plan with both parts to demonstrate human SHIP.
6. Explain that neither demonstration sends money, issues refunds or proves settlement.

Use `docs/IMPORT_CONTRACTS.md` for formats. Retain originals privately; do not use real
bank exports or user receipts in public demonstrations.

## Limits

Advanced allocation is a saved-backend workflow; browser-local illustrative mode has
no retained multi-batch ledger. Both modes now reject same-reference reversal evidence
for shipping. Refund detection is conservative evidence review, not automatic refund
execution or exhaustive bank-specific reversal classification. New data does not
retroactively amend previously saved results; reset/reconcile explicitly when source
records change. Live Gemini/SMTP, PostgreSQL runtime/concurrency, Windows and hosted
Sites behavior remain unverified. Native PDF parsing is unchanged and unsupported.

The local implementation is **READY FOR REVIEW**, not a production deployment or a
claim that operational bank integration exists.
