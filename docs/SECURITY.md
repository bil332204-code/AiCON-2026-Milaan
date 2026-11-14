# Security notes

What protects Milaan, and what an operator still has to do. Based on the audit of 14 Nov 2026.

## Built into the application

| Area | Protection |
| --- | --- |
| Seller isolation | Every object is looked up through its owner; cross-seller requests return 404 (21 probes tested). |
| Sign-in | scrypt password hashes; hashed session tokens in a `__Host-` HttpOnly cookie; CSRF token + Origin check; optional authenticator-app (TOTP) step with replay protection; 14-day "remember me". |
| Brute force | Real client IP from `CF-Connecting-IP` / `X-Forwarded-For`, trusted only from a private proxy hop. 15 auth requests per minute per IP; 5 failed sign-ins per account per network and 20 per account overall per 15 minutes; no hard account lock. Owner is emailed about repeated failures. |
| Signup | Same reply whether or not the email already has an account; the real owner gets a notice. Breached passwords refused (Have I Been Pwned range API, k-anonymity) when `CHECK_BREACHED_PASSWORDS` is on (default in production). |
| Statement PDFs | Parsed in a child process with no secrets in its environment, 320 MB memory cap, 15 s CPU cap, 30 s wall cap and bounded decompression (32 MB per stream, 96 MB total). |
| Images | Pillow 13 limited to JPEG/PNG/WEBP parsers, 25 MP cap, JPEG decoded at reduced scale, re-encoded and stripped of metadata. |
| Memory | Heavy uploads run one per seller at a time and `HEAVY_UPLOAD_SLOTS` (default 2) at once. Per-seller cap of `MAX_SELLER_RECEIPTS` stored screenshots (default 1000). |
| Payments | Used bank credits are copied to `credit_ledger` when a batch expires or is deleted and kept `CREDIT_LEDGER_DAYS` (default 400), so one payment cannot fund two orders. SHIP/HOLD decisions are kept in `decision_log` for the same period. |
| AI | Gemini output always needs the seller's confirmation; daily cap `MAX_DAILY_EXTRACTIONS` (default 200) per seller. |
| Browser | CSP with `script-src 'self'` plus the pinned, integrity-checked OCR script; no inline scripts; frame, sniffing and referrer headers; HSTS with subdomains in production. API docs are off in production. |
| Privacy | Settings has "Download all my data", "Download decision history" and "Delete my account". |
| Supply chain | Dependabot, weekly pip-audit + Bandit (`security.yml`), GitHub Actions pinned to commit SHAs, offline ML code excluded from the image. |

## Operator checklist

- [ ] Render: Starter plan (no sleeping), health check path `/api/health`, delete unused services.
- [ ] Uptime monitor on `https://milaan.app/` with alerts to your phone.
- [ ] Neon: confirm point-in-time restore is on and try one restore into a branch.
- [ ] Rotate the Resend sending key and update `RESEND_API_KEY` on Render.
- [ ] DNS (Cloudflare): root SPF `v=spf1 -all`, DMARC `p=quarantine` then `p=reject`, CAA records, DNSSEC (add the DS record at Name.com).
- [ ] Turn on two-step sign-in for Name.com, Cloudflare, Render, Neon, Resend and GitHub.
- [ ] Legal review of the privacy policy and terms before charging customers.
