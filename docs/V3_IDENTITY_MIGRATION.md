# Hosted identity migration — blocked until authoritative access exists

The hosted Sites source, provider administration, schema and identity/data mappings
are not available in this environment. The supplied public homepage/guide requests
failed through the proxy, and no Sites connector or source checkout was available.
The GitHub branches belong to the local kit. Provider replacement support cannot be
inferred from a URL, a screenshot or the presence of an authentication button.

**No hosted migration, account linking, ownership rewrite or provider cutover has
been performed. Keep the working hosted provider and its data intact.**

## Safe boundary already implemented for the local kit

Existing local user IDs, password hashes, financial ownership and bearer credentials
survive migrations. Password hashes upgrade after valid password authentication.
No legacy email is automatically marked verified. New signups verify email; older
users can prove their current authenticated account and its mailbox before enabling
password recovery. This is local account hardening, not proof that a hosted ChatGPT
identity belongs to a new email/password account.

## Required evidence before any hosted linking implementation

1. Obtain authorized access to the actual hosted source, supported deployment/identity
   controls and read-only schema/ownership information. Identify actual provider
   subjects and financial owner relationships rather than inventing field names.
2. Verify whether the provider permits custom authentication. If it does not, keep
   its login intact and use a separately approved host with an explicit export/import
   migration supported by that provider. Do not work around platform restrictions.
3. Take a recoverable encrypted backup of records, private assets, identity mappings
   and relevant retention metadata. Establish expected row/asset counts privately.
4. Design linking that requires authenticated proof of the old provider identity AND
   verified possession of the new account/email, plus explicit consent. A matching
   email string, user-supplied subject ID or unsigned export is not sufficient.
   Use expiring one-time link grants bound to both identities, uniqueness checks and
   a private audit. Never infer or manufacture a ChatGPT user's password.
5. Dry-run owner remapping on staging with transactional referential checks, asset
   checksums and counts. Preserve record IDs, retention choices and private asset
   boundaries. Do not expose financial records in a public migration report.
6. Prove login, recovery, owned-record access, another-user isolation, export and
   rollback for representative consented test accounts. Test actual email and HTTPS.
7. Obtain explicit cutover approval. Keep the old provider reachable until users can
   safely reach their records; support those who cannot link yet. Never orphan an
   account simply because it has not completed migration.

The exact adapter, linking endpoints and hosted schema migration must be written
against the verified provider/source. They are deliberately not fabricated in this
branch. The deployment image is a reusable alternative, not an automatically
connected copy of the hosted database.
