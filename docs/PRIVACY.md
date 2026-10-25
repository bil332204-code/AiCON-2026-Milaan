# Local retention and privacy

New batches expire after 168 hours (seven days). Configure
`BATCH_RETENTION_HOURS` from 1 to 8760 before creating batches; this does not
retroactively change existing expiry dates. Expired batches are denied immediately;
the running worker performs cleanup approximately every minute.

Expiry or explicit deletion removes batch records, orders, claims, statements,
jobs, results, allocations and batch audit records. Private receipt files are
removed. Accounts and seller content survive. Reset clears current results and
allocations while keeping input and prior run/audit history until deletion/expiry.
Credit reuse protection covers retained allocations only; expiry, deletion or reset
releases them. Export before expiry. Back up the SQLite database and private upload
directory together while writes are stopped; protect backups and exports as private
financial records. CSV export does not constitute an image backup.

Receipts are decoded, resized, stripped of metadata and stored as private JPEGs.
Image routes require authentication and seller ownership. Uploaded images are not
public assets. The worker reaps crash-created orphan JPEGs after a grace period.
Gemini receives images only when configured and extraction is explicitly requested
with cloud consent. Manual confirmation works without a provider or key.
Browser-local OCR can download an external engine; browser-local work is distinct
from saved backend records. Do not use production records in demonstrations.

Authentication uses hashed passwords, revocable expiring bearer sessions and basic
single-instance authentication rate limits. These are not a distributed abuse
prevention system. Use HTTPS and explicit CORS origins for public deployments.
Never commit `.env`, upload directories, databases or exported financial records.
Audit review reasons can contain sensitive text; restrict database access.
The external hosted workspace's privacy and retention have not been independently
validated here; consult its current guide before supplying real information.


V2 reviewed allocations reserve explicit integer-paisa shares across retained records.
Private audit history includes reviewer reasons and exact source shares. Idempotency
records contain private response snapshots and expire/delete with their batch.
Partial funding may remain in REVIEW while its credit shares stay reserved. Legacy
HOLD/REVIEW, reset, deletion and expiry release reservations; no refund is sent.
See [Milestone B](V2_MILESTONE_B.md) for budget protection and migration requirements.


V3 browser sessions use HttpOnly cookies, in-memory CSRF material and server-side
revocation/expiry. Remember-me has a finite 30-day maximum; passwords and raw reset
credentials are not stored in browser web storage. Reset links expire after 15 minutes
and use one-time hashed server records; recovery is enabled only for proven emails.
Previously unverified local users must confirm the mailbox from an authenticated
account first. Their IDs, password access and financial ownership are not rewritten.
Hosted provider identities are not linked by email strings. See
[V3 migration boundaries](V3_IDENTITY_MIGRATION.md) and [release evidence](V3_RELEASE.md).

### V4 transactional email

Verification and recovery messages use the Resend HTTPS API. Resend processes the
recipient address and authentication message, including its OTP or reset link.
The application does not send financial records in these emails and does not log
provider bodies or token-bearing payloads. Operators must review provider retention,
suppression and delivery logging, and disable tracking for authentication messages.
No live message or provider configuration change occurred during V4 development.
