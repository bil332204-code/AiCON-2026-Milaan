# Milaan: making payment evidence review explainable

Built for AiCON 2026 — Build With AI; maintained in
`bil332204-code/AiCON-2026-Milaan`. Contributor attribution remains in Git history.

## Problem

An order, a customer screenshot and a receiving statement are separate pieces of
evidence. References can be masked, bank posting can be delayed, receipt images
can be reused and Pakistani names can vary. Treating a plausible screenshot or a
similar name as settlement creates avoidable operational risk.

## Approach and implementation

The local kit combines FastAPI, SQLAlchemy, Alembic, SQLite, static JavaScript,
Pillow, pytest and Node's test runner. Authenticated saved batches connect orders,
normalized CSV statements and private receipt images. A persistent worker performs
deterministic reconciliation; Pakistani name similarity expands review candidates.
Manual confirmation works offline from AI services. Optional Gemini extraction
requires configuration and explicit consent, then review of extracted evidence.

SHIP requires strict reference, amount, account, successful-status and coverage
checks. HOLD indicates missing evidence within usable coverage. REVIEW exposes
conflicts and uncertainty. Versioned human decisions preserve the machine result.
Database uniqueness protects retained allocations across batches. Expiring sessions,
ownership checks, image sanitization, CSV formula neutralization and configurable
retention protect the working-data lifecycle.

## Engineering challenges and evolution

The original project and hackathon history are preserved. Post-hackathon work
restored the separate synthetic store and interrupted synchronization recovery.
This release pass found that browser-local matching omitted a successful-status
gate used by the backend. A regression test reproduced the unsafe recommendation;
the gate and editable receipt status now align. A forward migration resolves
legacy unique-index representation drift without rewriting historical migrations.
Credential-free CI exercises synthetic matching, imports, APIs and live HTTP flows.

## Demonstration and evidence

Correct payment ships; missing credit holds; wrong amount, reused proof and name
variation require review. [Demo script](DEMO.md) and [release evidence](RELEASE_REPORT.md)
record scope and actual results. Fixture mode tests matching, not OCR accuracy.
No screenshots, user counts, performance numbers or endorsements are fabricated.

## Limits and future work

The hosted workspace is separate and was not updated or independently validated.
The local kit has no bank connection, payment execution or native PDF processing.
Windows, Python 3.13, live Gemini/SMTP and PostgreSQL runtime remain unverified.
Future work includes PostgreSQL concurrency exercises, browser accessibility testing
and stronger distributed deployment controls. Recommendations are based on supplied
evidence and do not guarantee financial settlement.

## Ready-to-use portfolio summary

Milaan is an AiCON 2026 payment evidence review project that compares orders,
receipts and receiving-bank exports. Its local FastAPI system provides explainable
SHIP/HOLD/REVIEW recommendations, private saved batches, manual review and CSV
exports, with optional consent-based Gemini receipt extraction. A separate simulated
store and synthetic integration suite demonstrate ambiguous evidence and duplicate
payment handling. The externally hosted application is maintained separately.
