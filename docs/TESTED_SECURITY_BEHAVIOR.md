# Security release checks — verified behavior only

This is a **test inventory**, not a penetration-test certificate or authorization to onboard users. All test data is synthetic; no production account or financial record is used.

| Behavior | Code reference | Automated checks |
|---|---|---|
| CSV export prefixes formula-starting strings | `milaan/backend/app/parsing.py:97-105`, `milaan/frontend/dist/engine.js` | `test_release_security.py::test_csv_export_cannot_start_spreadsheet_formulas`, `security-output.test.mjs` |
| Private receipt bytes re-encoded without EXIF | `milaan/backend/app/storage.py:8-23` | `test_release_security.py::test_receipt_image_is_reencoded_without_private_exif` |
| Cookie mutations require CSRF | `milaan/backend/app/browser_auth.py:18-21` | `test_release_security.py::test_non_ascii_csrf_header_denied_with_403` |
| Baseline response security headers | `milaan/backend/app/middleware.py:15-24` | `test_release_security.py::test_standard_security_response_headers` |
| Anonymous accounts cannot list saved batches | `milaan/backend/app/main.py` authenticated endpoints | `test_release_security.py::test_anon_cannot_access_saved_financial_records` |
| Retained credit allocation concurrency | `milaan/backend/app/allocations.py:10-35` | `test_payment_allocations.py::test_concurrent_reviews_cannot_overallocate_retained_credit` |

The isolated PostgreSQL and S3 suite is exercised by the existing CI step `python scripts/test_postgres_s3.py`; use its logs to confirm the **actual** test result. Live provider delivery and scaling guarantees are separate operator acceptance tests. Do not treat a passing synthetic test as evidence of payment settlement or completed compliance review.

Future security evaluations should use an operator-approved private channel; do not publish sensitive findings or infrastructure configurations.
