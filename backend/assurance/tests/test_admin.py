import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from accounts.models import User
from assurance.admin import (
    AssuranceFindingAdmin,
    AssuranceFindingOccurrenceInline,
    AssuranceRunAdmin,
)
from assurance.models import AssuranceFinding, AssuranceFindingOccurrence, AssuranceRun
from assurance.services import create_run, execute_run


@pytest.mark.django_db(transaction=True)
def test_tenant_assurance_admins_scope_runs_findings(manager, foreign_manager, asset_factory):
    manager.is_staff = True
    manager.save(update_fields=("is_staff",))
    foreign_manager.is_staff = True
    foreign_manager.save(update_fields=("is_staff",))
    asset_factory(current_book_value="900.00")
    local_run = create_run(actor=manager, run_type="FULL")
    execute_run(run_id=local_run.pk, actor=manager)
    foreign_run = create_run(actor=foreign_manager, run_type="FULL")
    execute_run(run_id=foreign_run.pk, actor=foreign_manager)
    request = RequestFactory().get("/admin/")
    request.user = manager

    run_admin = AssuranceRunAdmin(AssuranceRun, AdminSite())
    finding_admin = AssuranceFindingAdmin(AssuranceFinding, AdminSite())
    assert list(run_admin.get_queryset(request).values_list("pk", flat=True)) == [local_run.pk]
    assert set(finding_admin.get_queryset(request).values_list("organization_id", flat=True)) == {
        manager.organization_id
    }
    assert "organization" not in run_admin.get_list_filter(request)
    assert "organization" not in finding_admin.get_list_filter(request)

    local_finding = finding_admin.get_queryset(request).first()
    AssuranceFindingOccurrence.objects.create(
        organization=foreign_manager.organization,
        finding=local_finding,
        assurance_run=foreign_run,
        description="Malformed cross-organization relation for admin isolation test",
    )
    inline = AssuranceFindingOccurrenceInline(AssuranceFinding, AdminSite())
    inline_queryset = inline.get_queryset(request)
    assert not inline_queryset.filter(organization_id=foreign_manager.organization_id).exists()


@pytest.mark.django_db(transaction=True)
def test_superuser_assurance_admins_remain_global(manager, foreign_manager, asset_factory):
    asset_factory(current_book_value="900.00")
    local_run = create_run(actor=manager, run_type="FULL")
    execute_run(run_id=local_run.pk, actor=manager)
    foreign_run = create_run(actor=foreign_manager, run_type="FULL")
    execute_run(run_id=foreign_run.pk, actor=foreign_manager)
    superuser = User.objects.create_superuser("global-root@example.test", "test-password")
    request = RequestFactory().get("/admin/")
    request.user = superuser

    assert AssuranceRunAdmin(AssuranceRun, AdminSite()).get_queryset(request).count() == 2
    assert AssuranceFindingAdmin(AssuranceFinding, AdminSite()).get_queryset(request).exists()
