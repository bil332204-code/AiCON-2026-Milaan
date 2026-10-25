# Public SaaS launch review

25 October 2026. Continuation of Issue #8 and Draft PR #15, based on
`35dd07e643f7776b1bad68777b2322e0e9520b40` (includes main
`8f2c4a0a87ddfe2da9734d0391bd9d23f958d89a`). This is a code review and
synthetic validation record, not deployment approval or a legal compliance opinion.

## Completed in this continuation

- Replaced provider-message excerpts in password-recovery logs with the existing
  fixed diagnostic categories, status code, provider-code allowlist and field hints.
  Pattern-based redaction could still copy personal names, addresses, spaced codes
  or short tokens from an upstream error. Tests now exercise those responses through
  the recovery endpoint and assert they never enter application logs. Provider
  errors still produce the same account-enumeration-resistant client response.
- Completed public guide title, description and Open Graph metadata. Public pages
  derive their canonical URL from `PUBLIC_ORIGIN`, so staging no longer advertises
  the production URL inside policy HTML. Request queries and forwarded hosts are
  not used in metadata. Static `.html` aliases redirect to the canonical document
  routes; APIs retain their existing behavior. Public documents support HEAD with
  the same canonical/security headers; private workspace HEAD still requires login.
- Prepared Privacy Policy, Terms & Conditions, and About drafts using facts supplied
  by the owner: Bilal Ahmed is the individual founder/operator in Pakistan; Milaan
  is not a registered company and has no registered business office. No personal
  address is published. Pakistan is the proposed governing jurisdiction, subject
  to legal review. No working support inbox is invented or linked.
- Added desktop/mobile browser checks for the public guide's keyboard language
  controls, Escape dismissal, accessible legal pages and viewport fit. Fixed two
  stale browser-test expectations in the existing PR after its visible import
  labels changed to seller terminology. Import validation and financial assertions
  remain active.
- Fixed an authentication-dialog focus race discovered during browser validation.
  A delayed animation-frame callback could steal focus from password confirmation
  and direct input into the first password field. Initial focus now happens when
  the dialog opens. A deterministic delayed-frame browser regression failed before
  this fix and is included in both desktop and mobile runs.

The design assets, matching rules, financial schemas, production secrets and
infrastructure are not changed by this continuation. No live email was sent.

## Owner facts versus outstanding policy details

The pages identify themselves as drafts, not effective contracts or final policies.
The owner has not supplied a working support inbox. Before public onboarding,
establish a private contact route and define data-request identity checks and
response periods. Confirm provider/subprocessor locations, account/log/backup
retention, storage-version deletion, incident procedures, applicable legal grounds
and age/eligibility rules. Pricing, billing, refunds, liability, IP permissions,
dispute procedures and an effective date need review before final terms or paid
plans. No home address is requested or published as a substitute for these facts.

## Release gates still outstanding

1. **Real email delivery:** verify an authorized message in an actual inbox,
   including expiry, single use and recovery/session behavior. Mocked browser
   outboxes and successful provider responses do not prove inbox receipt.
2. **Explicit signup activation:** keep `ALLOW_REGISTRATION=false` and
   `EMAIL_DELIVERY_VERIFIED=false` until delivery testing and owner approval are
   recorded. The public website, fictional demo, guide and policy routes remain
   anonymously accessible. No maintenance or invite-only gate is introduced.
3. **Operations:** independently scheduled expiry processing while Render Free
   sleeps; backup/PITR and coordinated database/object restore rehearsal;
   monitoring, abuse controls and provider-access review. These require separate
   infrastructure work and approval, not silent changes in a source PR.
4. **Legal/contact readiness:** complete the items above and obtain legal review.
5. **Release:** review this draft, verify CI on its final commit, then separately
   approve merge/deployment. Earlier authorization for `aa6053e` does not authorize
   deploying this new code. Preserve production/staging isolation and auto-deploy OFF.

The proposed normalized receipt-status dropdown in the earlier Phase 1 report
remains a proposal. It must preserve original provider evidence and must not turn
ambiguous text such as “Payment sent” into automatic SHIP. No such mapping has
been introduced. License selection, repository reorganization and commercial
billing are also not implemented by this change.

## Validation

See the final validation entry below for executed commands and results. Local
PostgreSQL/S3 tests use disposable containers and synthetic data; they do not
establish Neon permissions, backup behavior or actual email delivery. Browser
tests use an isolated database and intercepted email transport. The existing
Starlette/httpx TestClient deprecation warning remains.

### Executed results in this continuation

| Check | Result |
| --- | --- |
| Backend/matching SQLite (`python -m pytest tests matching/tests`) | 218 passed, 3 PostgreSQL-only skips |
| Backend/matching PostgreSQL 17 + Moto S3 (`python scripts/test_postgres_s3.py`) | 215 passed; executed before the six additional document HEAD tests, which subsequently passed in SQLite |
| Final public-page, canonical/header and email regression subset | 64 passed |
| Root store and migration tests | 8 passed |
| Frontend Node tests | 41 passed |
| Desktop/mobile Playwright, system Chromium | 16 passed; includes the deterministic focus regression |
| Local HTTP demo scenarios | Passed including manual receipt confirmation, saved human review and private CSV export |
| Docker build and final container smoke | Passed; non-root runtime, CSRF, persistence, logout revocation and forwarded-IP spoof rejection |
| Dependency consistency, compilation, frontend syntax, diff whitespace | Passed |
| Gitleaks v8.24.2 | Existing full Git history and staged added lines passed; original exact synthetic-fixture exception retained, no new exclusions |
| Public HTTPS read-only checks | Landing 200; health 200/database reachable; unauthenticated workspace 303 to login |

Initial browser runs found stale import-label assertions and the focus race; those
failures were resolved and the complete 16-test browser suite rerun. An intermediate
PostgreSQL run overlapped the owner's policy-content update and used older expected
text; the complete PostgreSQL suite was rerun after those edits and passed. Generated
screenshots/performance outputs were restored rather than changing design artifacts.

The scans are pattern checks, not proof that every vulnerability or secret is absent.
The hosted read-only checks do not establish deployed commit, email delivery, storage
permissions or infrastructure configuration. GitHub GraphQL is blocked in this
session; PR source updates use the existing authenticated Git remote. No new remote
CI result or production deployment is claimed here.
