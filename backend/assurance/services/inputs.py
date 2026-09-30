"""Explicit versioned input capture; never serialize unrestricted model instances."""

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from itertools import islice
from types import SimpleNamespace
from uuid import UUID

from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.utils import timezone

from assurance.models import AssuranceRunInput, AssuranceWorkUnit
from assurance.rules import RULES_BY_RUN_TYPE
from assurance.rules.common import FindingCandidate
from assurance.rules.context import EvaluationContext
from depreciation.models import DepreciationEntry, DepreciationSchedule
from disposals.models import Disposal
from maintenance.models import WorkOrder
from transfers.models import AssetAssignment, AssetTransfer
from verification.models import PhysicalVerification, VerificationEvidence, VerificationException
from verification.selectors import expected_assets

EXECUTOR_VERSION = 1
INPUT_VERSION = 1
MAX_PAYLOAD_BYTES = 65_536


class InputTooLarge(ValueError):
    """An explicit subject/candidate limit was exceeded; no results may be published."""


ASSET_FIELDS = (
    "asset_tag",
    "status",
    "condition",
    "capitalization_date",
    "useful_life_months",
    "purchase_cost",
    "residual_value",
    "accumulated_depreciation",
    "current_book_value",
    "depreciation_method",
    "updated_at",
    "department_id",
    "location_id",
)
SCHEDULE_FIELDS = (
    "capitalized_cost",
    "residual_value",
    "useful_life_months",
    "method",
    "status",
    "depreciable_base",
)
DISPOSAL_FIELDS = (
    "status",
    "completed_at",
    "capitalized_cost_at_disposal",
    "accumulated_depreciation_at_disposal",
)
OBSERVATION_FIELDS = (
    "observed_asset_tag",
    "observed_description",
    "observed_condition",
    "observed_location_id",
    "observed_department_id",
    "observed_custodian_id",
)


def scalar(value):
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def fields(obj, names):
    return {name: scalar(getattr(obj, name)) for name in names}


def label(obj):
    return {"pk": scalar(obj.pk), "label": str(obj)} if obj is not None else None


def bounded(payload):
    if len(json.dumps(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise InputTooLarge("Assurance subject payload exceeds 64 KiB.")
    return payload


def batches(iterator, size):
    iterator = iter(iterator)
    while rows := list(islice(iterator, size)):
        yield rows


def observation_queryset(run):
    rows = PhysicalVerification.objects.filter(
        organization_id=run.organization_id,
        verified_at__lte=run.started_at,
    )
    if run.verification_campaign_id:
        rows = rows.filter(campaign_id=run.verification_campaign_id).order_by("pk")
    else:
        # Exactly the latest observation for each registered organization asset.
        rows = (
            rows.filter(asset__organization_id=run.organization_id)
            .order_by("asset_id", "-verified_at", "-created_at", "-pk")
            .distinct("asset_id")
        )
    exceptions = VerificationException.objects.filter(
        organization_id=run.organization_id, verification_id=OuterRef("pk")
    )
    return (
        rows.select_related("observed_department", "observed_location", "observed_custodian")
        .only(
            "pk",
            "asset_id",
            "campaign_id",
            "verified_at",
            "created_at",
            *OBSERVATION_FIELDS,
            "observed_department__code",
            "observed_department__name",
            "observed_location__code",
            "observed_location__name",
            "observed_custodian__email",
        )
        .annotate(
            severe=Exists(exceptions.filter(severity__in=("HIGH", "CRITICAL"))),
            not_found=Exists(exceptions.filter(exception_type="ASSET_NOT_FOUND")),
            has_evidence=Exists(
                VerificationEvidence.objects.filter(
                    organization_id=run.organization_id, verification_id=OuterRef("pk")
                )
            ),
        )
    )


def capture_observations(run, size):
    count = 0
    if run.run_type == "FINANCIAL":
        return count
    for rows in batches(observation_queryset(run).iterator(chunk_size=size), size):
        pending = []
        for row in rows:
            ordinal = None
            if row.asset_id is None:
                count += 1
                ordinal = count
            payload = fields(row, OBSERVATION_FIELDS)
            payload.update(
                version=INPUT_VERSION,
                observed_location=label(row.observed_location),
                observed_department=label(row.observed_department),
                observed_custodian=label(row.observed_custodian),
                severe=row.severe,
                not_found=row.not_found,
                has_evidence=row.has_evidence,
            )
            pending.append(
                AssuranceRunInput(
                    run=run,
                    kind="OBSERVATION",
                    source_id=row.pk,
                    asset_id=row.asset_id,
                    campaign_id=row.campaign_id,
                    normalized_tag=row.observed_asset_tag.strip().casefold(),
                    subject_ordinal=ordinal,
                    payload=bounded(payload),
                )
            )
        AssuranceRunInput.objects.bulk_create(pending, batch_size=size)
    return count


def financial_context(run, asset_ids):
    schedules = {
        row.asset_id: row
        for row in DepreciationSchedule.objects.filter(
            organization_id=run.organization_id, asset_id__in=asset_ids
        ).annotate(entry_count=Count("entries"))
    }
    entries = {
        row["asset_id"]: row
        for row in DepreciationEntry.objects.filter(
            organization_id=run.organization_id, asset_id__in=asset_ids
        )
        .order_by()
        .values("asset_id")
        .annotate(total=Sum("depreciation_amount"), last=Max("posted_at"))
    }
    return schedules, entries


def asset_payloads(run, assets):
    ids = [asset.pk for asset in assets]
    financial = run.run_type in ("FULL", "FINANCIAL")
    operational = run.run_type in ("FULL", "OPERATIONAL")
    physical = run.run_type != "FINANCIAL"
    assignments = {}
    orders = defaultdict(dict)
    transfers = defaultdict(list)
    disposals = defaultdict(list)
    schedules, entries = ({}, {})
    expected = set()
    if physical:
        assignments = {
            row.asset_id: label(row.assigned_to)
            for row in AssetAssignment.objects.filter(
                organization_id=run.organization_id, asset_id__in=ids, returned_at__isnull=True
            ).select_related("assigned_to")
        }
        if run.verification_campaign_id:
            from assurance.services.runs import scope_campaign

            expected = set(
                expected_assets(scope_campaign(run)).filter(pk__in=ids).values_list("pk", flat=True)
            )
    if operational:
        for row in (
            WorkOrder.objects.filter(
                organization_id=run.organization_id,
                asset_id__in=ids,
                status__in=("OPEN", "ASSIGNED", "IN_PROGRESS"),
            )
            .order_by()
            .values("asset_id", "status")
            .annotate(n=Count("pk"))
        ):
            orders[row["asset_id"]][row["status"]] = row["n"]
        for row in AssetTransfer.objects.filter(
            organization_id=run.organization_id,
            asset_id__in=ids,
            status__in=("REQUESTED", "APPROVED"),
        ):
            transfers[row.asset_id].append(row.status)
    if operational or financial:
        for row in Disposal.objects.filter(
            organization_id=run.organization_id,
            asset_id__in=ids,
            status__in=("DRAFT", "PENDING_APPROVAL", "APPROVED", "COMPLETED"),
        ):
            disposals[row.asset_id].append(fields(row, DISPOSAL_FIELDS))
    if financial:
        schedules, entries = financial_context(run, ids)
    for asset in assets:
        schedule = schedules.get(asset.pk)
        entry = entries.get(asset.pk, {})
        yield bounded(
            {
                "version": INPUT_VERSION,
                "asset": fields(asset, ASSET_FIELDS),
                "department": label(asset.department),
                "location": label(asset.location),
                "assignment": assignments.get(asset.pk),
                "expected": asset.pk in expected,
                "work_orders": orders[asset.pk],
                "transfers": transfers[asset.pk],
                "disposals": disposals[asset.pk],
                "schedule": fields(schedule, SCHEDULE_FIELDS) if schedule else None,
                "entry_count": schedule.entry_count if schedule else 0,
                "entry_total": scalar(entry.get("total", Decimal("0"))),
                "entry_last": scalar(entry.get("last")),
            }
        )


def capture(run, size):
    from assurance.services.runs import _asset_population

    if run.input_schema_version not in (0, INPUT_VERSION):
        raise ValueError("Unsupported assurance input schema.")
    if run.inputs.exists() or run.work_units.exists():
        raise ValueError("An unsealed run cannot contain execution inputs.")
    ordinal = capture_observations(run, size)
    population = 0
    population_query = _asset_population(run).only(
        "pk",
        *ASSET_FIELDS,
        "department__code",
        "department__name",
        "location__code",
        "location__name",
    )
    for assets in batches(population_query.iterator(chunk_size=size), size):
        pending = []
        for asset, payload in zip(assets, asset_payloads(run, assets), strict=True):
            ordinal += 1
            population += 1
            pending.append(
                AssuranceRunInput(
                    run=run,
                    kind="ASSET",
                    source_id=asset.pk,
                    asset_id=asset.pk,
                    subject_ordinal=ordinal,
                    payload=payload,
                )
            )
        AssuranceRunInput.objects.bulk_create(pending, batch_size=size)
    for starts in batches(range(1, ordinal + 1, size), size):
        AssuranceWorkUnit.objects.bulk_create(
            [
                AssuranceWorkUnit(
                    run=run,
                    ordinal=(start - 1) // size,
                    first_subject=start,
                    last_subject=min(start + size - 1, ordinal),
                )
                for start in starts
            ],
            batch_size=size,
        )
    run.population_count = population
    run.subject_count = ordinal
    run.unit_count = (ordinal + size - 1) // size
    run.work_unit_size = size
    run.input_schema_version = INPUT_VERSION
    run.sealed_at = timezone.now()
    run.execution_phase = "EVALUATE" if ordinal else "PUBLISH"


class FrozenLabel(SimpleNamespace):
    def __str__(self):
        return self.label


def thaw_label(value):
    if not value:
        return None
    pk = UUID(value["pk"]) if isinstance(value["pk"], str) else value["pk"]
    return FrozenLabel(pk=pk, label=value["label"])


def thaw(values):
    result = dict(values)
    for key, value in result.items():
        if value is None:
            continue
        if key.endswith("_id") and isinstance(value, str):
            result[key] = UUID(value)
        elif key in ("updated_at", "completed_at"):
            result[key] = datetime.fromisoformat(value)
        elif key == "capitalization_date":
            result[key] = date.fromisoformat(value)
        elif key in (
            "purchase_cost",
            "residual_value",
            "accumulated_depreciation",
            "current_book_value",
            "capitalized_cost",
            "depreciable_base",
            "capitalized_cost_at_disposal",
            "accumulated_depreciation_at_disposal",
        ):
            result[key] = Decimal(value)
    return SimpleNamespace(**result)


def observation(row):
    payload = row.payload
    obj = thaw({name: payload[name] for name in OBSERVATION_FIELDS})
    obj.pk, obj.asset_id, obj.campaign_id = row.source_id, row.asset_id, row.campaign_id
    for name in ("observed_location", "observed_department", "observed_custodian"):
        setattr(obj, name, thaw_label(payload[name]))
    return obj


def observations_for_unit(run, rows):
    assets = [row.source_id for row in rows if row.kind == "ASSET"]
    unregistered = [row.source_id for row in rows if row.kind == "OBSERVATION"]
    duplicates = run.inputs.filter(
        kind="OBSERVATION",
        campaign_id=OuterRef("campaign_id"),
        normalized_tag=OuterRef("normalized_tag"),
    ).exclude(pk=OuterRef("pk"))
    observations = (
        run.inputs.filter(kind="OBSERVATION")
        .filter(Q(asset_id__in=assets) | Q(source_id__in=unregistered))
        .annotate(duplicate=Exists(duplicates))
    )
    return {
        ("ASSET" if row.asset_id else "OBSERVATION", row.asset_id or row.source_id): row
        for row in observations
    }


def evaluate_input(run, row, observation_rows=None):
    from assurance.rules.evidence import evaluate_unregistered as evidence
    from assurance.rules.physical import evaluate_unregistered as physical
    from assurance.services.runs import _merge_candidates

    if row.payload.get("version") != INPUT_VERSION:
        raise ValueError("Unsupported assurance input payload.")
    ctx = EvaluationContext()
    candidates = []
    if observation_rows is None:
        observation_rows = observations_for_unit(run, [row])
    obs = observation_rows.get((row.kind, row.source_id))
    if obs:
        if obs.payload.get("version") != INPUT_VERSION:
            raise ValueError("Unsupported observation input payload.")
        value = observation(obs)
        if obs.payload["severe"]:
            ctx.severe_exception_verification_ids.add(value.pk)
        if obs.payload["not_found"]:
            ctx.asset_not_found_verification_ids.add(value.pk)
        if obs.payload["has_evidence"]:
            ctx.verification_evidence_ids.add(value.pk)
        if obs.normalized_tag and obs.duplicate:
            ctx.duplicate_tag_verifications.add(value.pk)
            ctx.duplicate_tag_assets.add(value.asset_id)
        if row.kind == "OBSERVATION":
            ctx.unregistered_verifications = [value]
            return _merge_candidates([*physical(ctx), *evidence(ctx)])
        ctx.latest_verification[row.source_id] = value
    p = row.payload
    asset = thaw(p["asset"])
    asset.pk = row.source_id
    asset.department, asset.location = thaw_label(p["department"]), thaw_label(p["location"])
    if p["assignment"]:
        ctx.assignments[asset.pk] = SimpleNamespace(assigned_to=thaw_label(p["assignment"]))
    if p["expected"]:
        ctx.campaign_expected_asset_ids.add(asset.pk)
    # Compact finite status counts retain repeated workflow text without storing rows.
    if sum(p["work_orders"].values()) * 32 > MAX_PAYLOAD_BYTES:
        raise InputTooLarge("Assurance workflow comparison exceeds 64 KiB.")
    ctx.work_orders[asset.pk] = [
        SimpleNamespace(status=status)
        for status, count in p["work_orders"].items()
        for _ in range(count)
    ]
    ctx.transfers[asset.pk] = [SimpleNamespace(status=status) for status in p["transfers"]]
    ctx.disposals[asset.pk] = [thaw(item) for item in p["disposals"]]
    if p["schedule"]:
        ctx.schedules[asset.pk] = thaw(p["schedule"])
    ctx.schedule_entry_counts[asset.pk] = p["entry_count"]
    ctx.entry_totals[asset.pk] = Decimal(p["entry_total"])
    if p["entry_last"]:
        ctx.entry_last_posted[asset.pk] = datetime.fromisoformat(p["entry_last"])
    for rule in RULES_BY_RUN_TYPE[run.run_type]:
        candidates.extend(rule(asset, ctx, run, run.started_at))
    return _merge_candidates(candidates)


def candidate_payload(candidate):
    return bounded({key: scalar(value) for key, value in asdict(candidate).items()})


def candidate_from_payload(payload):
    data = dict(payload)
    for key in ("asset_id", "verification_id"):
        data[key] = UUID(data[key]) if data[key] else None
    return FindingCandidate(**data)
