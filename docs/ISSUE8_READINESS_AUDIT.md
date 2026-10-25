# Issue #8 readiness audit

25 October 2026. Base: `d538c86`, merged V4. Branch: `fix/milaan-readiness-audit`.
Source of truth: https://github.com/bil332204-code/AiCON-2026-Milaan/issues/8 .
The complete issue and comments were read via GitHub's public HTML page. GitHub
GraphQL and REST access are blocked by this environment's proxy. The connector bot
comment on the issue says “create an environment for this repo”; that integration
message does not invalidate the local checkout or native Git access here.

## Verified scope and changes

Reviewed application configuration, authentication/session/verification/recovery,
Resend, request guards, database/migrations, receipt lifecycle/worker, input parsing,
reconciliation/allocation constraints and human review, frontend API/HTML rendering,
local demo-store boundaries, Docker/CI and deployment documentation. Existing
regression suites cover these workflows. This is a source and synthetic integration
audit, not a penetration-test certificate or proof that every possible vulnerability
has been eliminated. No installed connector exposes Render/Neon administration.

| Priority | Finding and evidence | Resolution |
|---|---|---|
| High | Docker default trusted arbitrary forwarded client-IP headers, permitting IP-limit identity spoofing when reached directly | Disable proxy header trust by default; container regression varies forged X-Forwarded-For headers and still reaches 429 |
| Medium | Non-ASCII CSRF header reaches `hmac.compare_digest(str,str)`, which raises TypeError instead of denying the request | Compare encoded bytes; malformed headers return 403, correct CSRF still works |
| Medium | WWW documents can issue cookie-auth requests with an Origin rejected by the canonical PUBLIC_ORIGIN policy | Production GET/HEAD browser documents redirect to configured PUBLIC_ORIGIN; API requests retain existing behavior and never redirect credentials |
| Medium | Resend Retry-After HTTP dates were treated as malformed numbers and retried immediately | Parse HTTP dates, respect a future retry window, fail safely on invalid advice; at most one retry retained |
| Medium | Extremely long numeric CSV fields reach Decimal/int conversion despite the small supported monetary range | Bound the amount input before conversion; reject the import without partial writes |
| Low | Valid local timestamps at year boundaries can overflow when converted to UTC | Convert OverflowError to a validation error |
| Low | Duplicate document hosts had no canonical metadata and auth pages lacked crawler exclusion headers | Canonical Link headers on browser documents; noindex/nofollow on auth/workspace pages |

Only safe browser documents redirect. Redirect targets come exclusively from
PUBLIC_ORIGIN, never Host/X-Forwarded-Host. Query strings are preserved; reset tokens
remain URL fragments and are never inserted into an HTTP redirect by the server.
307 responses use no-store so rollback is not pinned by browser caches. Host-only
cookies are not copied across domains: users arriving with an old alias-host cookie
may need to sign in again at the canonical origin. API and health-probe compatibility
is retained. No URL, HTML, CSS, animation or matching-decision redesign is included.

The production environment reference template now reflects the issue's confirmed
apex/www origins, private production endpoint/prefix and sender. It contains no
credentials, is not applied to any service, and must never be used for staging.

## Hosted facts versus observations

Issue #8 reports production `milaan-production-2026` and staging
`milaan-neon-stage-2026` live on `d538c86`, production origin https://milaan.app,
and successful apex/www domain validation. Those are handoff facts, not independently
reverified deployment claims. This environment attempted only read-only GETs for
https://milaan.app, https://www.milaan.app, /api/health and /workspace. All were blocked
by the outbound proxy with tunnel 403 before reaching the app. This is not evidence
that any service is down. Current redirect behavior, headers, DNS and provider TLS
remain unverified from here. No POST or email request was sent to hosted services.

Production: Neon branch `br-plain-thunder-azzkcek5`, prefix
`milaan/production/receipts/v1/`. Staging: `br-cool-wind-azgg33ig`, prefix
`milaan/render-staging/receipts/v1/`. The old preview is preserved. No real database
counts were queried; the issue's earlier zero-user snapshot is not asserted current.
Staging's test-only account must not be treated as a production user or copied into
production. No secrets were retrieved, displayed, copied or modified.

## Remaining release gates, in priority order

1. **Before public onboarding: email and signup.** Keep ALLOW_REGISTRATION=false,
   EMAIL_DELIVERY_VERIFIED=false and ENABLE_DEMO=false. Issue #8 reports staging's
   sending key configured, production key likely absent, and no verified inbox
   receipt. An authorized operator must check only key presence in the production
   Render secret UI; if absent, enter a scoped Resend sending key there, never in
   chat/Git/logs. Preserve EMAIL_FROM=`Milaan <no-reply@milaan.app>`, disable auth-link
   tracking and confirm sender-domain alignment. Separately authorize a synthetic
   staging recovery/verified-account challenge and observe actual inbox delivery,
   expiry, single-use behavior and session revocation. A Resend 200 or verified DNS
   does not pass this gate. Opening registration requires a separate explicit go-ahead.
2. **Before financial records: expiry scheduling.** A sleeping Render Free API cannot
   promise retention erasure. Prepare one independently scheduled cleanup job per
   environment, every 15 minutes (`*/15 * * * *`), using the reviewed image and
   `cd /app/milaan/backend && python -m app.worker --cleanup`. Bind only that
   environment's DB and storage secrets; do not mix prefixes. This is a proposed
   schedule, not an applied cron. Keep the API worker available for reconciliation.
   Record successful scheduler execution and alert on missed runs, cleanup errors,
   retry counts >=5, or overdue `receipt_deletions.next_attempt_at`. Test interrupted
   erasure and retries with synthetic data before accepting a retention SLA. Bucket
   versioning can retain old versions after DeleteObject: verify provider erasure
   policy and least-privilege List/Get/Put/Delete scope separately. No lifecycle or
   scheduler infrastructure was created.
3. **Before financial records: backups and restore.** Confirm actual Neon PITR window,
   S3 versioning/recovery policy and recovery objectives. Rehearse a coordinated
   isolated DB/object restore with synthetic data, check references and pending
   erasures, and record the result. A database backup alone is not a receipt backup;
   a restored pre-deletion DB must not silently resurrect erased records. Existing
   roles are reported as `milaan_owner`; review runtime DML versus migration DDL
   privileges before granting broader access. No grants or backup settings changed.
4. **Before public scale: abuse controls and observability.** IP throttling is bounded
   but process-local; account lockouts/cooldowns are database-backed. Confirm Render's
   forwarded-header contract before trusting proxy client IPs. The Dockerfile now defaults to `--no-proxy-headers`; verify actual Render command
   overrides too, since an override can bypass that default. Behind an ingress this
   conservatively shares an IP budget until an approved trusted-proxy configuration
   is supplied. Multi-instance operation requires a shared limiter or approved ingress
   control. Monitor latency, 5xx, queue age, DB pool pressure, delivery rejections,
   provider bounces and worker heartbeat without payload/credential logging. No
   public maintenance endpoint or unauthenticated cleanup trigger was introduced.
5. **Before approving this deployment:** verify canary apex/www/Render-host redirects,
   canonical Link headers, auth-page noindex, cookie host scope and reset fragment
   handling on staging using its own PUBLIC_ORIGIN. Confirm CORS preflights and CSRF
   rejection, registration/demo denial and current image SHA. Existing native bearer
   API URLs remain supported. Stage first, with owner approval; no auto-deploy.

The demo-store remains a loopback-only synthetic tool, excluded from the production
image; it is not a separately hardened public commerce service. Native bank-PDF
extraction and settlement/bank verification must not be advertised beyond the
existing documented import/extraction capabilities. The audit adds no fabricated
financial data, provider success, payment decision or product capability.

## Rollback

After separately approved rollout, roll back to the recorded previous compatible
image if canonical/origin checks regress. Keep the same DB/storage namespace and
closed-registration flags. There is no new migration, so no downgrade, account
rewrite or receipt copy is needed. Canonical redirects are non-permanent/no-store.
Do not change DNS, secrets, infrastructure or actual user records as an automatic
rollback action. Retain the current production and staging deployment IDs from
Issue #8 in the operator release record rather than assuming the old snapshot is
still current.

## Executed validation

Results are synthetic/local. Email uses MockTransport; S3 uses the local HTTP
emulator, not Neon. Browser regressions run the existing SQLite test server.

| Check | Actual result |
|---|---|
| Backend/matching with SQLite | 177 passed; 3 PostgreSQL-only tests skipped |
| Same suites with PostgreSQL 17 + local S3 HTTP emulator | 180 passed; none skipped |
| Root store/migration suites | 8 passed |
| Frontend unit tests | 36 passed |
| Desktop/mobile browser workflows | 12 passed |
| Live local HTTP scenarios | All five original scenarios plus receipt confirmation, saved review and private export passed |
| Final Docker build and container smoke | Passed: non-root, CSRF, persistence after restart, session revocation and forged forwarded-IP rate-limit check |
| Dependency consistency, compilation, frontend syntax and whitespace | Passed |

The existing Starlette/httpx TestClient deprecation warning remains. No migration
was added or changed. The PostgreSQL suite replays migration history with the direct
connection and checks schema drift; it does not establish the live Neon pooler's
TLS behavior. No new remote CI success is claimed. Test-generated screenshots were
restored so design artifacts have no branch diff. The branch is ready for review;
public onboarding remains blocked by the operational gates above.
