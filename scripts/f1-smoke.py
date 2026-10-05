"""Bounded F1 smoke against a disposable PostgreSQL database, never the app database.

Uses existing configured PostgreSQL credentials to create/drop a unique database.
No credentials, tokens, or database dumps are printed or written to files.
"""

import os
import secrets
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
    prefix = "assetflow_f7_" if os.environ.get("F7_SMOKE_MODE") else "assetflow_f6_" if os.environ.get("F6_SMOKE_MODE") else "assetflow_f5_" if os.environ.get("F5_SMOKE_MODE") else "assetflow_f4_" if os.environ.get("F4_SMOKE_MODE") else "assetflow_f3_" if os.environ.get("F3_SMOKE_MODE") else "assetflow_f2_" if os.environ.get("F2_SMOKE_MODE") else "assetflow_f1_"
    assert settings.DATABASES["default"]["NAME"] == os.environ["F1_SMOKE_DATABASE"]
    assert os.environ["F1_SMOKE_DATABASE"].startswith(prefix)
    organization = Organization.objects.create(name=f"{prefix[:-1].upper()} smoke", code=f"{prefix[:-1].upper()}SMOKE")
    manager = User.objects.create_user(
        os.environ["F1_SMOKE_EMAIL"], os.environ["F1_SMOKE_PASSWORD"],
        organization=organization, role="ASSET_MANAGER",
    )
    category = AssetCategory.objects.create(
        organization=organization, name="Equipment", code="EQ", default_useful_life_months=36,
    )
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
    if prefix.endswith("f7_"):
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
        return
    for number in (1, 2):
        Asset.objects.create(
            organization=organization, category=category, asset_tag=f"F1-SMOKE-{number:02}",
            name=f"Smoke asset {number}", purchase_cost="999999999999999999.99",
        )


def run(f2=False, f3=False, f4=False, f5=False, f6=False, f7=False):
    database = settings.DATABASES["default"]
    f7 = f7 or bool(os.environ.get("F7_SMOKE_MODE"))
    f6 = f6 or bool(os.environ.get("F6_SMOKE_MODE"))
    f5 = f5 or bool(os.environ.get("F5_SMOKE_MODE"))
    prefix = "assetflow_f7_" if f7 else "assetflow_f6_" if f6 else "assetflow_f5_" if f5 else "assetflow_f4_" if f4 else "assetflow_f3_" if f3 else "assetflow_f2_" if f2 else "assetflow_f1_"
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
        "F1_SMOKE_DATABASE": name, "F2_SMOKE_MODE": "1" if f2 else "", "F3_SMOKE_MODE": "1" if f3 else "", "F4_SMOKE_MODE": "1" if f4 else "", "F5_SMOKE_MODE": "1" if f5 else "", "F6_SMOKE_MODE": "1" if f6 else "", "F7_SMOKE_MODE": "1" if f7 else "", "F1_SMOKE_APPROVER_EMAIL": "approver@example.test",
        "F1_SMOKE_EMAIL": "smoke@example.test",
        "F1_SMOKE_PASSWORD": secrets.token_urlsafe(32),
        "F1_SMOKE_URL": f"http://127.0.0.1:{port}/api/v1",
        "DEBUG": "false", "SECURE_SSL_REDIRECT": "false", "ALLOWED_HOSTS": "127.0.0.1,localhost",
    })
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
        if f7 and os.name == "nt":
            # tsx asks Node for account details when choosing its cache directory; some
            # managed Windows runners deny that OS lookup. Keep the compatibility shim
            # temporary and outside the repository.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".cjs", encoding="utf-8", delete=False) as shim:
                shim.write("const os=require('node:os');os.userInfo=()=>({uid:-1,gid:-1,username:'assetflow-smoke',homedir:os.homedir(),shell:null});\n")
                shim_path = shim.name
            node_command.extend(["--require", shim_path])
        node_command.extend(["--import", "tsx", "scripts/f7-api-smoke.ts" if f7 else "scripts/f6-api-smoke.ts" if f6 else "scripts/f5-api-smoke.ts" if f5 else "scripts/f4-api-smoke.ts" if f4 else "scripts/f3-api-smoke.ts" if f3 else "scripts/f2-api-smoke.ts" if f2 else "scripts/f1-api-smoke.ts"])
        result = subprocess.run(
            node_command, cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=60, creationflags=flags, check=False,
        )
        if result.returncode:
            for line in result.stdout.splitlines():
                if line.startswith("SMOKE:"):
                    print(line)
            raise RuntimeError("Frontend API smoke failed; captured output withheld to protect temporary credentials.")
        print(result.stdout.strip())
        if f2 or f3 or f4 or f5 or f6 or f7:
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
            run(f2=sys.argv[1:] == ["--f2"], f3=sys.argv[1:] == ["--f3"], f4=sys.argv[1:] == ["--f4"], f5=sys.argv[1:] == ["--f5"], f6=sys.argv[1:] == ["--f6"], f7=sys.argv[1:] == ["--f7"])
        except Exception as error:  # noqa: BLE001 -- Do not print exception bodies containing credentials.
            mode = "F7" if sys.argv[1:] == ["--f7"] else "F6" if sys.argv[1:] == ["--f6"] else "F5" if sys.argv[1:] == ["--f5"] else "F4" if sys.argv[1:] == ["--f4"] else "F3" if sys.argv[1:] == ["--f3"] else "F2" if sys.argv[1:] == ["--f2"] else "F1"
            print(f"{mode} smoke unavailable/failed ({type(error).__name__}); no connection details printed.")
            if isinstance(error, RuntimeError):
                print(str(error))
            sys.exit(1)
