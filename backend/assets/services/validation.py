from django.core.exceptions import ValidationError


def validate_organization_relationships(*, organization, category, department=None, location=None):
    """Reject related master data that belongs to a different organization."""
    if organization is None or not organization.pk:
        raise ValidationError({"organization": "An organization is required."})

    errors = {}
    for field_name, related_object in (
        ("category", category),
        ("department", department),
        ("location", location),
    ):
        if related_object and related_object.organization_id != organization.pk:
            errors[field_name] = f"The {field_name} must belong to the asset's organization."

    if errors:
        raise ValidationError(errors)
