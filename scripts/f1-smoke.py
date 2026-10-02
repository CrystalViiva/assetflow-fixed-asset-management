"""Bounded F1 smoke against a disposable PostgreSQL database, never the app database.

Uses existing configured PostgreSQL credentials to create/drop a unique database.
No credentials, tokens, or database dumps are printed or written to files.
"""

import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import psycopg
from django.conf import settings
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def seed():
    import django

    django.setup()
    from accounts.models import User
    from assets.models import Asset, AssetCategory
    from organizations.models import Organization

    # This child must only ever connect to the random database selected by the parent.
    assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
    assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f1_")
    organization = Organization.objects.create(name="F1 smoke", code="F1SMOKE")
    User.objects.create_user(
        os.environ["F1_SMOKE_EMAIL"], os.environ["F1_SMOKE_PASSWORD"],
        organization=organization, role="ASSET_MANAGER",
    )
    category = AssetCategory.objects.create(
        organization=organization, name="Equipment", code="EQ", default_useful_life_months=36,
    )
    for number in (1, 2):
        Asset.objects.create(
            organization=organization, category=category, asset_tag=f"F1-SMOKE-{number:02}",
            name=f"Smoke asset {number}", purchase_cost="999999999999999999.99",
        )


def run():
    database = settings.DATABASES["default"]
    name = "assetflow_f1_" + uuid.uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    admin = psycopg.connect(
        dbname="postgres", user=database["USER"], password=database["PASSWORD"],
        host=database["HOST"] or "127.0.0.1", port=database["PORT"] or 5432,
        connect_timeout=5, autocommit=True,
    )
    environment = os.environ.copy()
    user = urllib.parse.quote(database["USER"], safe="")
    password = urllib.parse.quote(database["PASSWORD"], safe="")
    host = database["HOST"] or "127.0.0.1"
    db_port = database["PORT"] or 5432
    environment.update({
        "DATABASE_URL": f"postgresql://{user}:{password}@{host}:{db_port}/{name}",
        "F1_SMOKE_DATABASE": name, "F1_SMOKE_EMAIL": "smoke@example.test",
        "F1_SMOKE_PASSWORD": secrets.token_urlsafe(32),
        "F1_SMOKE_URL": f"http://127.0.0.1:{port}/api/v1",
        "DEBUG": "false", "SECURE_SSL_REDIRECT": "false", "ALLOWED_HOSTS": "127.0.0.1,localhost",
    })
    server = None
    created = False
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        created = True
        for command in (
            [sys.executable, "backend/manage.py", "migrate", "--noinput", "--verbosity=0"],
            [sys.executable, str(Path(__file__).resolve()), "--seed"],
        ):
            result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=120, creationflags=flags, check=False)
            if result.returncode:
                raise RuntimeError("Isolated database setup failed; captured output withheld to protect configuration.")
        server = subprocess.Popen(
            [sys.executable, "backend/manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
            cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
        )
        for _ in range(40):
            try:
                with urllib.request.urlopen(environment["F1_SMOKE_URL"] + "/health/", timeout=1) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            raise RuntimeError("Isolated Django server did not become ready.")
        result = subprocess.run(
            ["node", "--import", "tsx", "scripts/f1-api-smoke.ts"], cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=60, creationflags=flags, check=False,
        )
        if result.returncode:
            for line in result.stdout.splitlines():
                if line.startswith("SMOKE:"):
                    print(line)
            raise RuntimeError("Frontend API smoke failed; captured output withheld to protect temporary credentials.")
        print(result.stdout.strip())
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
        if created:
            # Drop only the exact randomly generated database this process created.
            assert name.startswith("assetflow_f1_") and len(name) == 45
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print("Disposable PostgreSQL database removed; application database untouched.")
        admin.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--seed"]:
        seed()
    else:
        try:
            run()
        except Exception as error:  # noqa: BLE001 -- Do not print exception bodies containing credentials.
            print(f"F1 smoke unavailable/failed ({type(error).__name__}); no connection details printed.")
            if isinstance(error, RuntimeError):
                print(str(error))
            sys.exit(1)
