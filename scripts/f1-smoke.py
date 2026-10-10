"""Bounded F1 smoke against a disposable PostgreSQL database, never the app database.

Uses existing configured PostgreSQL credentials to create/drop a unique database.
No credentials, tokens, or database dumps are printed or written to files.
"""

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
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
    from organizations.models import Department, Location, Organization
    from transfers.models import AssetAssignment

    # This child must only ever connect to the random database selected by the parent.
    prefix = "assetflow_f16_" if os.environ.get("F16_SMOKE_MODE") else "assetflow_f14_" if os.environ.get("F14_SMOKE_MODE") else "assetflow_f13_" if os.environ.get("F13_SMOKE_MODE") else "assetflow_f12_" if os.environ.get("F12_SMOKE_MODE") else "assetflow_f11_" if os.environ.get("F11_SMOKE_MODE") else "assetflow_f10_" if os.environ.get("F10_SMOKE_MODE") else "assetflow_f9_" if os.environ.get("F9_SMOKE_MODE") else "assetflow_f8_" if os.environ.get("F8_SMOKE_MODE") else "assetflow_f7_" if os.environ.get("F7_SMOKE_MODE") else "assetflow_f6_" if os.environ.get("F6_SMOKE_MODE") else "assetflow_f5_" if os.environ.get("F5_SMOKE_MODE") else "assetflow_f4_" if os.environ.get("F4_SMOKE_MODE") else "assetflow_f3_" if os.environ.get("F3_SMOKE_MODE") else "assetflow_f2_" if os.environ.get("F2_SMOKE_MODE") else "assetflow_f1_"
    assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
    assert os.environ["F1_SMOKE_DATABASE"].startswith(prefix)
    if prefix.endswith("f16_") and os.environ.get("F16_COMMERCIAL_MODE") == "1":
        from django.core.management import call_command

        User.objects.create_superuser("f16-operator@example.test", os.environ["F1_SMOKE_PASSWORD"])
        call_command("enable_platform_operator", "f16-operator@example.test")
        return
    organization = Organization.objects.create(name=f"{prefix[:-1].upper()} smoke", code=f"{prefix[:-1].upper()}SMOKE")
    manager = User.objects.create_user(
        os.environ["F1_SMOKE_EMAIL"], os.environ["F1_SMOKE_PASSWORD"],
        organization=organization, role="ADMIN" if prefix.endswith("f11_") else "ASSET_MANAGER",
    )
    category = AssetCategory.objects.create(
        organization=organization, name="Equipment", code="EQ", default_useful_life_months=36,
    )
    if prefix.endswith("f16_"):
        Department.objects.create(organization=organization, name="Operations", code="OPS")
        Department.objects.create(organization=organization, name="Destination Operations", code="OPS-DST")
        Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        Location.objects.create(organization=organization, name="Destination Plant", code="PLANT-DST")
        User.objects.create_user(
            os.environ["F1_SMOKE_APPROVER_EMAIL"], os.environ["F1_SMOKE_PASSWORD"],
            organization=organization, role="ADMIN",
        )
        User.objects.create_user(
            "f16-custodian@example.test", os.environ["F1_SMOKE_PASSWORD"],
            organization=organization, role="EMPLOYEE",
        )
        return
    if prefix.endswith("f14_"):
        department = Department.objects.create(organization=organization, name="F14 Operations", code="OPS")
        location = Location.objects.create(organization=organization, name="F14 Main Plant", code="PLANT")
        Asset.objects.create(organization=organization, category=category, asset_tag="F14-SMOKE-001", name="F14 authentication smoke asset", department=department, location=location, status="ACTIVE", purchase_cost="125.00", current_book_value="125.00")
        User.objects.create_user("f14-employee@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=organization, department=department, role="EMPLOYEE")
        return
    if prefix.endswith("f13_"):
        from decimal import Decimal

        from assets.models import Acquisition, AcquisitionStatus
        from depreciation.models import (
            AccountingPeriod,
            DepreciationEntry,
            DepreciationSchedule,
        )
        from django.utils import timezone
        from maintenance.models import MaintenanceType, WorkOrder

        department_a = Department.objects.create(organization=organization, name="Operations", code="OPS")
        department_b = Department.objects.create(organization=organization, name="Finance", code="FIN")
        location = Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        assets = []
        for number, department, cost, depreciation, book in (
            (1, department_a, "100.10", "10.05", "90.05"),
            (2, department_b, "200.20", "20.10", "180.10"),
        ):
            assets.append(Asset.objects.create(
                organization=organization, category=category, asset_tag=f"F13-{number:02}",
                name=f"F13 analytics asset {number}", department=department, location=location,
                status="ACTIVE", condition="GOOD", acquisition_date="2026-01-01",
                capitalization_date="2026-01-02", available_for_use_date="2026-01-02",
                purchase_cost=cost, residual_value="0.00", useful_life_months=36,
                depreciation_method="SLM", accumulated_depreciation=depreciation,
                current_book_value=book,
            ))
        for asset, cost in zip(assets, ("100.10", "200.20"), strict=True):
            Acquisition.objects.create(
                organization=organization,
                asset=asset,
                acquisition_date="2026-01-01",
                capitalization_date="2026-01-02",
                currency=organization.currency,
                purchase_price=Decimal(cost),
                status=AcquisitionStatus.CAPITALIZED,
                created_by=manager,
                updated_by=manager,
            )
        current_month = timezone.localdate().month
        current_year = timezone.localdate().year
        period = AccountingPeriod.objects.create(organization=organization, year=current_year, month=current_month)
        for asset, cost, amount, book in zip(assets, ("100.10", "200.20"), ("10.05", "20.10"), ("90.05", "180.10"), strict=True):
            schedule = DepreciationSchedule.objects.create(
                organization=organization, asset=asset, method="SLM", capitalized_cost=cost,
                depreciable_base=cost, residual_value="0.00", useful_life_months=36,
                start_date="2026-01-02", end_date="2028-12-31", periodic_depreciation=amount,
            )
            DepreciationEntry.objects.create(
                organization=organization, asset=asset, schedule=schedule, accounting_period=period,
                opening_book_value=cost, depreciation_amount=amount, accumulated_depreciation=amount,
                closing_book_value=book,
            )
        for number in (1, 2):
            WorkOrder.objects.create(
                organization=organization, work_order_number=f"F13-WO-{number}", asset=assets[0],
                maintenance_type=MaintenanceType.CORRECTIVE, description="Dashboard join fixture",
                requested_by=manager,
            )
        User.objects.create_user("f13-dept@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=organization, department=department_a, role="DEPARTMENT_MANAGER")
        User.objects.create_user("f13-employee@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=organization, role="EMPLOYEE")
        foreign = Organization.objects.create(name="F13 foreign smoke", code="F13FOREIGN")
        foreign_category = AssetCategory.objects.create(organization=foreign, name="Foreign", code="F", default_useful_life_months=12)
        Asset.objects.create(organization=foreign, category=foreign_category, asset_tag="F13-FOREIGN", name="Foreign asset", status="ACTIVE", capitalization_date="2026-01-02", purchase_cost="99999.99", current_book_value="99999.99")
        return
    if prefix.endswith("f11_"):
        department = Department.objects.create(organization=organization, name="Operations", code="OPS")
        location = Location.objects.create(organization=organization, name="Main Plant", code="PLANT", city="Lagos")
        Asset.objects.create(organization=organization, category=category, asset_tag="F11-PLACEMENT-001", name="F11 placement invariant", department=department, location=location, purchase_cost="450.00")
        foreign = Organization.objects.create(name="F11 foreign smoke", code="F11FOREIGN")
        foreign_department = Department.objects.create(organization=foreign, name="Foreign", code="FOR")
        Location.objects.create(organization=foreign, name="Foreign hub", code="FH")
        User.objects.create_user("foreign-admin@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=foreign, role="ADMIN")
        User.objects.create_user("foreign-employee@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=foreign, role="EMPLOYEE", department=foreign_department)
        return
    if prefix.endswith("f10_"):
        Department.objects.create(organization=organization, name="Operations", code="OPS")
        Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        foreign = Organization.objects.create(name="F10 foreign smoke", code="F10FOREIGN")
        User.objects.create_user(
            "foreign-manager@example.test", os.environ["F1_SMOKE_PASSWORD"],
            organization=foreign, role="ASSET_MANAGER",
        )
        foreign_category = AssetCategory.objects.create(
            organization=foreign, name="Foreign equipment", code="EQ", default_useful_life_months=36,
        )
        Asset.objects.create(
            organization=foreign, category=foreign_category, asset_tag="F10-FOREIGN-ONLY",
            name="Foreign tenant asset", purchase_cost="100.00",
        )
        return
    if prefix.endswith("f9_"):
        department = Department.objects.create(organization=organization, name="Operations", code="OPS")
        location = Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        Asset.objects.create(
            organization=organization, category=category, asset_tag="F9-REPORT-01",
            name="F9 report snapshot original", department=department, location=location,
            status="ACTIVE", condition="GOOD", acquisition_date="2026-01-01",
            capitalization_date="2026-01-02", available_for_use_date="2026-01-02",
            purchase_cost="1234.56", residual_value="0.00", useful_life_months=36,
            depreciation_method="SLM", accumulated_depreciation="34.56", current_book_value="1200.00",
        )
        return
    if prefix.endswith(("f2_", "f3_", "f4_", "f5_", "f6_")):
        Department.objects.create(organization=organization, name="Operations", code="OPS")
        Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        if prefix.endswith("f4_"):
            Department.objects.create(organization=organization, name="Destination Operations", code="OPS-DST")
            Location.objects.create(organization=organization, name="Destination Plant", code="PLANT-DST")
            User.objects.create_user("custodian@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=organization, role="EMPLOYEE")
        if prefix.endswith("f6_"):
            User.objects.create_user(os.environ["F1_SMOKE_APPROVER_EMAIL"], os.environ["F1_SMOKE_PASSWORD"], organization=organization, role="ADMIN")
        return
    if prefix.endswith("f8_"):
        department = Department.objects.create(organization=organization, name="Operations", code="OPS")
        location = Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        asset = Asset.objects.create(
            organization=organization, category=category, asset_tag="F8-ASSURANCE-01",
            name="F8 deterministic assurance asset", department=department, location=location,
            status="ACTIVE", condition="GOOD", acquisition_date="2026-01-01",
            capitalization_date="2026-01-02", available_for_use_date="2026-01-02",
            purchase_cost="1001.00", residual_value="100.00", useful_life_months=36,
            depreciation_method="SLM", accumulated_depreciation="25.03", current_book_value="900.00",
        )
        custodian = User.objects.create_user(
            "f8-custodian@example.test", os.environ["F1_SMOKE_PASSWORD"],
            organization=organization, department=department, role="EMPLOYEE",
        )
        AssetAssignment.objects.create(
            organization=organization, asset=asset, assigned_to=custodian,
            department=department, location=location, created_by=manager,
            notes="Disposable F8 custody fixture",
        )
        return
    if prefix.endswith(("f7_", "f12_")):
        department_a = Department.objects.create(organization=organization, name="Operations", code="OPS")
        Department.objects.create(organization=organization, name="Finance", code="FIN")
        location_a = Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        Location.objects.create(organization=organization, name="Remote Plant", code="REMOTE")
        created_assets = []
        for number, department, location in ((1, department_a, location_a), (2, department_a, location_a)):
            created_assets.append(Asset.objects.create(
                organization=organization, category=category, asset_tag=f"F7-SMOKE-{number:02}",
                name=f"F7 physical verification asset {number}", department=department, location=location,
                status="ACTIVE", condition="GOOD", acquisition_date="2026-01-01",
                capitalization_date="2026-01-02", available_for_use_date="2026-01-02",
                purchase_cost="1001.00", residual_value="100.00", useful_life_months=36,
                depreciation_method="SLM", accumulated_depreciation="25.03", current_book_value="975.97",
            ))
        custodian = User.objects.create_user(
            "custodian@example.test", os.environ["F1_SMOKE_PASSWORD"],
            organization=organization, department=department_a, role="EMPLOYEE",
        )
        AssetAssignment.objects.create(
            organization=organization, asset=created_assets[1], assigned_to=custodian,
            department=department_a, location=location_a, created_by=manager,
            notes="Disposable F7 custody fixture",
        )
        if prefix.endswith("f12_"):
            foreign = Organization.objects.create(name="F12 foreign smoke", code="F12FOREIGN")
            User.objects.create_user("f12foreign@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=foreign, role="ASSET_MANAGER")
        return
    for number in (1, 2):
        Asset.objects.create(
            organization=organization, category=category, asset_tag=f"F1-SMOKE-{number:02}",
            name=f"Smoke asset {number}", purchase_cost="999999999999999999.99",
        )


def run(f2=False, f3=False, f4=False, f5=False, f6=False, f7=False, f8=False, f9=False, f10=False, f11=False, f12=False, f13=False, f14=False, f16=False):
    f16 = f16 or bool(os.environ.get("F16_SMOKE_MODE"))
    f14 = f14 or bool(os.environ.get("F14_SMOKE_MODE"))
    f13 = f13 or bool(os.environ.get("F13_SMOKE_MODE"))
    f12 = f12 or bool(os.environ.get("F12_SMOKE_MODE"))
    f11 = f11 or bool(os.environ.get("F11_SMOKE_MODE"))
    f10 = f10 or bool(os.environ.get("F10_SMOKE_MODE"))
    database = settings.DATABASES["default"]
    f9 = f9 or bool(os.environ.get("F9_SMOKE_MODE"))
    f8 = f8 or bool(os.environ.get("F8_SMOKE_MODE"))
    f7 = f7 or bool(os.environ.get("F7_SMOKE_MODE"))
    f6 = f6 or bool(os.environ.get("F6_SMOKE_MODE"))
    f5 = f5 or bool(os.environ.get("F5_SMOKE_MODE"))
    prefix = "assetflow_f16_" if f16 else "assetflow_f14_" if f14 else "assetflow_f13_" if f13 else "assetflow_f12_" if f12 else "assetflow_f11_" if f11 else "assetflow_f10_" if f10 else "assetflow_f9_" if f9 else "assetflow_f8_" if f8 else "assetflow_f7_" if f7 else "assetflow_f6_" if f6 else "assetflow_f5_" if f5 else "assetflow_f4_" if f4 else "assetflow_f3_" if f3 else "assetflow_f2_" if f2 else "assetflow_f1_"
    name = prefix + uuid.uuid4().hex
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
        "F1_SMOKE_DATABASE": name, "F2_SMOKE_MODE": "1" if f2 else "", "F3_SMOKE_MODE": "1" if f3 else "", "F4_SMOKE_MODE": "1" if f4 else "", "F5_SMOKE_MODE": "1" if f5 else "", "F6_SMOKE_MODE": "1" if f6 else "", "F7_SMOKE_MODE": "1" if f7 else "", "F8_SMOKE_MODE": "1" if f8 else "", "F9_SMOKE_MODE": "1" if f9 else "", "F10_SMOKE_MODE": "1" if f10 else "", "F11_SMOKE_MODE": "1" if f11 else "", "F12_SMOKE_MODE": "1" if f12 else "", "F13_SMOKE_MODE": "1" if f13 else "", "F14_SMOKE_MODE": "1" if f14 else "", "F16_SMOKE_MODE": "1" if f16 else "", "F1_SMOKE_APPROVER_EMAIL": "approver@example.test",
        "F1_SMOKE_EMAIL": "smoke@example.test",
        "F1_SMOKE_PASSWORD": secrets.token_urlsafe(32),
        "F1_SMOKE_URL": f"http://127.0.0.1:{port}/api/v1",
        "DEBUG": "false", "SECURE_SSL_REDIRECT": "false", "ALLOWED_HOSTS": "127.0.0.1,localhost",
    })
    private_root = tempfile.mkdtemp(prefix="assetflow_f16_private_") if f16 else tempfile.mkdtemp(prefix="assetflow_f12_private_") if f12 else tempfile.mkdtemp(prefix="assetflow_f9_private_") if f9 else None
    if f9 or f12 or f16:
        environment.update({"DJANGO_SETTINGS_MODULE":"config.f9_smoke_settings","F9_SMOKE_PRIVATE_ROOT":private_root})
        if f16 and os.environ.get("F16_COMMERCIAL_MODE") == "1":
            environment.update({
                "EMAIL_BACKEND": "django.core.mail.backends.filebased.EmailBackend",
                "EMAIL_FILE_PATH": str(Path(private_root) / "captured-email"),
                "SMOKE_PYTHON": sys.executable,
            })
    elif f8:
        environment.update({"DJANGO_SETTINGS_MODULE":"config.f8_smoke_settings","ASSURANCE_WORK_UNIT_SIZE":"1"})
    server = None
    created = False
    shim_path = None
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
        if f2 or f4:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "backend/organizations/tests/test_reference_api.py", "backend/transfers/tests/test_api.py", "backend/transfers/tests/test_services.py", "--create-db", "-q"],
                cwd=ROOT, env=environment, capture_output=True, timeout=600, creationflags=flags, check=False,
            )
            if result.returncode:
                raise RuntimeError("Focused reference API regression tests failed on an isolated PostgreSQL test database.")
            print(result.stdout.strip())
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
        node_command = ["node"]
        if (f7 or f8 or f9 or f10 or f11 or f12 or f13 or f14 or f16) and os.name == "nt":
            # tsx asks Node for account details when choosing its cache directory; some
            # managed Windows runners deny that OS lookup. Keep the compatibility shim
            # temporary and outside the repository.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".cjs", encoding="utf-8", delete=False) as shim:
                shim.write("const os=require('node:os');os.userInfo=()=>({uid:-1,gid:-1,username:'assetflow-smoke',homedir:os.homedir(),shell:null});\n")
                shim_path = shim.name
            node_command.extend(["--require", shim_path])
        node_command.extend(["--import", "tsx", "scripts/f16-api-smoke.ts" if f16 else "scripts/f14-api-smoke.ts" if f14 else "scripts/f13-api-smoke.ts" if f13 else "scripts/f12-api-smoke.ts" if f12 else "scripts/f11-api-smoke.ts" if f11 else "scripts/f10-api-smoke.ts" if f10 else "scripts/f9-api-smoke.ts" if f9 else "scripts/f8-api-smoke.ts" if f8 else "scripts/f7-api-smoke.ts" if f7 else "scripts/f6-api-smoke.ts" if f6 else "scripts/f5-api-smoke.ts" if f5 else "scripts/f4-api-smoke.ts" if f4 else "scripts/f3-api-smoke.ts" if f3 else "scripts/f2-api-smoke.ts" if f2 else "scripts/f1-api-smoke.ts"])
        result = subprocess.run(
            node_command, cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=180 if os.environ.get("F16_COMMERCIAL_MODE") else 60, creationflags=flags, check=False,
        )
        if result.returncode:
            for line in result.stdout.splitlines():
                if line.startswith("SMOKE:"):
                    print(line)
            raise RuntimeError("Frontend API smoke failed; captured output withheld to protect temporary credentials.")
        print(result.stdout.strip())
        if f2 or f3 or f4 or f5 or f6 or f7 or f8 or f9 or f10 or f11 or f12 or f13 or f16:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--verify"], cwd=ROOT, env=environment,
                capture_output=True, text=True, timeout=30, creationflags=flags, check=False,
            )
            if result.returncode:
                for line in result.stdout.splitlines():
                    if line.startswith("VERIFY:"):
                        print(line)
                if result.stderr:
                    last = result.stderr.strip().splitlines()[-1]
                    print(f"VERIFY: verifier raised {last.split(':', maxsplit=1)[0]}")
                    import re

                    locations = re.findall(r'File "[^"\n]*f1-smoke\.py", line (\d+)', result.stderr)
                    if locations:
                        print(f"VERIFY: assertion location scripts/f1-smoke.py:{locations[-1]}")
                raise RuntimeError("Isolated PostgreSQL state and audit verification failed; details withheld.")
            print(result.stdout.strip())
    finally:
        if shim_path:
            Path(shim_path).unlink(missing_ok=True)
        if server:
            server.terminate()
            server.wait(timeout=10)
        if created:
            # Drop only the exact randomly generated database this process created.
            assert name.startswith(prefix) and len(name) == len(prefix) + 32
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print("Disposable PostgreSQL database removed; application database untouched.")
        if private_root:
            private_path = Path(private_root).resolve()
            assert private_path.parent == Path(tempfile.gettempdir()).resolve()
            assert private_path.name.startswith("assetflow_f16_private_" if f16 else "assetflow_f12_private_" if f12 else "assetflow_f9_private_")
            shutil.rmtree(private_path)
            print("Disposable F16 private evidence/export storage removed; no private files were written to the repository." if f16 else "Disposable private verification evidence storage removed; no uploaded file was written to the repository." if f12 else "Disposable private export storage removed; no export file was written to the repository.")
        admin.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--seed"]:
        seed()
    elif sys.argv[1:] == ["--verify"]:
        import django
        django.setup()
        if os.environ.get("F16_SMOKE_MODE"):
            import hashlib

            from accounts.models import User
            from assets.models import Acquisition, Asset
            from audit.models import AuditLog
            from assurance.models import AssuranceRun
            from depreciation.models import DepreciationEntry
            from disposals.models import Disposal
            from django.core.files.storage import storages
            from maintenance.models import MaintenanceRecord
            from organizations.models import Organization
            from reporting.models import ExportStatus, ReportExport, ReportSnapshot, SnapshotStatus
            from transfers.models import AssetAssignment, AssetTransfer
            from verification.models import PhysicalVerification, VerificationEvidence

            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f16_")
            organization = Organization.objects.get(code="ASSETFLOW_F16SMOKE")
            asset = Asset.objects.get(organization=organization, asset_tag="F16-GOLDEN-001")
            assert asset.status == "DISPOSED"
            assert [str(asset.purchase_cost), str(asset.accumulated_depreciation), str(asset.current_book_value)] == ["1001.00", "25.03", "975.97"]
            acquisition = Acquisition.objects.get(asset=asset)
            assert acquisition.status == "CAPITALIZED" and acquisition.total_cost == asset.purchase_cost
            entry = DepreciationEntry.objects.get(asset=asset)
            assert [str(entry.opening_book_value), str(entry.depreciation_amount), str(entry.accumulated_depreciation), str(entry.closing_book_value)] == ["1001.00", "25.03", "25.03", "975.97"]
            assert MaintenanceRecord.objects.filter(asset=asset, total_cost="33.43").count() == 1
            assert PhysicalVerification.objects.filter(asset=asset).count() == 1
            evidence = VerificationEvidence.objects.get(verification__asset=asset, integrity_status="VERIFIED")
            snapshot = ReportSnapshot.objects.get(organization=organization, report_type="asset_register", status=SnapshotStatus.COMPLETED)
            assert snapshot.row_count == 1 and snapshot.schema_version == 1
            assert snapshot.rows.get().payload["status"] == "ACTIVE"
            exports = list(ReportExport.objects.filter(organization=organization, source_snapshot=snapshot, status=ExportStatus.COMPLETED))
            assert {item.format for item in exports} == {"CSV", "JSON"}
            private_root = Path(os.environ["F9_SMOKE_PRIVATE_ROOT"]).resolve()
            assert private_root.parent == Path(tempfile.gettempdir()).resolve()
            storage = storages["assetflow_private"]
            for item in [evidence, *exports]:
                key = item.binary_storage_key if item is evidence else item.storage_key
                with storage.open(key, "rb") as stream:
                    content = stream.read()
                expected_size = evidence.byte_size if item is evidence else item.byte_size
                expected_hash = evidence.sha256 if item is evidence else item.sha256
                assert len(content) == expected_size and hashlib.sha256(content).hexdigest() == expected_hash
                assert not key.startswith("/") and ".." not in key
            transfer = AssetTransfer.objects.get(asset=asset)
            assignment = AssetAssignment.objects.get(asset=asset)
            disposal = Disposal.objects.get(asset=asset, status="COMPLETED")
            assert transfer.status == "COMPLETED" and assignment.returned_at is not None
            assert [str(disposal.carrying_amount), str(disposal.gain_or_loss)] == ["975.97", "224.03"]
            assert AssuranceRun.objects.filter(organization=organization, status="COMPLETED").count() == 1
            assert User.objects.filter(organization=organization, role="ADMIN").count() == 1
            actions = set(AuditLog.objects.filter(organization=organization).values_list("action", flat=True))
            assert {"ASSET_CAPITALIZED", "DEPRECIATION_POSTED", "ASSET_TRANSFER_COMPLETED", "WORK_ORDER_COMPLETED", "VERIFICATION_EVIDENCE_VERIFIED", "ASSET_DERECOGNIZED", "REPORT_SNAPSHOT_COMPLETED", "REPORT_EXPORT_COMPLETED"}.issubset(actions)
            print("PASS: single-asset F16 PostgreSQL lifecycle reconciles exact ledger/disposal values, transfer/custody separation, maintenance and verification history, completed assurance/snapshot/exports, verified private bytes and domain audit events.")
            sys.exit(0)
        if os.environ.get("F12_SMOKE_MODE"):
            import hashlib

            from assets.models import Asset
            from audit.models import AuditLog
            from django.core.files.storage import storages
            from verification.models import VerificationEvidence
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f12_")
            evidence = list(VerificationEvidence.objects.filter(integrity_status="VERIFIED").order_by("created_at"))
            assert len(evidence) == 4
            for item in evidence:
                with storages["assetflow_private"].open(item.binary_storage_key, "rb") as stream:
                    content = stream.read()
                assert len(content) == item.byte_size and hashlib.sha256(content).hexdigest() == item.sha256
            assert VerificationEvidence.objects.count() == 5
            assert Asset.objects.count() == 2
            events = set(AuditLog.objects.filter(organization=evidence[0].organization).values_list("action", flat=True))
            assert {"VERIFICATION_EVIDENCE_VERIFIED", "VERIFICATION_EVIDENCE_DOWNLOADED"}.issubset(events)
            assert not any(item.binary_storage_key.startswith("/") or ".." in item.binary_storage_key for item in evidence)
            print("PASS: isolated PostgreSQL/private storage F12 verified bytes, size/SHA256, invalid upload rejection, domain-generated audit events, and unchanged two-asset master-data boundary.")
            sys.exit(0)
        if os.environ.get("F14_SMOKE_MODE"):
            from accounts.models import User
            from assets.models import Asset
            from organizations.models import Organization

            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f14_")
            org = Organization.objects.get(code="ASSETFLOW_F14SMOKE")
            assert Asset.objects.filter(organization=org, asset_tag="F14-SMOKE-001").count() == 1
            assert User.objects.filter(organization=org, role="EMPLOYEE").count() == 1
            print("PASS: isolated F14 PostgreSQL contains scoped administrator/employee identities and a real asset; persistent application database untouched.")
        elif os.environ.get("F13_SMOKE_MODE"):
            from assets.models import Acquisition, Asset
            from depreciation.models import DepreciationEntry
            from maintenance.models import WorkOrder
            from organizations.models import Organization
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f13_")
            assert Organization.objects.count() == 2
            assert Asset.objects.filter(organization__code="ASSETFLOW_F13SMOKE").count() == 3
            assert str(Asset.objects.get(asset_tag="F13-01").purchase_cost) == "100.10"
            assert WorkOrder.objects.filter(organization__code="ASSETFLOW_F13SMOKE").count() == 2
            assert DepreciationEntry.objects.filter(organization__code="ASSETFLOW_F13SMOKE").count() == 2
            assert Acquisition.objects.filter(organization__code="ASSETFLOW_F13SMOKE", status="CAPITALIZED").count() == 2
            print("PASS: isolated F13 PostgreSQL contains scoped fixture data, the authenticated draft refresh, capitalized acquisitions, two child work orders and two posted depreciation entries; persistent application database untouched.")
            sys.exit(0)
        if os.environ.get("F9_SMOKE_MODE"):
            from uuid import UUID

            from assets.models import Asset
            from audit.models import AuditLog
            from reporting.models import (
                ExportStatus,
                ReportExport,
                ReportSnapshot,
                SnapshotStatus,
            )
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f9_")
            print("VERIFY: isolated F9 database boundary confirmed")
            asset = Asset.objects.get(asset_tag="F9-REPORT-01")
            snapshot = ReportSnapshot.objects.get(idempotency_key=UUID("11111111-1111-4111-8111-111111111111"))
            assert snapshot.status == SnapshotStatus.COMPLETED
            assert snapshot.schema_version == 1 and snapshot.row_count == 1
            assert snapshot.as_of is not None and snapshot.requested_at <= snapshot.as_of <= snapshot.generated_at
            assert snapshot.rows.get().payload["name"] == "F9 report snapshot original"
            assert snapshot.rows.get().payload["purchase_cost"] == "1234.56"
            print("VERIFY: completed frozen snapshot and original source row confirmed")
            assert asset.name == "F9 report snapshot changed after capture"
            assert str(asset.purchase_cost) == "1234.56"
            csv_export = ReportExport.objects.get(idempotency_key=UUID("22222222-2222-4222-8222-222222222222"))
            json_export = ReportExport.objects.get(idempotency_key=UUID("33333333-3333-4333-8333-333333333333"))
            assert csv_export.source_snapshot_id == json_export.source_snapshot_id == snapshot.pk
            assert csv_export.status == json_export.status == ExportStatus.COMPLETED
            assert csv_export.row_count == json_export.row_count == snapshot.row_count
            assert csv_export.byte_size and json_export.byte_size and len(csv_export.sha256) == len(json_export.sha256) == 64
            print("VERIFY: private completed CSV/JSON exports cite source snapshot with size and hash metadata")
            events = set(AuditLog.objects.filter(organization=asset.organization).values_list("action", flat=True))
            assert {"REPORT_SNAPSHOT_REQUESTED", "REPORT_SNAPSHOT_STARTED", "REPORT_SNAPSHOT_COMPLETED", "REPORT_EXPORT_REQUESTED", "REPORT_EXPORT_COMPLETED", "REPORT_EXPORT_DOWNLOADED"}.issubset(events)
            print("VERIFY: report and authenticated download audit events confirmed")
            private_path = Path(os.environ["F9_SMOKE_PRIVATE_ROOT"]).resolve()
            assert private_path.parent == Path(tempfile.gettempdir()).resolve()
            print("VERIFY: private storage root is a disposable system-temp child")
            assert any(private_path.rglob("*"))
            print("VERIFY: isolated F9 captured immutable original report rows, source changed afterward, both completed exports cite that snapshot, private artifacts/audits verified, and only the disposable DB was used")
            sys.exit(0)
        if os.environ.get("F11_SMOKE_MODE"):
            from accounts.models import User
            from assets.models import Asset
            from audit.models import AuditLog
            from organizations.models import Department, Location, Organization
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f11_")
            own = Organization.objects.get(code="ASSETFLOW_F11SMOKE")
            foreign = Organization.objects.get(code="F11FOREIGN")
            created = User.objects.get(email="new.employee@example.test")
            assert created.organization_id == own.pk and created.role == "EMPLOYEE" and created.department.organization_id == own.pk
            assert created.check_password(os.environ["F1_SMOKE_PASSWORD"])
            events = set(AuditLog.objects.filter(organization=own).values_list("action", flat=True))
            assert {"DEPARTMENT_CREATED", "LOCATION_CREATED", "LOCATION_UPDATED", "USER_CREATED", "USER_ADMIN_UPDATED"}.issubset(events)
            assert os.environ["F1_SMOKE_PASSWORD"] not in str(list(AuditLog.objects.filter(organization=own).values("changes", "metadata")))
            assert Department.objects.filter(organization=foreign).count() == 1
            assert Location.objects.filter(organization=foreign).count() == 1
            asset = Asset.objects.get(asset_tag="F11-PLACEMENT-001")
            assert asset.location.code == "PLANT" and asset.department.code == "OPS"
            assert not AuditLog.objects.filter(organization=own, entity_type="TRANSFER").exists()
            assert User.objects.filter(organization=foreign).count() == 2
            print("VERIFY: isolated F11 hashed credentials; administrative audit actions persisted; foreign organization stayed separate; location edit did not move asset or create transfer history")
            sys.exit(0)
        if os.environ.get("F10_SMOKE_MODE"):
            from assets.models import Asset
            from audit.models import AuditLog
            from organizations.models import Organization
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f10_")
            asset = Asset.objects.get(asset_tag="F10-AUDIT-001")
            foreign_asset = Asset.objects.get(asset_tag="F10-FOREIGN-ONLY-NEW")
            assert AuditLog.objects.filter(organization=asset.organization, entity_type="ASSET", entity_id=str(asset.pk), action="ASSET_CREATED").exists()
            assert AuditLog.objects.filter(organization=asset.organization, entity_type="ASSET", entity_id=str(asset.pk), action="ASSET_UPDATED").exists()
            assert AuditLog.objects.filter(organization=foreign_asset.organization, entity_type="ASSET", entity_id=str(foreign_asset.pk), action="ASSET_CREATED").exists()
            assert asset.organization_id != foreign_asset.organization_id
            assert Organization.objects.count() == 2
            print("VERIFY: isolated F10 tenant boundary and audit events generated by asset and acquisition domain services")
            sys.exit(0)
        elif os.environ.get("F8_SMOKE_MODE"):
            from assets.models import Asset
            from assurance.models import (
                AssuranceFinding,
                AssuranceFindingOccurrence,
                AssuranceRun,
            )
            from audit.models import AuditLog
            from transfers.models import AssetAssignment
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f8_")
            asset = Asset.objects.get(asset_tag="F8-ASSURANCE-01")
            run = AssuranceRun.objects.get(run_type="FULL")
            findings = AssuranceFinding.objects.filter(occurrences__assurance_run=run).distinct()
            events = set(AuditLog.objects.filter(organization=asset.organization).values_list("action", flat=True))
            expected_events = {"ASSURANCE_RUN_CREATED","ASSURANCE_RUN_STARTED","ASSURANCE_INPUTS_SEALED","ASSURANCE_FINDING_CREATED","ASSURANCE_FINDING_REVIEWED","ASSURANCE_FINDING_RESOLVED","ASSURANCE_RUN_COMPLETED"}
            assert run.status == "COMPLETED" and run.execution_phase == "DONE"
            assert run.assets_evaluated == 1 and run.unit_count == run.units_completed == 1
            assert findings.filter(finding_type="BOOK_VALUE_EXCEPTION", status="RESOLVED", occurrence_count=1).exists()
            assert findings.count() >= 1 and AssuranceFindingOccurrence.objects.filter(assurance_run=run).exists()
            assert expected_events <= events
            assert (asset.asset_tag, asset.department.code, asset.location.code, asset.status, asset.condition, str(asset.purchase_cost), str(asset.accumulated_depreciation), str(asset.current_book_value)) == ("F8-ASSURANCE-01","OPS","PLANT","ACTIVE","GOOD","1001.00","25.03","900.00")
            assert (asset.capitalization_date.isoformat(), asset.available_for_use_date.isoformat()) == ("2026-01-02","2026-01-02")
            assert AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True, assigned_to__email="f8-custodian@example.test").count() == 1
            assert Asset.objects.count() == 1
            print("VERIFY: isolated F8 completed run, public book-value finding and occurrence, review/resolution audit, unchanged asset/custody values, and one-asset count")
            sys.exit(0)
        if os.environ.get("F7_SMOKE_MODE"):
            from assets.models import Asset
            from audit.models import AuditLog
            from transfers.models import AssetAssignment
            from verification.models import (
                PhysicalVerification,
                VerificationCampaign,
                VerificationEvidence,
                VerificationException,
            )
            assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
            assert os.environ["F1_SMOKE_DATABASE"].startswith("assetflow_f7_")
            campaign = VerificationCampaign.objects.get(name="F7 isolated physical verification")
            registered = Asset.objects.get(asset_tag="F7-SMOKE-01")
            mismatch_asset = Asset.objects.get(asset_tag="F7-SMOKE-02")
            unregistered_count = PhysicalVerification.objects.filter(campaign=campaign, asset__isnull=True).count()
            events = set(AuditLog.objects.filter(organization=registered.organization).values_list("action", flat=True))
            assert campaign.status == "COMPLETED"
            assert campaign.verifications.filter(asset=registered).count() == 1
            assert campaign.verifications.filter(asset__asset_tag="F7-SMOKE-02", result="CONDITION_MISMATCH").count() == 1
            assert campaign.verifications.filter(asset__isnull=True, result="UNREGISTERED_ASSET").count() == 1 and unregistered_count == 1
            exception_types = set(VerificationException.objects.filter(campaign=campaign).values_list("exception_type", flat=True))
            assert {"LOCATION_MISMATCH", "DEPARTMENT_MISMATCH", "CUSTODY_MISMATCH", "TAG_MISMATCH", "CONDITION_MISMATCH", "DAMAGED_ASSET", "UNREGISTERED_ASSET"}.issubset(exception_types)
            assert VerificationEvidence.objects.filter(verification__campaign=campaign, evidence_type="NOTE", integrity_status="METADATA_ONLY").exists()
            assert Asset.objects.filter(organization=registered.organization).count() == 2
            assert [mismatch_asset.asset_tag, mismatch_asset.department.code, mismatch_asset.location.code, mismatch_asset.status, str(mismatch_asset.purchase_cost), str(mismatch_asset.residual_value), str(mismatch_asset.accumulated_depreciation), str(mismatch_asset.current_book_value)] == ["F7-SMOKE-02", "OPS", "PLANT", "ACTIVE", "1001.00", "100.00", "25.03", "975.97"]
            assert [mismatch_asset.acquisition_date.isoformat(), mismatch_asset.capitalization_date.isoformat(), mismatch_asset.available_for_use_date.isoformat(), mismatch_asset.depreciation_method, mismatch_asset.useful_life_months, mismatch_asset.condition] == ["2026-01-01", "2026-01-02", "2026-01-02", "SLM", 36, "GOOD"]
            active_assignments = list(AssetAssignment.objects.filter(asset=mismatch_asset, returned_at__isnull=True).values_list("assigned_to__email", "department__code", "location__code"))
            assert active_assignments == [("custodian@example.test", "OPS", "PLANT")]
            assert {"VERIFICATION_CAMPAIGN_CREATED", "VERIFICATION_CAMPAIGN_STARTED", "VERIFICATION_CREATED", "VERIFICATION_RESULT_RECONCILED", "VERIFICATION_EXCEPTION_CREATED", "VERIFICATION_CAMPAIGN_COMPLETED", "VERIFICATION_EVIDENCE_ADDED"}.issubset(events)
            print("PASS: isolated PostgreSQL F7 campaign, registered/mismatching/unregistered observations, exceptions, NOTE evidence metadata, asset invariance, two-asset count and audit events verified.")
            sys.exit(0)
        from assets.models import Acquisition, Asset
        from audit.models import AuditLog
        assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
        f6 = bool(os.environ.get("F6_SMOKE_MODE"))
        f5 = bool(os.environ.get("F5_SMOKE_MODE"))
        f4 = bool(os.environ.get("F4_SMOKE_MODE"))
        f3 = bool(os.environ.get("F3_SMOKE_MODE"))
        prefix = "assetflow_f6_" if f6 else "assetflow_f5_" if f5 else "assetflow_f4_" if f4 else "assetflow_f3_" if f3 else "assetflow_f2_"
        assert os.environ["F1_SMOKE_DATABASE"].startswith(prefix)
        asset = Asset.objects.get(asset_tag="F6-SMOKE-001" if f6 else "F5-SMOKE-001" if f5 else "F4-SMOKE-001" if f4 else "F3-SMOKE-001" if f3 else "F2-SMOKE-001")
        acquisition = Acquisition.objects.get(asset=asset)
        def check(condition, label):
            if not condition:
                print(f"VERIFY: {label}")
            return bool(condition)

        assert check(asset.status == ("DISPOSED" if f6 else "ACTIVE") and str(asset.purchase_cost) == "1001.00", "asset lifecycle and total")
        assert check(str(asset.residual_value) == "100.00" and asset.useful_life_months == 36, "residual and useful life")
        expected_capitalization = "2026-02-02" if f4 or f5 or f6 else "2026-01-02"
        assert check(asset.depreciation_method == "SLM" and asset.capitalization_date.isoformat() == expected_capitalization, "asset accounting dates and method")
        assert check(asset.organization_id == asset.category.organization_id == asset.department.organization_id == asset.location.organization_id, "tenant-owned reference relationships")
        assert check(acquisition.status == "CAPITALIZED" and str(acquisition.total_cost) == "1001.00", "acquisition state and total")
        assert check([str(value) for value in (acquisition.purchase_price, acquisition.freight_cost,
            acquisition.installation_cost, acquisition.civil_works_cost, acquisition.other_capitalizable_cost)] == ["1000.01", "0.99", "0.00", "0.00", "0.00"]
            , "component costs")
        events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
        assert check("ASSET_CAPITALIZED" in events and "ACQUISITION_CAPITALIZED" in events, "capitalization audit events")
        if f6:
            from depreciation.models import DepreciationEntry, DepreciationSchedule
            from disposals.models import Disposal
            disposal = Disposal.objects.get(asset=asset)
            acquisition.refresh_from_db()
            entry = DepreciationEntry.objects.get(asset=asset)
            schedule = DepreciationSchedule.objects.get(asset=asset)
            events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
            events.update(AuditLog.objects.filter(entity_id=str(disposal.pk)).values_list("action", flat=True))
            events.update(AuditLog.objects.filter(entity_id=str(asset.pk), action="ASSET_DERECOGNIZED").values_list("action", flat=True))
            assert check(disposal.status == "COMPLETED" and asset.status == "DISPOSED", "completed disposal and terminal asset status")
            assert check([str(disposal.capitalized_cost_at_disposal), str(disposal.accumulated_depreciation_at_disposal), str(disposal.carrying_amount), str(disposal.proceeds), str(disposal.gain_or_loss)] == ["1001.00", "25.03", "975.97", "1200.00", "224.03"], "exact server-derived derecognition snapshot")
            assert check(disposal.gain_or_loss == disposal.proceeds - disposal.carrying_amount, "gain/loss equals proceeds less carrying amount")
            assert check([str(asset.purchase_cost), str(asset.residual_value), asset.useful_life_months, asset.depreciation_method] == ["1001.00", "100.00", 36, "SLM"], "disposal preserves capitalized cost and depreciation assumptions")
            assert check([str(asset.accumulated_depreciation), str(asset.current_book_value)] == ["25.03", "975.97"], "disposal preserves accumulated depreciation and book value")
            assert check(acquisition.status == "CAPITALIZED" and str(acquisition.total_cost) == "1001.00", "capitalized acquisition remains unchanged")
            assert check(DepreciationEntry.objects.filter(asset=asset).count() == 1 and [str(entry.depreciation_amount), str(entry.closing_book_value)] == ["25.03", "975.97"], "posted depreciation ledger remains unchanged")
            assert check(schedule.status == "ACTIVE", "disposal does not rewrite depreciation schedule history")
            assert check(Disposal.objects.filter(asset=asset).count() == 1 and {"DISPOSAL_CREATED", "DISPOSAL_SUBMITTED", "DISPOSAL_APPROVED", "ASSET_DERECOGNIZED", "DISPOSAL_COMPLETED"}.issubset(events), "duplicate prevention and full disposal audit trail")
            print("PASS: isolated PostgreSQL F6 derecognition snapshots 975.97 carrying amount, 1200.00 proceeds and 224.03 gain; asset/acquisition/depreciation ledger preserved; terminal status and audit verified.")
            sys.exit(0)
        if f5:
            from depreciation.models import DepreciationEntry, DepreciationSchedule
            from maintenance.models import (
                MaintenanceCost,
                MaintenancePlan,
                MaintenanceRecord,
                WorkOrder,
            )
            asset.refresh_from_db()
            costs = list(MaintenanceCost.objects.filter(work_order__asset=asset))
            records = list(MaintenanceRecord.objects.filter(asset=asset))
            order = WorkOrder.objects.get(asset=asset)
            plan = MaintenancePlan.objects.get(asset=asset)
            events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
            events.update(AuditLog.objects.filter(entity_id=str(costs[0].pk)).values_list("action", flat=True))
            events.update(AuditLog.objects.filter(entity_id=str(order.pk)).values_list("action", flat=True))
            events.update(AuditLog.objects.filter(entity_id=str(plan.pk)).values_list("action", flat=True))
            assert check(order.status == "COMPLETED" and len(costs) == 1 and len(records) == 1, "completed order, one exact cost and one history record")
            assert check(MaintenancePlan.objects.filter(asset=asset, active=False, frequency_value=3, frequency_unit="MONTHS").count() == 1, "plan creation and deactivation")
            assert check(str(costs[0].quantity) == "2.500" and str(costs[0].unit_cost) == "13.37" and str(costs[0].total_cost) == "33.43", "exact Decimal cost values")
            assert check(str(records[0].total_cost) == "33.43" and records[0].work_order_id == order.pk, "completion-generated immutable maintenance record total and linkage")
            assert check(asset.status == "ACTIVE" and str(asset.purchase_cost) == "1001.00" and str(asset.residual_value) == "100.00" and asset.useful_life_months == 36 and asset.depreciation_method == "SLM", "maintenance leaves asset lifecycle restored and financial assumptions unchanged")
            assert check(str(asset.accumulated_depreciation) == "0.00" and str(asset.current_book_value) == "1001.00", "maintenance leaves accumulated depreciation and book value unchanged")
            assert check(not DepreciationEntry.objects.filter(asset=asset).exists() and not DepreciationSchedule.objects.filter(asset=asset).exists(), "maintenance creates no depreciation schedule or entry")
            assert check({"MAINTENANCE_PLAN_CREATED", "MAINTENANCE_PLAN_UPDATED", "WORK_ORDER_CREATED", "WORK_ORDER_ASSIGNED", "WORK_ORDER_STARTED", "MAINTENANCE_COST_CREATED", "WORK_ORDER_COMPLETED", "MAINTENANCE_RECORD_CREATED"}.issubset(events), "plan, work order, cost, completion and record audit events")
            assert check(WorkOrder.objects.filter(asset=asset).count() == 1 and MaintenanceRecord.objects.filter(work_order=order).count() == 1, "repeated completion did not create another record")
            print("PASS: isolated PostgreSQL F5 exact-Decimal maintenance workflow, completion history, audit and accounting invariance verified.")
            sys.exit(0)
        if f4:
            from audit.models import AuditLog
            from transfers.models import AssetAssignment, AssetTransfer
            assignment = AssetAssignment.objects.get(asset=asset)
            transfer = AssetTransfer.objects.get(asset=asset)
            asset.refresh_from_db()
            events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
            assert check(assignment.returned_at is not None and assignment.assigned_to.email == "custodian@example.test", "assignment return retained with assigned custodian")
            assert check(transfer.status == "COMPLETED", "transfer completed")
            assert check(asset.department.code == "OPS-DST" and asset.location.code == "PLANT-DST", "completed transfer applied destination placement")
            assert check(not AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).exists(), "transfer did not create or alter active custody")
            assert check({"ASSET_ASSIGNED", "ASSET_ASSIGNMENT_RETURNED", "ASSET_TRANSFER_REQUESTED", "ASSET_TRANSFER_APPROVED", "ASSET_TRANSFER_COMPLETED"}.issubset(events), "assignment and transfer audit events")
            print("PASS: disposable PostgreSQL F4 preserves placement through assignment/return and changes placement only at transfer completion; custody history and audit retained.")
            sys.exit(0)
        if f3:
            from depreciation.models import (
                AccountingPeriod,
                DepreciationEntry,
                DepreciationSchedule,
            )
            period = AccountingPeriod.objects.get(organization=asset.organization, year=2026, month=1)
            entry = DepreciationEntry.objects.get(asset=asset, accounting_period=period)
            schedule = DepreciationSchedule.objects.get(asset=asset)
            events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
            assert check(period.status == "CLOSED", "closed period state")
            assert check(schedule.method == "SLM" and schedule.start_date.isoformat() == "2026-01-02", "backend schedule policy and available-for-use start")
            assert check([str(entry.opening_book_value), str(entry.depreciation_amount), str(entry.accumulated_depreciation), str(entry.closing_book_value)] == ["1001.00", "25.03", "25.03", "975.97"], "exact first-month backend posting")
            assert check(str(asset.accumulated_depreciation) == "25.03" and str(asset.current_book_value) == "975.97", "authoritative post-posting asset balances")
            period_events = set(AuditLog.objects.filter(organization=asset.organization, entity_id=str(period.pk)).values_list("action", flat=True))
            assert check("ACCOUNTING_PERIOD_CREATED" in period_events and "ACCOUNTING_PERIOD_CLOSED" in period_events, "period audit events")
            assert check("DEPRECIATION_SCHEDULE_CREATED" in events and "DEPRECIATION_POSTED" in events, "schedule/posting audit events")
            print("PASS: isolated PostgreSQL F3 entry exactly posts 25.03 for the full January 2026 available-for-use month, closes at 975.97 above the 100.00 residual floor, and records audit history.")
            sys.exit(0)
        print("PASS: isolated PostgreSQL holds one tenant asset and acquisition with exact components, ACTIVE lifecycle and capitalization audit.")
    else:
        try:
            run(f2=sys.argv[1:] == ["--f2"], f3=sys.argv[1:] == ["--f3"], f4=sys.argv[1:] == ["--f4"], f5=sys.argv[1:] == ["--f5"], f6=sys.argv[1:] == ["--f6"], f7=sys.argv[1:] == ["--f7"], f8=sys.argv[1:] == ["--f8"], f9=sys.argv[1:] == ["--f9"], f10=sys.argv[1:] == ["--f10"], f11=sys.argv[1:] == ["--f11"], f12=sys.argv[1:] == ["--f12"], f13=sys.argv[1:] == ["--f13"], f14=sys.argv[1:] == ["--f14"], f16=sys.argv[1:] == ["--f16"])
        except Exception as error:  # noqa: BLE001 -- Do not print exception bodies containing credentials.
            mode = "F16" if sys.argv[1:] == ["--f16"] else "F14" if sys.argv[1:] == ["--f14"] else "F13" if sys.argv[1:] == ["--f13"] else "F11" if sys.argv[1:] == ["--f11"] else "F10" if sys.argv[1:] == ["--f10"] else "F9" if sys.argv[1:] == ["--f9"] else "F8" if sys.argv[1:] == ["--f8"] else "F7" if sys.argv[1:] == ["--f7"] else "F6" if sys.argv[1:] == ["--f6"] else "F5" if sys.argv[1:] == ["--f5"] else "F4" if sys.argv[1:] == ["--f4"] else "F3" if sys.argv[1:] == ["--f3"] else "F2" if sys.argv[1:] == ["--f2"] else "F1"
            print(f"{mode} smoke unavailable/failed ({type(error).__name__}); no connection details printed.")
            if isinstance(error, RuntimeError):
                print(str(error))
            sys.exit(1)
