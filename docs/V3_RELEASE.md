# Milaan V3 — cinematic UI and independent authentication

25 October 2026 · `feat/milaan-cinematic-auth` · based on main `3883e9f` (PR #4).

**READY FOR REVIEW as an integrated, deployable alternative. The hosted Sites
application was not edited, migrated or deployed.**

## Source and hosting verification

The available checkout is the GitHub local kit. Git remote discovery lists main,
post-hackathon and the earlier release/V2 feature branches; none is identified as
an authoritative Sites checkout. Available connectors expose no Sites source,
identity administration or deployment tools. Read-only requests to the supplied
hosted homepage and guide failed with a proxy error. This proves lack of access in
this environment, not that the website is down or that its source does not exist.

The repository already documents separate maintenance of the hosted application.
Its authentication constraints, database, identity subjects and ownership mappings
cannot be verified here. No attempt was made to bypass its provider, hide its login,
link accounts by email alone or replace its data. The existing hosted system must
stay available until a supported migration is proven. See
[identity migration boundaries](V3_IDENTITY_MIGRATION.md).

## Implemented visual system

The existing HTML/JavaScript frontend and all reconciliation workflows remain in
place. `cinematic.css` applies a midnight, purple/blue and teal visual language to
the homepage, saved workspace, tables, dialogs, import previews, evidence comparison,
allocation review, settings, guide and authentication forms. Existing CTA actions,
sections, scenario controls and demo/store behavior are retained.

`cinematic.js` adds ambient gradient fields, bounded desktop cursor illumination,
headline word entrances, a synthetic fixture activity chart, computed demo counters,
a labeled fictional transaction ticker and light parallax/magnetic interaction.
The existing Canvas scene supplies depth and floating financial cards; no new
WebGL, GSAP, scroll replacement or chart dependency is required. Native scrolling
and anchors remain usable. Pointer effects are disabled for touch; hidden/offscreen
work and workspace-only views pause decorative effects. Reduced-motion and the
existing motion toggle disable or pause animation. Keyboard scenario tabs now use
roving focus, arrows, Home/End and a labeled panel. Focus outlines stay visible.

Demo counters come from `reconcile(demoData())`; the chart counts timestamped synthetic
claims. They are labeled synthetic, not live activity, prices or product statistics.
Saved workspace totals still come from its real API data. No exchange-rate widget
was added to a PKR-only reconciliation workflow. No accuracy, customer or FPS claims
were fabricated.

## Implemented server authentication

- Independent email/password signup and login, confirmation field, visibility toggle,
  guidance, validation, verification, loading and recovery states.
- Versioned scrypt password hashes (N=32768, r=8, p=3, 32-byte derived key). Existing
  scrypt hashes remain usable and upgrade after a successful password login.
- Browser sessions use host-only HttpOnly SameSite=Lax cookies. Production uses Secure
  `__Host-` cookies. No session credential is returned to the same-site browser UI or
  stored in localStorage. CSRF material remains in memory and is derived from the
  server credential; unsafe cookie-authenticated requests require it and a trusted
  origin. Login/recovery check origin as well.
- Refresh-safe session bootstrap, protected `/workspace`, logout and logout-all.
  Normal sessions default to 12 hours; explicit remember-me has a 30-day absolute
  limit. A browser timer clears authentication/private UI at expiry; server expiry
  and ownership checks remain authoritative. Same-origin tabs clear cached private
  views on login/logout/recovery changes using a credential-free BroadcastChannel,
  with generation guards preventing stale loads from restoring a cleared view. Cross-device revocation is enforced on
  the next request, not through a claimed real-time push channel.
- Existing native bearer API clients remain supported. Separate-host browser API
  connections retain the old temporary in-memory bearer behavior; persistent cookie
  login requires same-site integration. No token is stored in localStorage in either
  mode. The recommended production deployment serves UI and API from one origin.
- Persistent per-account lockout after five failures (15 minutes), plus the existing
  bounded per-IP authentication limiter. Unknown-user checks perform password work;
  recovery responses do not disclose whether an address is eligible.
- Single-use random reset tokens are stored only as hashes, expire in 15 minutes and
  are sent as URL fragments to avoid HTTP access logs. The UI removes them from the
  address bar, including same-document navigation to a second recovery link. Successful
  reset revokes every session of that user, clears the requesting browser cookie and
  requires sign-in again. Request cooldowns and hourly limits persist in the database.
- New signup email verification records ownership proof. Migrated local users have
  unknown verification status rather than an invented verified flag. They retain
  password login, and can confirm their email from an authenticated session before
  enabling email-only recovery. Hosted identity mappings remain separate and blocked.

The UI retains existing private batch deletion and exports; a new irreversible
whole-account deletion workflow was not introduced. Email delivery uses the SMTP
implementation with verified TLS, not a JavaScript fake. Live SMTP delivery is
unverified until real credentials and a recipient test are supplied in deployment.

## Migration and deployment

`20261025_browser_auth` adds session kind, persistent lockout state and reset records.
`20261025_verified_email` adds nullable verification provenance and binds authenticated
verification challenges to existing user IDs. Existing IDs, passwords, financial rows
and bearer credentials are preserved. Legacy users are not linked or renamed by email.
Downgrade revokes cookie credentials instead of turning them into bearer credentials;
verification metadata is intentionally not guessed on re-upgrade.

[Deployment instructions](V3_DEPLOYMENT.md) describe the integrated non-root Python
3.12 image, persistent data volume, same-origin Caddy TLS proxy, mail settings and
backup/restart requirements. No Docker ports were published for the container smoke
check, no certificate was issued and no production environment was started. The
Caddy configuration was validated only. Operator approval is still required for any
future deployment or hosted cutover.

## Executed validation

| Check | Actual result |
|---|---|
| Backend `python -m pytest tests matching/tests` | 121 passed |
| Root store/migration suites | 8 passed |
| `node --test milaan/frontend/tests/*.test.mjs` | 36 passed |
| Playwright desktop/mobile suites | 12 passed |
| Live HTTP demo check | All five original scenarios and manual confirmation/review/private export passed |
| Alembic upgrade/check and migration round trips | Passed, no schema drift; legacy IDs/hash/bearer session retained |
| Docker image build with tested dependency constraints | Passed |
| `python scripts/container_smoke.py` | Passed: non-root, UI assets, CSRF, data/session persistence across restart, logout revocation |
| Compose schema / Caddy validation | Passed; no public deployment |
| Frontend syntax, Python compilation, dependency check, whitespace check | Passed |

Total: **177 automated tests passed**, plus HTTP, container and configuration checks.
There are no skipped or expected-failure tests in these runs. Starlette's existing
httpx TestClient deprecation warning remains.

The browser suites use actual application handlers, temporary synthetic databases and
a test-only captured SMTP transport. The transport is outside the application package
and Docker image, has no HTTP inbox endpoint, accepts only example.com addresses and
removes its private temporary mailbox after the test server exits. Fixed-IP browser
runs disable only the per-IP middleware limiter via the existing testing setting;
a dedicated testing=False test verifies the sixteenth request is rejected. Account
lockouts, CSRF, persistence and ownership checks remain active in browser tests.

Coverage includes bad credentials, signup/password mismatch, duplicate email, OTP,
recovery invalid token/reuse/expiry/concurrency, remembered and expired sessions,
legacy email confirmation, logout-all, another seller's records, CSV mapping,
receipt upload, reconciliation, human decisions, exports and combined allocations.
Browser checks exercise 1440px and 390px contexts plus 320px and 768px layouts,
including login dialog overflow and reduced motion. Before/after screenshots are
real local captures using synthetic data only.

During validation, a reset-link same-document navigation bug and a rapid import
cancel/reopen race were corrected. A concurrent batch-deletion read now handles
missing claim/order records safely. Dense workspace typography/contrast and the
inherited checkbox width rule were corrected after visual inspection. Browser
refresh retains private session access without persisting a token in web storage.

## Genuine before and after captures

| View | Before | After |
|---|---|---|
| Desktop homepage | [Before](screenshots/v3-before-home-desktop.png) | [After](screenshots/v3-home-desktop.png) |
| Mobile homepage | [Before](screenshots/v3-before-home-mobile.png) | [After](screenshots/v3-home-mobile.png) |
| Desktop authentication | [Before](screenshots/v3-before-auth-desktop.png) | [After](screenshots/v3-auth-desktop.png) |
| Mobile authentication | [Before](screenshots/v3-before-auth-mobile.png) | [After](screenshots/v3-auth-mobile.png) |
| Saved results | — | [Desktop](screenshots/results-desktop.png), [mobile](screenshots/results-mobile.png) |
| Reviewed imports | — | [Desktop](screenshots/import-desktop.png), [mobile](screenshots/import-mobile.png) |
| Payment allocations | — | [Desktop](screenshots/allocation-desktop.png), [mobile](screenshots/allocation-mobile.png) |

Local navigation/DOM/resource observations are saved as
[desktop JSON](screenshots/v3-performance-desktop.json) and
[mobile JSON](screenshots/v3-performance-mobile.json). They are headless local
observations, not production Lighthouse results, field performance or an FPS
promise. Real Android/iPhone hardware, assistive-technology testing and broader
browser/performance audits remain external validation.

## Remaining boundaries

Live Sites source/identity access, its provider replacement policy, hosted-user
migration, real SMTP deliverability, real-domain HTTPS, PostgreSQL runtime, production
load/distributed abuse controls and external portfolio editing remain unverified or
blocked. The deployment is a single-machine SQLite path; it is not claimed to be a
multi-node production architecture. Existing retention and evidence/settlement limits
still apply. No live user account or hosted financial record was modified.
