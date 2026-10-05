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
    from organizations.models import Department, Location, Organization

    # This child must only ever connect to the random database selected by the parent.
    prefix = "assetflow_f5_" if os.environ.get("F5_SMOKE_MODE") else "assetflow_f4_" if os.environ.get("F4_SMOKE_MODE") else "assetflow_f3_" if os.environ.get("F3_SMOKE_MODE") else "assetflow_f2_" if os.environ.get("F2_SMOKE_MODE") else "assetflow_f1_"
    assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
    assert os.environ["F1_SMOKE_DATABASE"].startswith(prefix)
    organization = Organization.objects.create(name=f"{prefix[:-1].upper()} smoke", code=f"{prefix[:-1].upper()}SMOKE")
    User.objects.create_user(
        os.environ["F1_SMOKE_EMAIL"], os.environ["F1_SMOKE_PASSWORD"],
        organization=organization, role="ASSET_MANAGER",
    )
    category = AssetCategory.objects.create(
        organization=organization, name="Equipment", code="EQ", default_useful_life_months=36,
    )
    if prefix.endswith(("f2_", "f3_", "f4_", "f5_")):
        Department.objects.create(organization=organization, name="Operations", code="OPS")
        Location.objects.create(organization=organization, name="Main Plant", code="PLANT")
        if prefix.endswith("f4_"):
            Department.objects.create(organization=organization, name="Destination Operations", code="OPS-DST")
            Location.objects.create(organization=organization, name="Destination Plant", code="PLANT-DST")
            User.objects.create_user("custodian@example.test", os.environ["F1_SMOKE_PASSWORD"], organization=organization, role="EMPLOYEE")
        return
    for number in (1, 2):
        Asset.objects.create(
            organization=organization, category=category, asset_tag=f"F1-SMOKE-{number:02}",
            name=f"Smoke asset {number}", purchase_cost="999999999999999999.99",
        )


def run(f2=False, f3=False, f4=False, f5=False):
    database = settings.DATABASES["default"]
    f5 = f5 or bool(os.environ.get("F5_SMOKE_MODE"))
    prefix = "assetflow_f5_" if f5 else "assetflow_f4_" if f4 else "assetflow_f3_" if f3 else "assetflow_f2_" if f2 else "assetflow_f1_"
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
        "F1_SMOKE_DATABASE": name, "F2_SMOKE_MODE": "1" if f2 else "", "F3_SMOKE_MODE": "1" if f3 else "", "F4_SMOKE_MODE": "1" if f4 else "", "F5_SMOKE_MODE": "1" if f5 else "",
        "F1_SMOKE_EMAIL": "smoke@example.test",
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
        result = subprocess.run(
            ["node", "--import", "tsx", "scripts/f5-api-smoke.ts" if f5 else "scripts/f4-api-smoke.ts" if f4 else "scripts/f3-api-smoke.ts" if f3 else "scripts/f2-api-smoke.ts" if f2 else "scripts/f1-api-smoke.ts"], cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=60, creationflags=flags, check=False,
        )
        if result.returncode:
            for line in result.stdout.splitlines():
                if line.startswith("SMOKE:"):
                    print(line)
            raise RuntimeError("Frontend API smoke failed; captured output withheld to protect temporary credentials.")
        print(result.stdout.strip())
        if f2 or f3 or f4 or f5:
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
                raise RuntimeError("F2/F3 PostgreSQL state and audit verification failed; details withheld.")
            print(result.stdout.strip())
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
        if created:
            # Drop only the exact randomly generated database this process created.
            assert name.startswith(prefix) and len(name) == 45
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print("Disposable PostgreSQL database removed; application database untouched.")
        admin.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--seed"]:
        seed()
    elif sys.argv[1:] == ["--verify"]:
        import django
        django.setup()
        from assets.models import Acquisition, Asset
        from audit.models import AuditLog
        assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
        f5 = bool(os.environ.get("F5_SMOKE_MODE"))
        f4 = bool(os.environ.get("F4_SMOKE_MODE"))
        f3 = bool(os.environ.get("F3_SMOKE_MODE"))
        prefix = "assetflow_f5_" if f5 else "assetflow_f4_" if f4 else "assetflow_f3_" if f3 else "assetflow_f2_"
        assert os.environ["F1_SMOKE_DATABASE"].startswith(prefix)
        asset = Asset.objects.get(asset_tag="F5-SMOKE-001" if f5 else "F4-SMOKE-001" if f4 else "F3-SMOKE-001" if f3 else "F2-SMOKE-001")
        acquisition = Acquisition.objects.get(asset=asset)
        def check(condition, label):
            if not condition:
                print(f"VERIFY: {label}")
            return bool(condition)

        assert check(asset.status == "ACTIVE" and str(asset.purchase_cost) == "1001.00", "asset lifecycle and total")
        assert check(str(asset.residual_value) == "100.00" and asset.useful_life_months == 36, "residual and useful life")
        expected_capitalization = "2026-02-02" if f4 or f5 else "2026-01-02"
        assert check(asset.depreciation_method == "SLM" and asset.capitalization_date.isoformat() == expected_capitalization, "asset accounting dates and method")
        assert check(asset.organization_id == asset.category.organization_id == asset.department.organization_id == asset.location.organization_id, "tenant-owned reference relationships")
        assert check(acquisition.status == "CAPITALIZED" and str(acquisition.total_cost) == "1001.00", "acquisition state and total")
        assert check([str(value) for value in (acquisition.purchase_price, acquisition.freight_cost,
            acquisition.installation_cost, acquisition.civil_works_cost, acquisition.other_capitalizable_cost)] == ["1000.01", "0.99", "0.00", "0.00", "0.00"]
            , "component costs")
        events = set(AuditLog.objects.filter(metadata__asset_id=str(asset.pk)).values_list("action", flat=True))
        assert check("ASSET_CAPITALIZED" in events and "ACQUISITION_CAPITALIZED" in events, "capitalization audit events")
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
            run(f2=sys.argv[1:] == ["--f2"], f3=sys.argv[1:] == ["--f3"], f4=sys.argv[1:] == ["--f4"], f5=sys.argv[1:] == ["--f5"])
        except Exception as error:  # noqa: BLE001 -- Do not print exception bodies containing credentials.
            mode = "F5" if sys.argv[1:] == ["--f5"] else "F4" if sys.argv[1:] == ["--f4"] else "F3" if sys.argv[1:] == ["--f3"] else "F2" if sys.argv[1:] == ["--f2"] else "F1"
            print(f"{mode} smoke unavailable/failed ({type(error).__name__}); no connection details printed.")
            if isinstance(error, RuntimeError):
                print(str(error))
            sys.exit(1)
