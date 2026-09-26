"""Organization-scoped assurance queries and database-derived campaign progress."""

from django.db.models import (
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from accounts.models import UserRole
from assets.models import Asset, AssetStatus
from verification.models import (
    CampaignScope,
    ExceptionStatus,
    PhysicalVerification,
    VerificationCampaign,
    VerificationEvidence,
    VerificationException,
    VerificationResult,
)

EXPECTED_STATUSES = (
    AssetStatus.ACTIVE,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.TRANSFERRED,
    AssetStatus.IMPAIRED,
)
TERMINAL_EXCEPTION_STATUSES = (ExceptionStatus.RESOLVED,)


def expected_assets(campaign):
    """Capitalized, non-disposed asset population under a campaign's declared scope."""
    assets = Asset.objects.filter(
        organization_id=campaign.organization_id,
        capitalization_date__isnull=False,
        status__in=EXPECTED_STATUSES,
    )
    if campaign.scope_type == CampaignScope.DEPARTMENT:
        assets = assets.filter(department_id=campaign.department_id)
    elif campaign.scope_type == CampaignScope.LOCATION:
        assets = assets.filter(location_id=campaign.location_id)
    return assets


def campaigns_for_organization(organization, user):
    org_id = getattr(organization, "pk", organization)
    queryset = VerificationCampaign.objects.filter(organization_id=org_id).select_related(
        "organization", "department", "location", "created_by", "updated_by"
    )

    if user.role == UserRole.DEPARTMENT_MANAGER:
        if not user.department_id:
            return queryset.none()
        queryset = queryset.filter(
            scope_type=CampaignScope.DEPARTMENT, department_id=user.department_id
        )

    # Separate grouped subqueries let each campaign row compute its scoped population
    # without loading asset or verification histories into Python.
    assets = Asset.objects.filter(
        organization_id=OuterRef("organization_id"),
        capitalization_date__isnull=False,
        status__in=EXPECTED_STATUSES,
    )
    org_expected = assets.values("organization_id").annotate(n=Count("pk")).values("n")[:1]
    dept_expected = (
        assets.filter(department_id=OuterRef("department_id"))
        .values("organization_id")
        .annotate(n=Count("pk"))
        .values("n")[:1]
    )
    location_expected = (
        assets.filter(location_id=OuterRef("location_id"))
        .values("organization_id")
        .annotate(n=Count("pk"))
        .values("n")[:1]
    )
    expected_expression = Case(
        When(
            scope_type=CampaignScope.ORGANIZATION, then=Coalesce(Subquery(org_expected), Value(0))
        ),
        When(scope_type=CampaignScope.DEPARTMENT, then=Coalesce(Subquery(dept_expected), Value(0))),
        When(
            scope_type=CampaignScope.LOCATION, then=Coalesce(Subquery(location_expected), Value(0))
        ),
        default=Value(0),
        output_field=IntegerField(),
    )

    found_base = PhysicalVerification.objects.filter(
        campaign_id=OuterRef("pk"),
        asset__isnull=False,
        asset__capitalization_date__isnull=False,
        asset__status__in=EXPECTED_STATUSES,
    ).exclude(result=VerificationResult.ASSET_NOT_FOUND)
    org_found = (
        found_base.filter(campaign__scope_type=CampaignScope.ORGANIZATION)
        .values("campaign_id")
        .annotate(n=Count("asset_id", distinct=True))
        .values("n")[:1]
    )
    dept_found = (
        found_base.filter(
            campaign__scope_type=CampaignScope.DEPARTMENT,
            asset__department_id=F("campaign__department_id"),
        )
        .values("campaign_id")
        .annotate(n=Count("asset_id", distinct=True))
        .values("n")[:1]
    )
    location_found = (
        found_base.filter(
            campaign__scope_type=CampaignScope.LOCATION,
            asset__location_id=F("campaign__location_id"),
        )
        .values("campaign_id")
        .annotate(n=Count("asset_id", distinct=True))
        .values("n")[:1]
    )
    found_expression = Case(
        When(scope_type=CampaignScope.ORGANIZATION, then=Coalesce(Subquery(org_found), Value(0))),
        When(scope_type=CampaignScope.DEPARTMENT, then=Coalesce(Subquery(dept_found), Value(0))),
        When(scope_type=CampaignScope.LOCATION, then=Coalesce(Subquery(location_found), Value(0))),
        default=Value(0),
        output_field=IntegerField(),
    )
    exception_count = (
        VerificationException.objects.filter(campaign_id=OuterRef("pk"))
        .values("campaign_id")
        .annotate(n=Count("pk"))
        .values("n")[:1]
    )
    resolved_count = (
        VerificationException.objects.filter(
            campaign_id=OuterRef("pk"), status__in=TERMINAL_EXCEPTION_STATUSES
        )
        .values("campaign_id")
        .annotate(n=Count("pk"))
        .values("n")[:1]
    )
    return queryset.annotate(
        expected_asset_count=Coalesce(expected_expression, Value(0)),
        verified_asset_count=Coalesce(found_expression, Value(0)),
        exception_count=Coalesce(Subquery(exception_count), Value(0)),
        resolved_exception_count=Coalesce(Subquery(resolved_count), Value(0)),
    ).annotate(
        unverified_asset_count=F("expected_asset_count") - F("verified_asset_count"),
        verification_percentage=Case(
            When(expected_asset_count=0, then=Value(0)),
            default=ExpressionWrapper(
                F("verified_asset_count") * Value(100) / F("expected_asset_count"),
                output_field=DecimalField(max_digits=7, decimal_places=2),
            ),
            output_field=DecimalField(max_digits=7, decimal_places=2),
        ),
    )


def verifications_for_organization(organization, user):
    queryset = PhysicalVerification.objects.filter(organization_id=organization).select_related(
        "organization",
        "campaign",
        "asset",
        "asset__department",
        "asset__location",
        "verified_by",
        "observed_location",
        "observed_department",
        "observed_custodian",
    )
    if user.role == UserRole.DEPARTMENT_MANAGER:
        if not user.department_id:
            return queryset.none()
        queryset = queryset.filter(
            Q(
                campaign__scope_type=CampaignScope.DEPARTMENT,
                campaign__department_id=user.department_id,
            )
            | Q(asset__department_id=user.department_id)
            | Q(observed_department_id=user.department_id)
        ).distinct()
    return queryset


def exceptions_for_organization(organization, user):
    queryset = VerificationException.objects.filter(organization_id=organization).select_related(
        "organization",
        "campaign",
        "verification",
        "asset",
        "asset__department",
        "assigned_to",
        "resolved_by",
    )
    if user.role == UserRole.DEPARTMENT_MANAGER:
        if not user.department_id:
            return queryset.none()
        queryset = queryset.filter(
            Q(
                campaign__scope_type=CampaignScope.DEPARTMENT,
                campaign__department_id=user.department_id,
            )
            | Q(asset__department_id=user.department_id)
            | Q(verification__observed_department_id=user.department_id)
        ).distinct()
    return queryset


def evidence_for_organization(organization, user):
    queryset = VerificationEvidence.objects.filter(organization_id=organization).select_related(
        "organization", "verification", "verification__asset", "exception", "captured_by"
    )
    if user.role == UserRole.DEPARTMENT_MANAGER:
        if not user.department_id:
            return queryset.none()
        queryset = queryset.filter(
            Q(
                verification__campaign__scope_type=CampaignScope.DEPARTMENT,
                verification__campaign__department_id=user.department_id,
            )
            | Q(verification__asset__department_id=user.department_id)
            | Q(verification__observed_department_id=user.department_id)
        ).distinct()
    return queryset
