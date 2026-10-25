> **Historical phase-1 findings only.** Legal/contact placeholders in the body were superseded by the source-backed draft pages and [public launch review](PUBLIC_LAUNCH_REVIEW.md). Current production remains governed by the [launch gates](PUBLIC_LAUNCH_GATES.md).

# Milaan Phase 1 — evidence-led implementation and security review

**Continuation:** See [Public launch review](PUBLIC_LAUNCH_REVIEW.md) for the latest fixes, owner-confirmed policy facts, validation and remaining launch gates. The original audit below is historical; its bracketed operator/support placeholders and deferred metadata notes are superseded by that review.

25 October 2026. Scope: guide, Transaction ID, CTA/arrow clarity, public draft trust pages and conservative security improvements. This change is **not** a financial compliance audit or a proof of production email delivery. No production secrets, real seller records or matching decisions were edited.

## 1. Seller guide — English and Roman Urdu

**Before:** `milaan/frontend/dist/index.html:59` was a single technical guide with "configuring the backend" and "retained allocations". It had no language control.

**After:** `milaan/frontend/dist/index.html` includes four numbered steps in both English and Roman Urdu, a worked fictional PKR 3,500 example, accurate meanings of SHIP/HOLD/REVIEW, an explanation of the origin of the Transaction ID, conservative missing/partial-reference guidance, CSV download guidance, no-signup demo and account limits. `milaan/frontend/dist/guide.js:1-16` manages the native-dialog language toggle with `hidden` and `aria-pressed`. `milaan/frontend/dist/phase1.css` retains the existing dark look.

**Tests:** `milaan/frontend/tests/guide-content.test.mjs`, `milaan/backend/tests/test_public_pages.py::test_home_and_guide_include_reference_explanation_and_bilingual_steps`; pre-existing browser modal/workspace tests remain part of CI.

**Risks and what I did not check:** The language is Roman Urdu, not Urdu script. The translations need review with Pakistani sellers and full mobile/browser keyboard testing. The FAQ section dynamically inserted by the account UI is not fully translated.

## 2. Transaction ID — exact matching behavior, no rules changed

**Before:** `milaan/frontend/dist/index.html:41-48` showed fictional `MLN778810` without saying its source. `milaan/frontend/dist/engine.js:116-119` contains the fictional demo records that use this prefix. `MLN` is **not** a Milaan-generated format.

**After:** The landing page, guide and visible result/input labels use **Transaction ID**. The customer finds it on their payment confirmation screen/receipt; the seller checks the same value against the credit in their statement. The illustration is explicitly labeled fictional. We deliberately retained the existing demo fixture IDs so the interactive demo and its regression snapshots stay consistent.

**Actual backend matcher branches** (verified source `milaan/backend/app/matcher.py`):
- Lines **9-13, 34-49** identify full references, shared proofs and possible credits, including amount/time candidates without a complete reference.
- Lines **85-97** reject unreadable evidence, wrong account, reused reference/screenshot, reversal or non-successful status before making any match.
- Lines **98-108** classify screenshot amount discrepancy as AMOUNT_CONFLICT / UNDERPAYMENT / OVERPAYMENT / COMBINED_PAYMENT, always REVIEW.
- Lines **109-127** require coverage, unique unused credit, exact amount/full reference, acceptable posting time and independently verified ID correspondence before automatic SHIP.
- Lines **128-137**: missing or partial reference produces POSSIBLE_MATCH if a candidate exists, else PARTIAL_REFERENCE; both REVIEW. A complete unmatched reference may produce HOLD only after necessary coverage and posting-window checks.
- Lines **145-150** revoke automatic SHIP when multiple orders contest one credit.
- Same full ID on two orders is normally REUSED_PROOF (lines **89-90**), both REVIEW. A different duplicate-source scenario can produce CONTESTED_CREDIT.

**Tests:** `milaan/backend/tests/test_rules.py:25-43,71-79` and new tests at end of that file; `milaan/frontend/tests/engine.test.mjs:3,9,11-16,40-43`; `milaan/backend/tests/test_payment_allocations.py:160-180`.

**Risks and what I did not check:** Actual bank/mobile providers may format their IDs differently. Current `full_ref` policy is only a conservative completeness heuristic, not a provider verification API. Manual allocations are separate, seller-reviewed operations; the guide intentionally does not claim all REVIEW cases are irreversible.

## 3. CTA and in-app arrows

**Before:** `milaan/frontend/dist/index.html:32,35,50-52` used inconsistent CTA labels and an external-link arrow on internal actions. `milaan/frontend/dist/app.js:54` also used a download arrow that implied external navigation.

**After:** Public primary action is **Try the demo**. Secondary is **Use your own files**. Internal links use right/down arrows, while the message distinguishes an account-free fictional demo from a signed-in seller workspace (email/password). Existing action handlers, layouts and animations remain unchanged.

**Tests:** `milaan/frontend/tests/guide-content.test.mjs` checks CTA text and arrows; existing `milaan/frontend/tests/browser-session.test.mjs` and browser workflow tests cover workspace/auth behavior.

**Risks and what I did not check:** Remaining action labels inside specialized import/review dialogs may be context-specific. This is not a full UX usability test or automated screenshot comparison.

## 4. Public Privacy, Terms and About/Contact

**Before:** `docs/PRIVACY.md:1-59` is an **internal retention/privacy note**, not a routed site policy. `milaan/backend/app/main.py:697-714` exposed home/guide/auth, but no `/privacy`, `/terms`, `/about` HTML policy routes.

**After:** `milaan/frontend/dist/privacy.html`, `terms.html`, `about.html` each provide an independent page, title, meta description, canonical, visible [BRACKETED] missing facts and lawyer-review notice. `milaan/backend/app/main.py` adds allowlisted public routes. Landing, workspace, and each policy page link to all pages through their footers. Privacy text carefully distinguishes default **seven-day batch expiry** from asynchronous receipt erasure and unknown backup retention.

**Tests:** `milaan/backend/tests/test_public_pages.py::test_legal_pages_are_public_and_reachable_without_login`; `milaan/backend/tests/test_readiness.py::test_public_legal_pages_have_correct_canonical_and_are_indexable`.

**Risks and what I did not check:** This is **NOT FINAL LEGAL LANGUAGE**. [SUPPORT_EMAIL], [TEAM MEMBER NAMES], ownership, location, processing terms, backup retention, data-rights request process, fee terms and governing law require owner verification and qualified legal review. No invented certifications or guaranteed immediate deletion are claimed. Open Graph and complete metadata for `/guide` belong to Phase 2.

## 5. Security audit — code-level findings with precise evidence

| Control / finding | Existing verified file:lines | Existing tests | Phase 1 change / remaining gap |
|---|---|---|---|
| CSV formula injection | `milaan/frontend/dist/engine.js:106-107`; `milaan/backend/app/parsing.py:97-106` | `milaan/frontend/tests/engine.test.mjs:17`, `milaan/backend/tests/test_api.py:51-59` | **FIXED:** originally prefixed `=,+,-,@` and whitespace leading to formulas but did **not** prefix a cell beginning with a plain tab/carriage return alone; added both and new regression tests |
| Gemini server-side key, structured extraction, untrusted image text | `milaan/backend/app/config.py:37-39`; `milaan/backend/app/extraction.py:7-14,18-47` | `milaan/backend/tests/test_extraction.py:9-39` | Existing backend key + Pydantic schema; no client-side Gemini API key use observed in examined integration; full repo secret-history audit **not performed** |
| Cloud consent, no automatic shipping on extraction | `milaan/backend/app/main.py:605-612`; `milaan/backend/app/extraction.py:50-61`; `milaan/backend/app/matcher.py:85-126` | `milaan/backend/tests/test_api.py:114-125`; `test_extraction.py:9-13` | Existing two-read checks and explicit consent. Real provider output accuracy **not verified** |
| Credit double-spend, seller budget locking and idempotency | `milaan/backend/app/main.py:647-679`; `milaan/backend/app/allocations.py:1-36` | `milaan/backend/tests/test_payment_allocations.py:160-181,238-257`; `milaan/backend/tests/test_api.py:60-65` | Core logic untouched. PostgreSQL race guarantees need ongoing hosted load/stress tests |
| Per-user access, IDOR, private receipt image | `milaan/backend/app/main.py:117-156,519-548` | `milaan/backend/tests/test_api.py:39-49`; `milaan/backend/tests/test_receipt_storage.py:14-45` | Existing owner checks; no signed public image URLs. No external penetration test |
| Upload type/size/metadata/path safety | `milaan/backend/app/storage.py:13-23,38-42`; `milaan/backend/app/config.py:46-50`; `milaan/backend/app/main.py:519-540` | `milaan/backend/tests/test_api.py:76-85`; `test_receipt_storage.py:133-151` | Existing Pillow content inspection, JPEG re-encode to drop metadata, UUID filenames. No malware scanner / external antivirus proof |
| Seven-day expiry and actual file erasure | `milaan/backend/app/config.py:36`; `milaan/backend/app/jobs.py:119-143` | `milaan/backend/tests/test_api.py:87-100`; `test_receipt_storage.py:46-67,101-118` | DB expiry and durable object deletion queue exist. **HIGH operational gap:** sleeping Free instance may not perform timely cleanup; independent scheduler and provider backup/versioned-object retention are NOT verified |
| Rate limiting, CSRF and sessions | `milaan/backend/app/middleware.py:5-28`; `milaan/backend/app/main.py:117-128`; `milaan/backend/app/browser_auth.py` | `milaan/backend/tests/test_browser_auth.py:36-64,138-148`; `milaan/backend/tests/test_readiness.py:11-18` | Existing process-local IP limits & DB-backed lockouts. Shared limiter still needed at scale; no public signup until Resend works |
| CSP/HSTS, framing, CORS | `milaan/backend/app/middleware.py:15-18,50-85`; `milaan/backend/app/main.py:89-94`; `milaan/backend/app/config.py:31,125-126` | `milaan/backend/tests/test_readiness.py:29-48` and new header/canonical tests | **FIXED:** X-Frame-Options DENY, permission restrictions and production-only HSTS; legal paths get canonical redirects. **GAP:** current CSP only includes frame-ancestors/base-uri/object-src; full script/style CSP is not yet audited. |
| Sensitive logging | `milaan/backend/app/main.py:96-99`; `milaan/backend/app/emailer.py` | `milaan/backend/tests/test_resend.py` provider-error sanitization tests | Reviewed main application paths; complete production log scrub, backup redaction and provider visibility audits still needed |
| Financial edge cases | `milaan/backend/app/matcher.py:85-151` | `milaan/backend/tests/test_rules.py`, `test_payment_allocations.py` | Added reference cases with **no rule change**; comprehensive Phase 2 matrix for fees, partial payments, timezone boundaries and reversals still required |

**Before/after excerpts for the fixed CSV edge case** (matching rules unchanged):

```diff
- if(/^[\s]*[=+@-]/.test(s)) s="'"+s
+ if(/^(?:[\t\r]|\s*[=+@-])/.test(s)) s="'"+s
```

```diff
- return "'" + s if re.match(r"^\s*[=+@-]", s) else s
+ return "'" + s if re.match(r"^(?:[\t\r]|\s*[=+@-])", s) else s
```

Security header policy is also recorded in the unified PR diff. **Never promise that all nine security subtopics are fully solved:** backup restore, independent cleanup scheduling, multi-instance rate limiting, full CSP and actual production email delivery are outside this branch.

**Risks and what I did not check:** No destructive live requests, real financial data tests, Resend secrets, live Gemini calls, performance benchmarks, or provider-specific compliance validation. Frontend screenshot regression, full browser accessibility, mobile Lighthouse 95+, Phase 2 edge cases and hosted TLS/headers require separate verification.

## No matching-rule modifications

This branch intentionally does not edit `milaan/backend/app/matcher.py`, `milaan/backend/matching/rules.py`, `milaan/backend/app/allocations.py`, schema/migrations, retention defaults, or credit decision behavior. The tests codify the existing rules without weakening them.


## Revised source-of-truth notes (2026-10-25)

**Which code runs on milaan.app?** Render production service `milaan-production-2026` is configured to build `main` in `bil332204-code/AiCON-2026-Milaan` with the root `Dockerfile`. The separate ChatGPT Sites instance is `milaan-studio.bil332204.chatgpt.site`. This PR touches the **Render production repository** only; it has not been merged or deployed. The distinction is now clarified in `README.md:8-36`.

**Two identities, no conflation:** `order_ref` is the seller's **Order number**, not payment evidence. `transaction_id` is the customer's payment-app or bank **Transaction ID**, compared with the seller's statement credit. Preserve both exact CSV keys and API schemas because `docs/IMPORT_CONTRACTS.md:13-35` requires them. Seller-facing labels in `index.html`, `app.js` and `import-preview.js` show the two terms separately; API field names remain unchanged.

**Successful statuses only:** `milaan/backend/app/matcher.py:157-160` accepts only success, successful, completed, paid, payment successful, transaction successful (trimmed, case-insensitive). `milaan/frontend/dist/engine.js:73` also returns REVIEW/STATUS_CONFLICT for unrecognized statuses. Existing `milaan/backend/tests/test_rules.py:45-51`, `milaan/frontend/tests/engine.test.mjs:20-27` and new explicit "Payment sent" tests prove it remains REVIEW. **Proposed, not implemented:** choose among Successful / Pending / Failed / Unclear while retaining a separate immutable original provider-status string and requiring manual verification; any "unclear" value must continue to REVIEW. No status mapping or decision algorithm was changed.

**Full guide SHIP rule:** Confirmed receipt fields, recognized successful status, correct receiving account, exact order total, declared complete statement coverage for receipt timestamp, full Transaction ID corresponding to exactly one credit, that credit's exact amount, no greater than 24 hours between credit and screenshot time, verified sender/receiver ID correspondence, no duplicate image or credit, reversal, or allocation conflict; never bank settlement confirmation. Source `docs/IMPORT_CONTRACTS.md:38-54`, `milaan/backend/app/matcher.py:85-150`.

**Seller-facing privacy source:** `docs/PRIVACY.md:3-31,42-57`. Implemented `milaan/frontend/dist/privacy.html` covers seven-day expiry, cleanup while worker runs, private receipt JPEG processing, optional Gemini with explicit consent, Resend auth-email data flow (not financial data), browser-local OCR potentially downloading an external engine, passwords/cookies and deletion limitations. It retains placeholders for hosting/backups, operator identity, legal approval, OCR provider details, support and rights. No invented legal claims.

**Existing controls — do not rebuild:**
- Receipt EXIF stripping: `milaan/backend/app/storage.py:8-23`; test `milaan/backend/tests/test_receipt_storage.py:14-45`.
- Ownership and private access: `milaan/backend/app/main.py:136-156,542-548`; test `test_api.py:39-49`.
- Expiry deletion: `milaan/backend/app/config.py:36`, `jobs.py:119-136`; tests `test_api.py:87-100` and `test_receipt_storage.py:101-118`.
- Hashed passwords: `milaan/backend/app/security.py:5-24`; test `test_browser_auth.py:67-79,81-102`.
- Cookie auth/CSRF: `milaan/backend/app/browser_auth.py:7-32`; tests `test_browser_auth.py:36-64,118-135`.
- SHIP/HOLD/REVIEW, reused proof, wrong amount: `milaan/backend/app/matcher.py:85-150`; tests `test_rules.py:25-43`, `test_payment_allocations.py:60-106,160-180`.
- Result CSV formula protection ALREADY existed: `milaan/backend/app/parsing.py:97-106`, `milaan/frontend/dist/engine.js:106-107`; tests `test_api.py:51-59`, `engine.test.mjs:17`. The only edit strengthens tab/CR edge cases and adds tests. No export rewrite.

**Repository hygiene:**
- `.gitignore` strengthened for credentials, local exports, SQLite sidecars and backups. Does not ignore source/demo fixture CSV.
- Dedicated full-history scan via `.github/workflows/windows-secrets-audit.yml` found **one** `generic-api-key`-classified match: `tests/browser/auth-visual.spec.mjs:6`, introduced in commit `8bbbcf559446`. That line is a deliberately synthetic browser-test password, not identified as an active provider token. Value deliberately not copied to logs or this report. After manually identifying this as a deliberately synthetic fixture, one exact historical fingerprint was added to `.gitleaksignore`; the full-history scan passes. New findings are NOT suppressed. Automated pattern scans do not prove absence of other leaks.
- `SETUP.bat` uses Python 3.12 fallback and runs the interactive `setup_admin.py`; `START_DEMO.bat` opens `START_MILAAN.bat` and `START_DEMO_STORE.bat`. The disposable Windows GitHub runner executed `SETUP.bat` and `START_DEMO.bat` successfully: Milaan health HTTP 200 and demo store HTTP 200 (run 40202954091). It used a preconfigured synthetic operator, so it did not test the interactive password prompt. Its preseeded operator deliberately does not test the interactive email/password prompt.
- Proposed GitHub repository description (cannot update repository metadata with currently exposed GitHub connector actions): **"Milaan helps small sellers compare orders, payment screenshots and supplied statements with explainable SHIP/HOLD/REVIEW suggestions. No bank connection or automatic payments."**
- License: intentionally **NOT added**. Ask owner to choose MIT, Apache-2.0, GPL-3.0, proprietary or another license before changing code distribution terms.
- **Layout proposal only — no moves:** `apps/milaan-api/`, `apps/milaan-web/`, `apps/demo-store/`, `docs/`, `tests/`, `deploy/`, `scripts/`, `windows/`. Reorganization would require rewriting Docker, relative imports, CI, Windows paths and docs and should be a separate approved PR.

**Risks and what I did not check:** The detected historical match was a deliberately synthetic test password, excluded by one exact fingerprint (not by ignoring its rule or directory); a scanner cannot prove absence of unrecognized secrets. Windows runner tested both application starts but not interactive password entry or an end-user Windows desktop. GitHub repository description was proposed, not changed. Neither LICENSE nor layout moved. Privacy placeholders require owner review. Public registration remains gated because real Resend provider delivery has not been confirmed.


### Verified workflow evidence
- Windows startup test: [successful Windows launch, HTTP 200 for both services](https://github.com/bil332204-code/AiCON-2026-Milaan/actions/runs/40202954091).
- Full-history secret scan (with the narrowly scoped synthetic fixture fingerprint): [workflow](https://github.com/bil332204-code/AiCON-2026-Milaan/actions/workflows/windows-secrets-audit.yml). This is a pattern scan, not a proof that no credentials exist.
- Complete Phase 1 unified diff: [Draft PR #15](https://github.com/bil332204-code/AiCON-2026-Milaan/pull/15/files). Release CI results should be verified on the latest commit before merging.
