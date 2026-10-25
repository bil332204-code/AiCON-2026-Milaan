# Public SaaS launch gates

**Review checklist only; no settings are changed by this document.**

- [ ] Production sender configured in a private secrets manager (never in Git).
- [ ] An authorized **real production** verification/recovery email arrives in the intended inbox, and a full end-to-end test proves OTP expiry, one-time reset, session revocation and login.
- [ ] Explicit product-owner approval to enable self-service registration; no temporary bypass of email ownership.
- [ ] Documented safe user-support/contact route (currently **not configured**); customer data requests have secure identity checks.
- [ ] Privacy and Terms have reviewed effective dates, retention/backups, third-party data handling, account eligibility, and appropriate legal review.
- [ ] Independent scheduled private receipt cleanup runs during web-service sleeps, with monitoring and recovery procedure.
- [ ] Automatic backups/restore plan covers both DB and private objects; restore rehearsal on synthetic data.
- [ ] Abuse protections and monitoring reviewed, including sensitive-log redaction.
- [ ] Rehearsed staging checks, CI passing at intended commit, backup plan and explicit deployment approval.

**Until every applicable gate is approved, the public site and fictional demo may remain accessible while new-account registration remains closed.** This is deliberate and must not be misrepresented as an invite-only service or a bank connection.
