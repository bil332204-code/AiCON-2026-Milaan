# Product decisions — proposals only, no implementation

Each proposal needs an explicit separate owner decision. Keep existing SHIP/HOLD/REVIEW and expiry rules unchanged.

## Receipt-status choice
Proposed UI: **Successful / Pending / Failed / Unclear**, with the original provider status preserved separately as evidence. Only independently confirmed success with all existing statement and identity checks could reach SHIP; **Pending / Failed / Unclear must remain REVIEW**. No automatic inference of success from words like “sent” or “transferred”. Negative tests: missing evidence, ambiguous text, duplicate proof, wrong amount and a reused credit never produce SHIP. Needs design review and exact mapping approval before implementation.

## Statement PDF / spreadsheets
Option A: user-controlled CSV conversion with a validated mapping screen (low engineering cost, safer provenance). Option B: server-side PDF/XLSX parser with explicit original-file preservation, row/page caps, conversion diagnostics and human approval (high complexity, more input risks and maintenance). No named bank navigation or native PDF processing is claimed.

## Multiple receiving accounts per batch
Proposed data model: each statement explicitly binds to one validated receiving account with independent coverage, and reconciliations never cross account budgets. Would require schema migration, ownership checks, import UI and race tests; do not silently change current single-account contract.

## Distributed abuse control
Alternatives to assess: trusted ingress-layer throttling; database-backed shared counters; dedicated rate-limit store. Compare policy, cost, latency and multi-instance behavior; never add a paid dependency without approval.

## Retention and backups
Compare a separately scheduled cleanup job versus an approved scheduled platform function, with strict server-only credentials and receipt-erasure evidence. Backups must include point-in-time database recovery AND private receipt objects, coordinated erasure behavior, alerts, and restore drills. Cost, monitoring and legal obligations require operator review.

## Public signup
Sequence: deliver real production mail to controlled inbox -> verify full OTP/reset/session flow -> establish trusted support/privacy/retention/backup operations -> secure review -> explicit owner activation. Never switch any signup or email assurance flags from a source PR.
