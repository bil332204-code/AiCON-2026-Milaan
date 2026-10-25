# Source repository hygiene review

This is a non-destructive, synthetic-only maintenance report. Repo access is public; do not place credentials, personal details, real records or private operational metadata in commits, issues, comments or CI logs.

## Verified source practices
- Root `.gitignore` and `.dockerignore` exclude common local environments, credentials, runtime databases, uploads, exports and backups. The CI release checks use controlled fake accounts and synthetic files.
- `setup_admin.py` receives the operator password interactively and writes it to an ignored local environment file; it does not ship a shared default account or password.
- Windows `SETUP.bat` prefers Python 3.12, installs pinned runtime requirements and sets up a private local operator. `START_DEMO.bat`, `START_DEMO_STORE.bat` and `START_MILAAN.bat` use quoted paths and local ports. These scripts were previously exercised in an isolated Windows CI runner. The interactive operator prompt and every user's personal Windows setup are not guaranteed by CI.
- The existing workflow runs a **redacted full fetched Git-history secret scan** using the same scanner already present in this repo. The scan is not a guarantee that all possible sensitive information is absent. Re-run after changes and investigate any failure privately; never post secret values or detailed findings in a public PR.

## New CI check
`python scripts/check_tracked_artifact_names.py` uses `git ls-files --cached -z` and fails if sensitive-looking file paths were accidentally tracked; the command prints counts only. This is a filename/placement safeguard, not a secret-content scanner.

## Windows fresh-clone checklist
1. Start from a new disposable folder, install Python 3.12 and ensure network access for pinned packages.
2. Run `SETUP.bat`; choose a test-only operator, not a real financial account.
3. Launch `START_DEMO.bat`; confirm local application and synthetic demo-store routes load without port collision.
4. Sign in with the synthetic operator in both services; import supplied fictional samples, reconcile and export.
5. Exit both processes and check that all credentials and resulting synthetic data remain outside Git.

## Proposed root organization — **no files moved**
Keep `README.md`, `Dockerfile`, `milaan/`, `deploy/`, `tests/`, `scripts/`, `docs/` and `demo-store/` at the root. Later, with explicit approval and Windows regression testing, consider moving legacy release narratives under `docs/history/` and relocating wrapper batch files to a discoverable `scripts/windows/` directory with compatibility shims. No movement or deletion is proposed in this PR.

## Repository public description (owner applies)
"Payment evidence reconciliation for sellers: SHIP / HOLD / REVIEW recommendations from orders, receipts and receiving-bank exports."

## License options (owner chooses later)
- MIT: short permissive grant, few restrictions.
- Apache-2.0: permissive with express patent grant.
- GPL-3.0: copyleft redistribution duties when distributing modified software.
- Proprietary/all rights reserved: no public reuse grant (default absent a license), but collaboration/third-party code requires clear terms.
No license file added automatically.

## GitHub settings (owner approval required)
Review repository branch protection, PR approvals, secret-scanning entitlement, dependency update alerts and minimal connector access. No account or repository settings are changed by this PR.

## Review summary
Review existing open PRs by independent area; do not merge draft branches without completed CI and an approved deployment rollback plan. Production enrollment and infrastructure are separate from source hygiene.
