"""Internal execution history. Tenant ownership is inherited exclusively from run."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from assurance.models import AssuranceHistoryQuerySet, AssuranceRun


class ExecutionQuerySet(AssuranceHistoryQuerySet):
    def bulk_create(self, objs, **kwargs):
        if kwargs.get("ignore_conflicts") or kwargs.get("update_conflicts"):
            raise ValidationError("Execution conflicts must not be ignored or overwrite history.")
        objs = list(objs)
        for run in AssuranceRun.objects.filter(pk__in={obj.run_id for obj in objs}):
            if self.model.__name__ == "AssuranceRunCandidate":
                valid = (
                    run.status == "RUNNING" and run.sealed_at and run.execution_phase == "EVALUATE"
                )
            else:
                valid = (
                    run.status == "RUNNING"
                    and not run.sealed_at
                    and run.execution_phase == "CAPTURE"
                )
            if not valid:
                raise ValidationError("Execution records cannot be appended in this phase.")
        return super().bulk_create(objs, **kwargs)


class ImmutableExecutionRecord(models.Model):
    objects = ExecutionQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Execution inputs and candidates are immutable.")
        # Use the same phase guard as bulk inserts; creation is service-owned.
        run = AssuranceRun.objects.get(pk=self.run_id)
        if self.__class__.__name__ == "AssuranceRunCandidate":
            valid = run.status == "RUNNING" and run.sealed_at and run.execution_phase == "EVALUATE"
        else:
            valid = (
                run.status == "RUNNING" and not run.sealed_at and run.execution_phase == "CAPTURE"
            )
        if not valid:
            raise ValidationError("Execution records cannot be appended in this phase.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Execution history cannot be deleted.")


class AssuranceRunInput(ImmutableExecutionRecord):
    run = models.ForeignKey(AssuranceRun, on_delete=models.PROTECT, related_name="inputs")
    kind = models.CharField(max_length=12)  # ASSET or OBSERVATION
    source_id = models.UUIDField()
    asset_id = models.UUIDField(null=True)
    campaign_id = models.UUIDField(null=True)
    normalized_tag = models.TextField(blank=True)
    subject_ordinal = models.PositiveIntegerField(null=True)
    payload = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("run", "kind", "source_id"), name="assin_source_uniq"),
            models.UniqueConstraint(fields=("run", "subject_ordinal"), name="assin_subject_uniq"),
            models.CheckConstraint(
                condition=Q(kind__in=("ASSET", "OBSERVATION")), name="assin_kind_valid"
            ),
        ]
        indexes = [
            models.Index(fields=("run", "campaign_id", "normalized_tag"), name="assin_tag_idx"),
            models.Index(fields=("run", "asset_id", "kind"), name="assin_asset_idx"),
        ]


class AssuranceWorkUnit(models.Model):
    run = models.ForeignKey(AssuranceRun, on_delete=models.PROTECT, related_name="work_units")
    ordinal = models.PositiveIntegerField()
    first_subject = models.PositiveIntegerField()
    last_subject = models.PositiveIntegerField()
    completed_at = models.DateTimeField(null=True)
    candidate_count = models.PositiveIntegerField(default=0)
    objects = ExecutionQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("run", "ordinal"), name="assunit_ordinal_uniq"),
            models.CheckConstraint(
                condition=Q(first_subject__gte=1) & Q(last_subject__gte=models.F("first_subject")),
                name="assunit_range_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("run", "completed_at", "ordinal"), name="assunit_pending_idx")
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.completed_at or any(
                getattr(previous, name) != getattr(self, name)
                for name in ("run_id", "ordinal", "first_subject", "last_subject")
            ):
                raise ValidationError("Work unit identity and completed history are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Execution history cannot be deleted.")


class AssuranceRunCandidate(ImmutableExecutionRecord):
    run = models.ForeignKey(AssuranceRun, on_delete=models.PROTECT, related_name="candidates")
    subject_ordinal = models.PositiveIntegerField()
    identity_key = models.CharField(max_length=80)
    finding_type = models.CharField(max_length=40)
    payload = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("run", "identity_key", "finding_type"), name="asscandidate_identity_uniq"
            )
        ]
