# Milaan operations runbook (no credentials)

This runbook is a review checklist, not authorization to change infrastructure. Source: this repository's `main` branch. Production uses the root `Dockerfile` and manual releases. Work in a disposable environment before any production change.

## Release procedure
1. Read the PR diff, assert unchanged payment-decision and retention contracts, run all supported CI suites and check the pinned commit SHA.
2. Prepare a backup/restore plan for the intended environment; verify database and private-object storage are isolated from staging.
3. Deploy the **reviewed** commit to staging, not an arbitrary branch tip. Check startup migrations, anonymous homepage/guide/health, authenticating and signing out with synthetic data, and negative authorization checks.
4. Obtain separate release authorization. Deploy the *same reviewed commit* to production with auto-deploy still disabled. Confirm health, canonical HTTPS, nonpublic account routes and log health.
5. Preserve previous known-good commit and deployment metadata for rollback. **Do not reset databases to resolve an app code bug.**

## Rollback and schema changes
A code rollback means deploying an earlier reviewed application commit; rolling back schema or restoring a database is a separate, potentially destructive operation. Alembic upgrades must use a **direct** database connection, appropriate privileges and backups. Test forward migrations on disposable data first; verify backward compatibility of the earlier app before attempting rollback. Never run destructive migrations or manually modify real-user data as part of an automated test.

## Retention, restoration and operations
Default batches expire after seven days; scheduled cleanup and private-object deletion must operate even if an idle web service sleeps. Before accepting real financial records, establish a separately scheduled, monitored cleanup job and prove the complete deletion path with synthetic data. Confirm object versions, exports, provider backups and restoration behavior. A database snapshot alone does not back up receipt objects. Rehearse a coordinated restore and document recovery objectives. Track failed background work, service errors and mail delivery without logging receipt data, credentials, OTPs or reset tokens.

## Access and boundaries
Limit deployment/settings to project operators; service roles should have only necessary database and object permissions. Public visitors can view marketing/demo pages but cannot read saved customer records. Never post environment variables, database details, account identifiers, secret values, or internal infrastructure into public issues or logs.

## Launch/incident escalation
Keep self-service registration disabled until **actual production inbox delivery**, email verification/reset end-to-end, support/contact route, retention, backups and legal review are approved. When an incident occurs, preserve logs with restricted access, stop affected onboarding safely, document impact privately, and use the operator's pre-approved rollback procedure. This file is not a legal/privacy guarantee.
