#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

for name in DATABASE_URL PRIVATE_MEDIA_ROOT BACKUP_DIR BACKUP_AGE_RECIPIENT; do
  if [[ -z "${!name:-}" ]]; then
    printf 'Required environment variable %s is not set.\n' "$name" >&2
    exit 2
  fi
done
for command_name in python3 pg_dump pg_restore age tar sha256sum; do
  command -v "$command_name" >/dev/null || {
    printf 'Required command not found: %s\n' "$command_name" >&2
    exit 2
  }
done
[[ -d "$PRIVATE_MEDIA_ROOT" ]] || {
  printf 'Private storage directory does not exist: %s\n' "$PRIVATE_MEDIA_ROOT" >&2
  exit 2
}
mkdir -p -- "$BACKUP_DIR"
backup_root="$(cd -- "$BACKUP_DIR" && pwd -P)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
temp_root="$(mktemp -d "$backup_root/.assetflow-backup.XXXXXXXX")"
final_dir="$backup_root/assetflow-$stamp"
[[ ! -e "$final_dir" ]] || { printf 'Backup destination already exists.\n' >&2; exit 2; }
cleanup() { rm -rf -- "$temp_root"; }
trap cleanup EXIT
trap cleanup ERR INT TERM

export ASSETFLOW_PG_SERVICE_FILE="$temp_root/pg_service.conf"
export PGSERVICEFILE="$ASSETFLOW_PG_SERVICE_FILE"
export PGPASSFILE="$temp_root/pgpass"
python3 - <<'PY'
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

parsed = urlparse(os.environ["DATABASE_URL"])
if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path:
    raise SystemExit("DATABASE_URL must be a PostgreSQL connection URL.")
host = parsed.hostname
port = str(parsed.port or 5432)
database = unquote(parsed.path.lstrip("/"))
user = unquote(parsed.username or "")
password = unquote(parsed.password or "")
query = parse_qs(parsed.query)
service = [f"host={host}", f"port={port}", f"dbname={database}", f"user={user}"]
if query.get("sslmode"):
    service.append(f"sslmode={query['sslmode'][0]}")
Path(os.environ["ASSETFLOW_PG_SERVICE_FILE"]).write_text(
    "[assetflow_backup]\n" + "\n".join(service) + "\n", encoding="utf-8"
)
escape = lambda value: value.replace("\\", "\\\\").replace(":", "\\:")
Path(os.environ["PGPASSFILE"]).write_text(
    ":".join((escape(host), escape(port), escape(database), escape(user), escape(password)))
    + "\n",
    encoding="utf-8",
)
os.chmod(os.environ["PGPASSFILE"], 0o600)
PY

mkdir -- "$temp_root/bundle"

pg_dump --format=custom --no-owner --no-acl --dbname="service=assetflow_backup" --file="$temp_root/database.dump"
pg_restore --list "$temp_root/database.dump" >/dev/null
tar --create --file="$temp_root/private-storage.tar" --directory="$(dirname -- "$PRIVATE_MEDIA_ROOT")" "$(basename -- "$PRIVATE_MEDIA_ROOT")"
cat >"$temp_root/manifest.txt" <<EOF
format=assetflow-backup-v1
created_at_utc=$stamp
application_commit=$(git rev-parse HEAD 2>/dev/null || printf unknown)
database_archive=database.dump
private_storage_archive=private-storage.tar
configuration=restore-from-approved-secret-manager
EOF
for item in database.dump private-storage.tar manifest.txt; do
  age --encrypt --recipient "$BACKUP_AGE_RECIPIENT" --output "$temp_root/bundle/$item.age" "$temp_root/$item"
done
(cd -- "$temp_root/bundle" && sha256sum ./*.age >SHA256SUMS)
mv -- "$temp_root/bundle" "$final_dir"
printf 'Encrypted backup bundle created: %s\n' "$final_dir"
printf 'Store the identity recovery material separately from this bundle.\n'
