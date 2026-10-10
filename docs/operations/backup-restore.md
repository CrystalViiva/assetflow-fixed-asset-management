# Backup and restoration procedure

The scripts in `scripts/ops/` create an encrypted PostgreSQL custom-format dump and a separate encrypted archive of private evidence/export storage. They do not back up secrets; keep the secret-manager recovery procedure separate. The scripts require `pg_dump`, `pg_restore`, `age`, `tar`, and `sha256sum` on an operator host. `BACKUP_DIR` must be an access-controlled, off-host mounted location in production. Never point this procedure at a database unless its identity and customer impact are known.

## Create a backup

Set `DATABASE_URL`, `PRIVATE_MEDIA_ROOT`, `BACKUP_DIR`, and an age recipient public key from the approved secret-management process in the operator's environment. Then run `bash scripts/ops/backup.sh`. The script uses restrictive file permissions, validates the custom dump archive, encrypts the database and private storage separately, and writes checksums. It does not print database contents or credentials. Configure external retention/lifecycle policy on the backup location and alert on missing backups; the script intentionally does not delete prior bundles.

## Verify a bundle

Set `BACKUP_AGE_IDENTITY` to the protected recovery identity file and `BACKUP_BUNDLE` to one bundle directory, then run `bash scripts/ops/verify-backup.sh`. This verifies ciphertext checksums, decryption, the PostgreSQL archive index, and private tar archive index. **That is not a restore test.**

## Restore drill (isolated disposable environment only)

1. Start a fresh, isolated PostgreSQL instance with no customer data, network-restricted to the operator, and a new empty database named for the drill.
2. Decrypt `database.dump` into an access-controlled temporary directory and restore using `pg_restore --no-owner --no-acl --dbname="$DISPOSABLE_DATABASE_URL" database.dump`.
3. Extract private storage into a new empty disposable directory; never overwrite an existing volume.
4. Point a matching application build at only the disposable database and restored file directory. Run Django checks, migrations (expect no pending drift), tenant/API smoke checks, and artifact size/hash reads.
5. Record backup timestamp, image/commit, restore start/end, database record counts, artifact integrity findings, elapsed time, and operator. Destroy the disposable resources under the test environment's own cleanup process after evidence is retained.

Do not use `--clean`, restore into a production URL, overwrite an existing storage path, or use a database name whose environment is unclear. Target RPO/RTO must be selected with the customer/provider and measured; a small synthetic drill is not a customer recovery promise.

## Executed encrypted application drill

`python scripts/ops/recovery_drill.py --port <disposable-port> --output <new-directory>` requires PostgreSQL client tools and age/age-keygen on PATH. It refuses the default database port, creates its own two uniquely named databases, migrates the source application and activates two synthetic managed companies. It encrypts/decrypts a custom-format PostgreSQL dump and private-file archive, restores into its own target, checks migration completeness, active companies/subscriptions, audit rows, API identity and cross-tenant denial, exact Decimal totals and private-file SHA256, then rejects an incorrect age key. Both databases and temporary identities/plaintext are cleaned up. The encrypted bundle and JSON evidence remain; the ephemeral drill key is intentionally not retained.

The latest continuation passed this drill on 2026-10-10: **68 migration records**, two active companies, two managed subscriptions, four audit records, cross-tenant user detail denied, numeric total `1234567890.13`, matching private-file hash, wrong key rejected; elapsed **63.90 seconds**. This supersedes the earlier 67-migration/56.70-second local drill. See the [executed validation record](../commercial/validation-2026-10-10.md) for the exact command and source state. This validates the local dump/encrypt/restore primitives and application recovery. It does not validate the Bash operator backup script end to end on a hosting provider, off-host retention, production-size recovery, or the owner's key-recovery procedure.
