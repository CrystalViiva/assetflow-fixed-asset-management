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

Do not use `--clean`, restore into a production URL, overwrite an existing storage path, or use a database name whose environment is unclear. The application has not yet completed a restore drill in this assignment, so no RPO/RTO or backup-validated claim is made. Target RPO/RTO must be selected with the customer/provider and measured.
