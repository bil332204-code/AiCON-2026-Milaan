# Milaan V4 — Resend HTTPS verification and password recovery

25 October 2026. Branch `feat/milaan-v4-resend-auth`, based on main `f985d6b`
(PR #6). No deployment, real email send, hosted-user modification or design change
was performed. PostgreSQL, private S3, cookies, CSRF, ownership checks and all
reconciliation behavior remain in place. This change requires no schema migration
and no additional runtime dependencies (`httpx` is already pinned).

## Render Free configuration — prepare, do not apply yet

Render Free can block outbound SMTP ports. The application now sends transactional
email exclusively to `https://api.resend.com/emails` over HTTPS/443. There is no SMTP
fallback, local email file queue, daemon or background delivery worker. Delivery is
attempted within the requesting API call; Render Free sleep/cold starts can delay
requests. An accepted provider response does not prove inbox delivery. Existing
always-on retention scheduling requirements still apply to private S3 erasures;
HTTPS email does not make sleeping instances an expiry scheduler.

Keep the Neon/S3/cookie configuration from
[Render readiness](RENDER_NEON_READINESS.md) and update these server-only variables:

| Variable | Value / purpose |
|---|---|
| `RESEND_API_KEY` | Secret sending key for the intended Resend account/domain; enter through Render's secret environment UI |
| `EMAIL_FROM` | Single sender mailbox on a Resend-verified domain, e.g. `Milaan <no-reply@your-verified-domain>` |
| `EMAIL_DELIVERY_VERIFIED` | `false` until an authorized operator verifies actual inbox delivery |
| `ALLOW_REGISTRATION` | **`false`** until live delivery checks pass and the owner separately approves opening signup |
| `REQUIRE_EMAIL_VERIFICATION` | `true` |
| `APP_ENV` | `production` |
| `PUBLIC_ORIGIN` | Exact approved HTTPS application origin; used for reset links |

Both [Render](../deploy/render-neon.env.example) and
[Compose](../deploy/production.env.example) templates leave registration closed.
Delete obsolete SMTP bindings during a later approved configuration change; SMTP
variables are no longer read. No real key belongs in Git, frontend configuration,
build arguments, logs, screenshots or chat. Use a domain-scoped sending key where
supported and rotate it through the secret manager. Missing credentials are allowed
while signup is closed, so existing login and health do not depend on mail delivery;
a send attempt fails safely. A key without EMAIL_FROM, invalid/multiple sender
mailboxes, whitespace in a key, and production signup without the delivery gate
fail configuration validation. The gate is an operator acknowledgement, not an
automatically verified fact, and provider acceptance never sets it.

## Delivery and failure semantics

The shared adapter sends plain-text verification codes and password reset links
with a server-side Authorization header. TLS verification is enabled; redirects
and ambient HTTP proxy settings are disabled. The destination is fixed in code,
not derived from the recipient or an environment-supplied URL. Explicit phase
limits are three seconds to connect, five seconds to read/write and two seconds
for the client pool. At most two attempts are made. Transport failures, 429 and
5xx can retry once with the same random idempotency key and identical payload.
Retry waits are bounded to one second; a long provider rate-limit window fails
safely instead of holding the request open. 4xx configuration/authentication errors,
redirects and malformed successes fail safely. There is no unbounded retry loop.

An accepted response must contain a nonempty message ID, which is not exposed to
the client. Provider error bodies, authorization headers, recipients, OTPs and
reset tokens are never logged by this adapter. Recovery logs only a generic
configuration warning; verification returns a generic 503. Do not enable HTTP
wire/body logging, APM body capture or provider SDK debug logging in production.

Verification retains its hashed OTP, ten-minute expiry, attempt limit, resend
cooldown and database-backed hourly cap. Failed delivery rolls back the verification
change, so no account is created and an existing challenge is not overwritten by a
failed attempt. If a provider accepts mail but its response is lost, retries use
idempotency; on total request failure, an emailed code may be unusable after rollback.
Request a new code after the relevant cooldown. Provider send and database commit
cannot be made atomic; this release does not claim guaranteed delivery or a durable
email outbox across process termination.

Recovery retains a generic response for unknown, unverified, throttled and failed
recipient cases. Failed delivery still commits the request's hashed reset grant and
cooldown/counter so an outage does not bypass throttling; no usable token is returned
to the caller. Only verified mailbox owners qualify. Tokens expire in 15 minutes,
are single-use and revoke all user sessions after reset. Links use the trusted
PUBLIC_ORIGIN and a URL fragment; tokens are not put in application access logs or
browser localStorage. Email providers/mailboxes necessarily receive the message.
Disable click/link tracking and open tracking for authentication mail in Resend's
domain configuration, and verify that link rewriting preserves the reset fragment.
No tracking configuration or DNS record was changed by this task.

## Later live verification and release checklist

1. Obtain owner approval for deployment/configuration separately. Keep registration
   closed, retain backups and existing identities, and deploy a reviewed pinned SHA
   using the existing Neon/S3 procedures. No real user data needs modification.
2. Configure a Resend-verified sender domain with its required DNS records and
   SPF/DKIM/DMARC policy. Confirm sending scope, quota and recipient restrictions;
   provider testing senders can be restricted to the account owner's address.
3. Enter RESEND_API_KEY and EMAIL_FROM securely. Do not print them or run a startup
   test that sends mail automatically. Configure provider delivery/bounce monitoring
   without logging token-bearing message bodies. Disable tracking for auth mail.
4. Using only authorized synthetic/private test accounts, verify the authenticated
   existing-account email challenge and recovery while public registration stays
   disabled. Confirm actual inbox delivery, sender alignment, timestamps, mobile
   link behavior, OTP expiry/reuse, reset single-use/expiry, old-session revocation
   and subsequent login. Use a disposable staging environment for the signup flow;
   do not temporarily open the production registration endpoint for this test.
5. Test invalid/revoked credentials, rate limiting, provider outage and no SMTP
   connectivity. Confirm generic errors, secret-free logs and persisted cooldowns.
   Review provider suppression/bounce state if accepted messages do not arrive.
6. Record successful live evidence without copying codes, tokens or keys. Only then
   may an authorized operator set EMAIL_DELIVERY_VERIFIED=true. Keep
   ALLOW_REGISTRATION=false until the owner explicitly approves signup. This task
   does neither. Revoke the acknowledgement after sender/domain/account changes
   until delivery is rechecked.
7. Rollback means restoring the prior compatible image/configuration deliberately;
   previous releases used SMTP, which may not work on Render Free. Do not enable
   registration or discard existing accounts/session data as a rollback shortcut.

## Validation

Automated HTTP mocks exercise the actual Resend adapter and API flows without real
network email. Browser tests use the existing private synthetic mail capture; they
validate authentication UI behavior, not Resend inbox delivery. The PostgreSQL/S3
runner uses isolated local PostgreSQL and an S3 HTTP emulator, not real Neon.
Executed checks:

| Check | Result |
|---|---|
| Backend/matching, SQLite | 168 passed; 3 PostgreSQL-only tests skipped |
| Same suites, local PostgreSQL 17 + S3 HTTP emulator | 171 passed; none skipped |
| Root store/migration | 8 passed |
| Frontend unit regressions | 36 passed |
| Desktop/mobile browser workflows | 12 passed |
| Live HTTP demo checks | Five original scenarios, receipt confirmation, saved review, private export passed |
| Updated Docker build and container smoke | Passed: non-root app, CSRF, persistence/session after restart, logout revocation |
| Compose configuration, dependency consistency, compilation, frontend syntax, whitespace | Passed |

No remote CI result, live Resend inbox delivery, Neon provider validation or Render
deployment is claimed. The existing Starlette/httpx TestClient deprecation warning
remains. The frontend and screenshot files are unchanged in the branch.
