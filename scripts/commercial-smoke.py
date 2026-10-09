"""Run Django/PostgreSQL/browser journeys with Vite or a built frontend behind local nginx."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import psycopg
from psycopg import sql


def frontend_server(root, out, env, nginx):
    if not nginx:
        return "vite", [
            "node",
            "node_modules/vite/bin/vite.js",
            "--host",
            "127.0.0.1",
            "--port",
            "3007",
            "--strictPort",
        ]
    nginx = nginx.resolve()
    with (out / "build.log").open("w", encoding="utf-8") as build_log:
        subprocess.run(
            ["node", "node_modules/vite/bin/vite.js", "build"],
            cwd=root,
            env=env,
            check=True,
            stdout=build_log,
            stderr=subprocess.STDOUT,
        )
    (out / "logs").mkdir()
    (out / "temp").mkdir()
    config = (root / "nginx.assetflow.conf").read_text()
    config = config.replace("${ASSETFLOW_INGRESS_PROXY_CIDR}", "127.0.0.1/32")
    config = config.replace("listen 80;", "listen 127.0.0.1:3007;")
    config = config.replace("/usr/share/nginx/html", f'"{(root / "dist").as_posix()}"')
    config = config.replace("http://web:8000", "http://127.0.0.1:8017")
    config = config.replace(
        "/srv/assetflow/static/", f'"{(out / "static").as_posix()}/"'
    )
    mime = nginx.parent / "conf/mime.types"
    if not mime.exists():
        mime = Path("/etc/nginx/mime.types")
    config = (
        "events { worker_connections 128; }\nhttp {\n"
        f'include "{mime.as_posix()}";\n' + config + "\n}\n"
    )
    path = out / "nginx.conf"
    path.write_text(config, encoding="utf-8")
    command = [str(nginx), "-p", out.as_posix() + "/", "-c", path.as_posix()]
    checked = subprocess.run([*command, "-t"], capture_output=True, check=False)
    if checked.returncode:
        raise RuntimeError(checked.stderr.decode(errors="replace"))
    return "nginx", [*command, "-g", "daemon off; master_process off;"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port", type=int, required=True, help="Disposable local PostgreSQL port"
    )
    parser.add_argument(
        "--nginx",
        type=Path,
        help="Optional local nginx executable for built-frontend validation",
    )
    args = parser.parse_args()
    if args.port == 5432:
        parser.error(
            "Use a dedicated disposable cluster, not the default PostgreSQL port."
        )
    root = Path(__file__).resolve().parent.parent
    out = root / f".codex-browser-{uuid.uuid4().hex[:8]}"
    out.mkdir()
    email = out / "email"
    email.mkdir()
    scratch = out / "tmp"
    scratch.mkdir()
    database = f"af_browser_{uuid.uuid4().hex}"
    env = dict(
        os.environ,
        DATABASE_URL=f"postgresql://assetflow@127.0.0.1:{args.port}/{database}",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
        DEBUG="false",
        ASSETFLOW_ENV="staging",
        SECURE_SSL_REDIRECT="false",
        ALLOWED_HOSTS="127.0.0.1,localhost,testserver",
        EMAIL_BACKEND="django.core.mail.backends.filebased.EmailBackend",
        EMAIL_FILE_PATH=str(email),
        FRONTEND_BASE_URL="http://127.0.0.1:3007",
        PRIVATE_MEDIA_ROOT=str(out / "private"),
        STATIC_ROOT=str(out / "static"),
        TRUSTED_PROXY_NETWORKS="127.0.0.1/32",
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="cache+memory://",
        SELF_SERVICE_ENABLED="true",
        BILLING_PROVIDER="local_sandbox",
        DISABLE_HMR="true",
        VITE_DATA_SOURCE="django",
        VITE_BACKEND_API_URL="/api/v1",
        DJANGO_DEV_PROXY_TARGET="http://127.0.0.1:8017",
        ASSETFLOW_DISPOSABLE_SMOKE="1",
        SMOKE_PASSWORD=secrets.token_urlsafe(24),
        SMOKE_PYTHON=sys.executable,
        TEMP=str(scratch),
        TMP=str(scratch),
        E2E_OUTPUT_DIR=str(out / "results"),
        E2E_NGINX="1" if args.nginx else "0",
    )
    processes = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    admin_dsn = f"postgresql://assetflow@127.0.0.1:{args.port}/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(
                sql.Identifier(database)
            )
        )
    start = time.monotonic()
    try:
        subprocess.run(
            [sys.executable, "backend/manage.py", "migrate", "--noinput"],
            cwd=root,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        code = "import os; from accounts.models import User; User.objects.create_user('browser-operator@example.test', os.environ['SMOKE_PASSWORD'], is_platform_operator=True)"
        subprocess.run(
            [sys.executable, "backend/manage.py", "shell", "-c", code],
            cwd=root,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        frontend_name, frontend_command = frontend_server(root, out, env, args.nginx)
        for name, command in [
            (
                "django",
                [
                    sys.executable,
                    "backend/manage.py",
                    "runserver",
                    "127.0.0.1:8017",
                    "--noreload",
                ],
            ),
            (frontend_name, frontend_command),
        ]:
            log = (out / f"{name}.log").open("w", encoding="utf-8")
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=root,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
            log.close()
        for url in ("http://127.0.0.1:8017/api/v1/ready/", "http://127.0.0.1:3007"):
            deadline = time.monotonic() + 45
            while True:
                try:
                    with urllib.request.urlopen(url, timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError(
                            f"Smoke server failed to start; inspect {out}"
                        ) from None
                    time.sleep(0.3)
        result = subprocess.run(
            ["node", "node_modules/@playwright/test/cli.js", "test"],
            cwd=root,
            env=env,
            creationflags=flags,
            check=False,
        )
        evidence = {
            "exit_code": result.returncode,
            "elapsed_seconds": round(time.monotonic() - start, 2),
            "scope": f"Local Django runserver/PostgreSQL/{frontend_name}/Chrome; not hosted/container/production",
            "artifacts": str(out),
        }
        (out / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(evidence))
        return result.returncode
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )


if __name__ == "__main__":
    sys.exit(main())
