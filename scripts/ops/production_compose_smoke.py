"""Build/run production images on a local Linux Docker engine with disposable data.

Uses a random, checked-empty Compose project and generated credentials. It never
accepts an application database, deployment project, SMTP recipient or payment key.
Only the resources belonging to this invocation are removed in finally.
"""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def run(command, *, env=None, capture=False, check=True):
    return subprocess.run(
        command, cwd=ROOT, env=env, text=True, capture_output=capture, check=check
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error(
            "Run on a local Linux Docker host or the production-compose CI job."
        )
    context = json.loads(run(["docker", "context", "inspect"], capture=True).stdout)[0]
    endpoint = os.environ.get("DOCKER_HOST") or context["Endpoints"]["docker"]["Host"]
    if not endpoint.startswith("unix://"):
        parser.error(
            "Remote Docker endpoints are not allowed for this disposable drill."
        )
    args.output.mkdir(parents=True, exist_ok=False)
    project = "af-smoke-" + uuid.uuid4().hex
    network = project + "-network"
    label = "com.docker.compose.project=" + project
    for kind in ("container", "volume"):
        assert not run(
            [
                "docker",
                kind,
                "ls",
                *(["--all"] if kind == "container" else []),
                "--quiet",
                "--filter",
                "label=" + label,
            ],
            capture=True,
        ).stdout.strip(), "Disposable project must be empty"
    started = time.monotonic()
    compose = None
    network_created = False
    owns_resources = False
    evidence = {"status": "failed", "project": project}
    with tempfile.TemporaryDirectory(prefix="assetflow-compose-") as directory:
        work = Path(directory)
        empty_env = work / "empty.env"
        empty_env.write_text("", encoding="utf-8")
        try:
            run(
                ["docker", "network", "create", "--label", label, network], capture=True
            )
            network_created = True
            subnet = json.loads(
                run(["docker", "network", "inspect", network], capture=True).stdout
            )[0]["IPAM"]["Config"][0]["Subnet"]
            override = work / "override.json"
            override.write_text(
                json.dumps(
                    {"networks": {"default": {"external": True, "name": network}}}
                ),
                encoding="utf-8",
            )
            env = dict(os.environ)
            env.update(
                DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
                POSTGRES_PASSWORD=secrets.token_hex(32),
                ALLOWED_HOSTS="assetflow.example.test",
                CSRF_TRUSTED_ORIGINS="https://assetflow.example.test",
                FRONTEND_BASE_URL="https://assetflow.example.test",
                SECURE_SSL_REDIRECT="true",
                SECURE_HSTS_SECONDS="31536000",
                SECURE_HSTS_INCLUDE_SUBDOMAINS="true",
                SECURE_HSTS_PRELOAD="true",
                TRUSTED_PROXY_NETWORKS=subnet,
                ASSETFLOW_INGRESS_PROXY_CIDR=subnet,
                ASSETFLOW_HTTP_PORT="0",
                EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                EMAIL_HOST="unused-smtp.invalid",
                EMAIL_HOST_USER="synthetic",
                EMAIL_HOST_PASSWORD=secrets.token_urlsafe(32),
                DEFAULT_FROM_EMAIL="noreply@assetflow.example.test",
                EMAIL_USE_TLS="true",
                CELERY_WORKER_CONCURRENCY="1",
            )
            command = [
                "docker",
                "compose",
                "--project-name",
                project,
                "--env-file",
                str(empty_env),
                "-f",
                str(ROOT / "docker-compose.production.yml"),
                "-f",
                str(override),
            ]

            def compose(*arguments, **kwargs):
                return run([*command, *arguments], env=env, **kwargs)

            config = json.loads(
                compose("config", "--format", "json", capture=True).stdout
            )
            assert all(
                value["name"].startswith(project + "_") and not value.get("external")
                for value in config["volumes"].values()
            ), "All database/storage volumes must belong to this disposable project"
            owns_resources = True
            compose("build")
            compose("up", "-d", "--wait", "db", "redis")
            compose("run", "--rm", "migrate")
            compose(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "150",
                "web",
                "worker",
                "beat",
                "frontend",
            )
            compose(
                "exec",
                "-T",
                "web",
                "python",
                "manage.py",
                "check",
                "--deploy",
                "--fail-level",
                "WARNING",
            )
            compose("exec", "-T", "web", "python", "manage.py", "migrate", "--check")
            port = compose("port", "frontend", "80", capture=True).stdout.strip()
            assert port.startswith("127.0.0.1:"), "Frontend must bind only to loopback"
            base = "http://" + port

            def request(path, body=None, expected=200):
                headers = {
                    "Host": "assetflow.example.test",
                    # Simulate the trusted TLS ingress on the owned Docker network.
                    # This exercises proxy handling, not a real TLS certificate.
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "192.0.2.10",
                    "Content-Type": "application/json",
                }
                data = None if body is None else json.dumps(body).encode()
                with urlopen(
                    Request(base + path, data=data, headers=headers), timeout=10
                ) as response:
                    assert response.status == expected, path
                    assert response.headers["X-Content-Type-Options"] == "nosniff"
                    return response.read(), response.headers

            for _ in range(20):
                try:
                    page, headers = request("/")
                    break
                except URLError:
                    time.sleep(1)
            else:
                raise AssertionError("Production frontend never became reachable")
            assert (
                b'id="root"' in page
                and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
            )
            request("/static/admin/css/base.css")
            request("/api/v1/health/")
            _, headers = request("/api/v1/ready/")
            assert "max-age=31536000" in headers["Strict-Transport-Security"]
            public = json.loads(request("/api/v1/public/config/")[0])
            assert (
                public["billing_provider"] == "disabled"
                and not public["self_service_enabled"]
            )
            request(
                "/api/v1/public/leads/",
                {
                    "request_key": str(uuid.uuid4()),
                    "kind": "DEMO",
                    "name": "Compose probe",
                    "email": "synthetic@example.test",
                    "company": "Disposable CI company",
                    "requirements": "Production image smoke",
                    "consent": True,
                },
                expected=202,
            )

            def shell(code, service="web", check=True, capture=False):
                return compose(
                    "exec",
                    "-T",
                    service,
                    "python",
                    "manage.py",
                    "shell",
                    "-c",
                    code,
                    check=check,
                    capture=capture,
                )

            shell(
                "import os; assert os.getuid() == 10001; from commercial.models import SalesLead; assert SalesLead.objects.count() == 1"
            )
            shell(
                "from django.core.files.storage import storages; from django.core.files.base import ContentFile; s=storages['assetflow_private']; assert s.save('compose/probe.txt', ContentFile(b'private-persistence')) == 'compose/probe.txt'"
            )
            private_check = "from django.core.files.storage import storages; assert storages['assetflow_private'].open('compose/probe.txt', 'rb').read() == b'private-persistence'"
            shell(private_check, "worker")
            # Wait for Beat -> Redis -> worker -> PostgreSQL, without eager/memory mode.
            for _ in range(30):
                health = compose(
                    "exec",
                    "-T",
                    "web",
                    "python",
                    "manage.py",
                    "check_operations",
                    capture=True,
                    check=False,
                )
                if health.returncode == 0:
                    print(health.stdout, flush=True)
                    break
                time.sleep(3)
            else:
                raise AssertionError(
                    "Real Beat/Redis/Celery heartbeat did not become healthy"
                )
            compose("restart", "web", "worker")
            compose(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "150",
                "web",
                "worker",
                "frontend",
            )
            shell(private_check)
            shell(private_check, "worker")
            shell(
                "from commercial.models import SalesLead; assert SalesLead.objects.count() == 1"
            )
            request("/api/v1/ready/")
            # Force an actual registered task failure; no financial data or side effect.
            shell(
                "from config.celery import app; app.send_task('operations.tasks.heartbeat', args=['invalid-probe-argument'], task_id='compose-failure-probe')"
            )
            for _ in range(20):
                result = shell(
                    "from operations.models import TaskFailure; assert TaskFailure.objects.filter(task_id='compose-failure-probe', error_type='TypeError').exists()",
                    check=False,
                    capture=True,
                )
                if result.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise AssertionError("Worker failure was not recorded")
            assert (
                compose(
                    "exec",
                    "-T",
                    "web",
                    "python",
                    "manage.py",
                    "check_operations",
                    check=False,
                ).returncode
                != 0
            )
            evidence.update(
                status="passed",
                production_images=True,
                migrations=True,
                gunicorn_nginx_postgres_redis=True,
                beat_worker_heartbeat=True,
                worker_failure_alert=True,
                private_and_database_restart_persistence=True,
                billing_disabled=True,
                real_tls=False,
                smtp_delivery=False,
                hosted_deployment=False,
                images=json.loads(
                    compose("images", "--format", "json", capture=True).stdout
                ),
            )
        finally:
            if compose and owns_resources:
                logs = compose(
                    "logs", "--no-color", "--tail", "150", capture=True, check=False
                )
                (args.output / "services.log").write_text(
                    logs.stdout + logs.stderr, encoding="utf-8"
                )
                compose("down", "--volumes", "--remove-orphans", check=False)
            if network_created:
                run(["docker", "network", "rm", network], check=False, capture=True)
            evidence["elapsed_seconds"] = round(time.monotonic() - started, 2)
            (args.output / "evidence.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
    print(
        "PASS: disposable production images, migrations, proxy, real Redis/Celery and restart persistence."
    )


if __name__ == "__main__":
    main()
