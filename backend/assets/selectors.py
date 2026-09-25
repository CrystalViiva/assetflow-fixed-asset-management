"""Reusable organization-scoped asset queries."""

from assets.models import Acquisition, Asset, AssetCategory, AssetStatus


def acquisitions_for_organization(organization):
    organization_id = getattr(organization, "pk", organization)
    return Acquisition.objects.filter(
        organization_id=organization_id,
        asset__organization_id=organization_id,
    ).select_related(
        "organization",
        "asset",
        "asset__category",
        "asset__department",
        "created_by",
        "updated_by",
    )


def assets_for_organization(organization):
    organization_id = getattr(organization, "pk", organization)
    return Asset.objects.filter(organization_id=organization_id).select_related(
        "organization", "category", "department", "location", "created_by", "updated_by"
    )


def active_assets(organization):
    return assets_for_organization(organization).filter(status=AssetStatus.ACTIVE)


def assets_by_category(organization, category):
    category_id = getattr(category, "pk", category)
    return assets_for_organization(organization).filter(category_id=category_id)


def assets_by_department(organization, department):
    department_id = getattr(department, "pk", department)
    return assets_for_organization(organization).filter(department_id=department_id)


def assets_by_location(organization, location):
    location_id = getattr(location, "pk", location)
    return assets_for_organization(organization).filter(location_id=location_id)


def assets_by_status(organization, status):
    return assets_for_organization(organization).filter(status=status)


def categories_for_organization(organization):
    organization_id = getattr(organization, "pk", organization)
    return AssetCategory.objects.filter(organization_id=organization_id).select_related(
        "organization"
    )
