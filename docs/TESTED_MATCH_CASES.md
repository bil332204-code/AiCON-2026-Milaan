# Synthetic reconciliation edge-case matrix

The application makes conservative **suggestions** based solely on uploaded evidence. It does not verify payment settlement with a provider or execute shipping. This table documents expected/current source-driven behavior; source logic was **not modified** in this PR.

| Synthetic evidence case | Expected/current outcome | Code/test evidence | Importance |
|---|---|---|---|
| Statement credit smaller than order (fees/shortfall) | REVIEW, amount discrepancy | `app/matcher.py:98-108,117-121`; `test_rules.py::test_additional_payment_evidence_boundaries_remain_conservative` | High |
| Partial screenshot amount | REVIEW, partial/amount conflict | `app/matcher.py:98-108`; `test_rules.py::test_conservative_rules` | High |
| Overpayment/combined credit | REVIEW with explicit human allocation | `app/matcher.py:98-106`; `test_payment_allocations.py::test_overpayment_is_not_auto_shipped_or_overallocated` | High |
| Debit refund/reversal with same reference | REVIEW, reversal evidence | `app/matcher.py:91-95`; `test_rules.py::test_refund_debit_or_reversed_status_prevents_automatic_ship` | High |
| Same proof or full Transaction ID on two orders | REVIEW for both | `app/matcher.py:89-90,145-150`; `test_rules.py::test_same_full_reference_on_two_orders_blocks_both_even_with_distinct_images` | High |
| Payment outside declared statement coverage | REVIEW until coverage is established | `app/matcher.py:109-112`; `test_rules.py::test_conservative_rules` | High |
| Posting more than 24 hours from receipt | REVIEW, date discrepancy | `app/matcher.py:121-122`; `test_rules.py::test_delayed_posting_is_a_conflict_not_automatic_settlement` | High |
| Equal-amount credits with **different** full IDs | A single fully confirmed unique matching ID can still SHIP | `app/matcher.py:117-127`; `test_rules.py::test_same_amount_with_distinct_transaction_ids_is_not_automatically_a_conflict` | Medium |
| Missing/partial Transaction ID | REVIEW, possible candidate only | `app/matcher.py:128-131`; `test_rules.py::test_missing_or_partial_reference_never_automatically_ships` | High |
| Mismatched complete Transaction ID | REVIEW, not an automatic exact match | `app/matcher.py:117-137`; `test_rules.py::test_additional_payment_evidence_boundaries_remain_conservative` | High |
| Wrong receiving account | REVIEW, account conflict | `app/matcher.py:87-88`; `test_rules.py::test_additional_payment_evidence_boundaries_remain_conservative` | High |
| Pending/failed/ambiguous provider status | REVIEW, status conflict | `app/matcher.py:96-97`; `test_rules.py::test_missing_or_ambiguous_status_cannot_ship` | High |
| Midnight in Asia/Karachi | Normalize to equivalent UTC instant | `app/parsing.py`; `test_rules.py::test_midnight_karachi_timezone_normalizes_to_the_same_instant` | Medium |
| Duplicate statement credit identity | REVIEW, duplicate source evidence | `app/matcher.py:113-114`; `test_rules.py::test_duplicate_proof_and_statement_credit` | High |
| Browser-local versus saved backend | Browser-local is illustrative/batch-scoped; saved backend persists retained-credit allocation history | `app/allocations.py:10-35`, `test_payment_allocations.py::test_concurrent_reviews_cannot_overallocate_retained_credit` | High |

**Review boundary:** `SHIP` always means “matching evidence in the records provided”; it does not mean bank-authenticated payment. No match, retention or allocation code changed. Concurrent PostgreSQL validation is run in the CI integration script using disposable synthetic services.
