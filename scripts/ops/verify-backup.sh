#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ -z "${BACKUP_AGE_IDENTITY:-}" || -z "${BACKUP_BUNDLE:-}" ]]; then
  printf 'Set BACKUP_AGE_IDENTITY and BACKUP_BUNDLE to verify a bundle.\n' >&2
  exit 2
fi
for command_name in age sha256sum pg_restore tar; do
  command -v "$command_name" >/dev/null || {
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 2
  }
done
[[ -d "$BACKUP_BUNDLE" ]] || { printf 'Backup bundle directory is missing.\n' >&2; exit 2; }
temp_root="$(mktemp -d "${TMPDIR:-/tmp}/assetflow-restore-check.XXXXXXXX")"
trap 'rm -rf -- "$temp_root"' EXIT
(cd -- "$BACKUP_BUNDLE" && sha256sum --check SHA256SUMS)
for item in database.dump private-storage.tar manifest.txt; do
  age --decrypt --identity "$BACKUP_AGE_IDENTITY" --output "$temp_root/$item" "$BACKUP_BUNDLE/$item.age"
done
pg_restore --list "$temp_root/database.dump" >/dev/null
tar --list --file="$temp_root/private-storage.tar" >/dev/null
printf 'Backup checks passed: encryption, checksums, PostgreSQL archive index, private storage archive index.\n'
printf 'This is not a database restoration drill; restore to a disposable isolated PostgreSQL database and verify application behavior before treating backups as validated.\n'
