"""Encrypted PostgreSQL + private-file recovery drill, restricted to disposable local DBs.

Requires pg_dump/pg_restore/psql/createdb and age/age-keygen on PATH.
Creates its own databases and synthetic evidence. Never accepts a source application DB.
Leaves the encrypted bundle and JSON evidence in --output; deletes only its own DBs.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--user", default="assetflow")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.port == 5432:
        parser.error("Use a dedicated disposable cluster on a non-default port.")
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.update(PGHOST="127.0.0.1", PGPORT=str(args.port), PGUSER=args.user)
    for key in ("PGSERVICE", "PGSERVICEFILE", "PGDATABASE", "DATABASE_URL"):
        os.environ.pop(key, None)
    suffix = uuid.uuid4().hex
    source, target = f"af_drill_source_{suffix}", f"af_drill_restore_{suffix}"
    created = []
    start = time.monotonic()
    try:
        for database in (source, target):
            run(["createdb", database])
            created.append(database)
        run(
            [
                "psql",
                "-X",
                "--set=ON_ERROR_STOP=1",
                "-d",
                source,
                "-c",
                "CREATE TABLE recovery_probe (id integer PRIMARY KEY, cost numeric(18,2)); INSERT INTO recovery_probe VALUES (1, 1234567890.12), (2, 0.01);",
            ]
        )
        with tempfile.TemporaryDirectory(prefix="assetflow-drill-") as work:
            work = Path(work)
            private = work / "private"
            private.mkdir()
            evidence = private / "synthetic-evidence.txt"
            evidence.write_text(
                "AssetFlow synthetic private evidence\n", encoding="utf-8"
            )
            root = Path(__file__).resolve().parents[2]
            app_env = dict(
                os.environ,
                DATABASE_URL=f"postgresql://{args.user}@127.0.0.1:{args.port}/{source}",
                DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
                ASSETFLOW_ENV="test",
                DEBUG="false",
                ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
                SECURE_SSL_REDIRECT="false",
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                FRONTEND_BASE_URL="http://localhost:3000",
                BILLING_PROVIDER="local_sandbox",
                CELERY_BROKER_URL="memory://",
                CELERY_RESULT_BACKEND="cache+memory://",
                PRIVATE_MEDIA_ROOT=str(private),
                DRILL_PASSWORD=secrets.token_urlsafe(32),
            )
            manage = [sys.executable, str(root / "backend/manage.py")]
            run([*manage, "migrate", "--noinput"], env=app_env, cwd=root)
            seed = """
import os
from uuid import uuid4
from accounts.models import User
from accounts.identity_services import provision, accept_ticket, ticket_token
operator = User.objects.create_user('drill-operator@example.test', None, is_platform_operator=True)
for number in (1, 2):
    record = provision(actor=operator, key=uuid4(), name=f'Drill {number}', code=f'DRILL{number}', email=f'drill{number}@example.test')
    accept_ticket(token=ticket_token(record.invitation), purpose='INVITE', password=os.environ['DRILL_PASSWORD'])
"""
            run([*manage, "shell", "-c", seed], env=app_env, cwd=root)
            key = work / "identity.txt"
            run(["age-keygen", "-o", str(key)])
            recipient = run(["age-keygen", "-y", str(key)]).stdout.decode().strip()
            dump = work / "database.dump"
            run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "-d",
                    source,
                    "-f",
                    str(dump),
                ]
            )
            archive = work / "private.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(private, arcname="private")
            for original in (dump, archive):
                encrypted = args.output / (original.name + ".age")
                run(
                    [
                        "age",
                        "--encrypt",
                        "--recipient",
                        recipient,
                        "--output",
                        str(encrypted),
                        str(original),
                    ]
                )
                original.unlink()
                run(
                    [
                        "age",
                        "--decrypt",
                        "--identity",
                        str(key),
                        "--output",
                        str(original),
                        str(encrypted),
                    ]
                )
            run(
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-acl",
                    "-d",
                    target,
                    str(dump),
                ]
            )
            restored = work / "restored"
            with tarfile.open(archive) as tar:
                tar.extractall(restored, filter="data")
            actual = (
                run(
                    [
                        "psql",
                        "-X",
                        "-At",
                        "-d",
                        target,
                        "-c",
                        "SELECT count(*),sum(cost)::text FROM recovery_probe;",
                    ]
                )
                .stdout.decode()
                .strip()
            )
            assert actual == "2|1234567890.13", actual
            restore_env = {
                **app_env,
                "DATABASE_URL": f"postgresql://{args.user}@127.0.0.1:{args.port}/{target}",
                "PRIVATE_MEDIA_ROOT": str(restored / "private"),
            }
            run([*manage, "migrate", "--check"], env=restore_env, cwd=root)
            check = """
from accounts.models import User, IdentityTicket
from organizations.models import Organization
from commercial.models import Subscription
from audit.models import AuditLog
from django.db.migrations.recorder import MigrationRecorder
from rest_framework.test import APIClient
assert Organization.objects.filter(is_active=True).count() == 2
assert Subscription.objects.filter(state='MANAGED').count() == 2
assert IdentityTicket.objects.filter(consumed_at__isnull=False).count() == 2
assert AuditLog.objects.count() == 4
first = User.objects.get(email='drill1@example.test')
second = User.objects.get(email='drill2@example.test')
assert first.organization_id != second.organization_id
client = APIClient()
client.force_authenticate(first)
assert client.get('/api/v1/auth/me/').status_code == 200
assert client.get('/api/v1/admin/users/').data['count'] == 1
assert client.get(f'/api/v1/admin/users/{second.pk}/').status_code == 404
print(f'MIGRATIONS={MigrationRecorder.Migration.objects.count()}')
"""
            restored_check = run(
                [*manage, "shell", "-c", check], env=restore_env, cwd=root
            )
            digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
            assert (
                hashlib.sha256(
                    (restored / "private" / evidence.name).read_bytes()
                ).hexdigest()
                == digest
            )
            # Wrong identities must fail; ciphertext alone must not reveal customer records.
            wrong = work / "wrong.txt"
            run(["age-keygen", "-o", str(wrong)])
            denied = subprocess.run(
                ["age", "-d", "-i", str(wrong), str(args.output / "database.dump.age")],
                capture_output=True,
                check=False,
            )
            assert denied.returncode != 0
            report = {
                "status": "passed",
                "postgres_rows": 2,
                "decimal_total": "1234567890.13",
                "private_sha256": digest,
                "wrong_identity_denied": True,
                "django_restore": {
                    "active_tenants": 2,
                    "managed_subscriptions": 2,
                    "audit_events": 4,
                    "cross_tenant_user_denied": True,
                    "migration_count": int(
                        restored_check.stdout.decode().split("MIGRATIONS=")[-1].strip()
                    ),
                },
                "elapsed_seconds": round(time.monotonic() - start, 2),
                "scope": "Synthetic disposable database and files only; not a production recovery guarantee",
                "application_commit": run(["git", "rev-parse", "HEAD"])
                .stdout.decode()
                .strip(),
            }
            (args.output / "evidence.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(report))
    finally:
        for database in reversed(created):
            run(["dropdb", database])


if __name__ == "__main__":
    main()
