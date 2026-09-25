"""Database-backed query filters for the asset register."""

from uuid import UUID

from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend

from assets.models import AssetStatus


class AssetFilterBackend(BaseFilterBackend):
    def get_schema_operation_parameters(self, view):
        parameters = [
            ("status", "string", AssetStatus.values),
            ("category", "string", None),
            ("category__name", "string", None),
            ("department", "string", None),
            ("department__name", "string", None),
            ("location", "string", None),
            ("location__name", "string", None),
            ("manufacturer", "string", None),
            ("acquisition_date_after", "string", None),
            ("acquisition_date_before", "string", None),
        ]
        return [
            {
                "name": name,
                "required": False,
                "in": "query",
                "schema": {"type": schema_type, **({"enum": enum} if enum else {})},
            }
            for name, schema_type, enum in parameters
        ]

    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        status = params.get("status")
        if status:
            if status not in AssetStatus.values:
                raise ValidationError({"status": "Select a valid asset status."})
            queryset = queryset.filter(status=status)

        for query_name, relation_name in (
            ("category", "category"),
            ("category__name", "category"),
            ("department", "department"),
            ("department__name", "department"),
            ("location", "location"),
            ("location__name", "location"),
        ):
            value = params.get(query_name)
            if value:
                queryset = self._filter_relation(queryset, relation_name, value)

        manufacturer = params.get("manufacturer")
        if manufacturer:
            queryset = queryset.filter(manufacturer__icontains=manufacturer.strip())

        date_after = self._query_date(
            params.get("acquisition_date_after"), "acquisition_date_after"
        )
        date_before = self._query_date(
            params.get("acquisition_date_before"), "acquisition_date_before"
        )
        if date_after and date_before and date_after > date_before:
            raise ValidationError(
                {"acquisition_date": "The start date must not be after the end date."}
            )
        if date_after:
            queryset = queryset.filter(acquisition_date__gte=date_after)
        if date_before:
            queryset = queryset.filter(acquisition_date__lte=date_before)
        return queryset

    @staticmethod
    def _filter_relation(queryset, relation_name, value):
        try:
            relation_id = UUID(value)
        except ValueError, TypeError:
            return queryset.filter(**{f"{relation_name}__name__iexact": value.strip()})
        return queryset.filter(**{f"{relation_name}_id": relation_id})

    @staticmethod
    def _query_date(value, field_name):
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise ValidationError({field_name: "Enter a valid date in YYYY-MM-DD format."})
        return parsed
