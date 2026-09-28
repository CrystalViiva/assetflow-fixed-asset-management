"""Durable daily assurance schedule orchestration."""

import logging

from django.utils import timezone

from assurance.constants import DAILY_FULL_SCHEDULE_ID
from assurance.selectors import organizations_for_scheduled_assurance
from assurance.services.runs import create_scheduled_run, dispatch_run
from organizations.models import Organization

logger = logging.getLogger(__name__)


def schedule_daily_full_assurance(*, window=None):
    """Create and dispatch one FULL assurance run per active organization and date."""
    window = window or timezone.localdate()
    organization_ids = list(organizations_for_scheduled_assurance().values_list("pk", flat=True))
    result = {
        "schedule_id": DAILY_FULL_SCHEDULE_ID,
        "window": window.isoformat(),
        "organizations_considered": len(organization_ids),
        "runs_created": 0,
        "runs_skipped_existing": 0,
        "organizations_skipped_inactive": [],
        "organizations_failed": [],
        "created_run_ids": [],
        "existing_run_ids": [],
    }

    for organization_id in organization_ids:
        organization_id = str(organization_id)
        try:
            organization = Organization.objects.filter(pk=organization_id, is_active=True).first()
            if organization is None:
                result["organizations_skipped_inactive"].append(organization_id)
                continue

            run, created = create_scheduled_run(organization=organization, scheduled_for=window)
            if created:
                result["runs_created"] += 1
                result["created_run_ids"].append(str(run.pk))
            else:
                result["runs_skipped_existing"] += 1
                result["existing_run_ids"].append(str(run.pk))

            dispatch_run(run_id=run.pk, actor=None, organization=organization)
        except Exception as exc:
            logger.exception(
                "Scheduled assurance failed for organization %s in window %s",
                organization_id,
                window.isoformat(),
                extra={
                    "organization_id": organization_id,
                    "schedule_window": window.isoformat(),
                    "schedule_id": DAILY_FULL_SCHEDULE_ID,
                },
            )
            result["organizations_failed"].append(
                {"organization_id": organization_id, "error_type": type(exc).__name__}
            )

    return result
