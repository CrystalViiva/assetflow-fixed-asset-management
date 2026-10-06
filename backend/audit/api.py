from django.db.models import Q
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import UserRole
from audit.models import AuditLog
from audit.serializers import AuditEventSerializer, PaginatedAuditEventsSerializer
from common.pagination import StandardResultsPagination


class AuditReadPermission(IsAuthenticated):
    """Audit visibility is limited to organization control roles."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(
            request.user.organization_id
            and (
                request.user.is_superuser
                or request.user.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            )
        )


class AuditEventListView(APIView):
    permission_classes = (AuditReadPermission,)
    pagination_class = StandardResultsPagination

    @extend_schema(
        operation_id="audit_event_list",
        parameters=[
            OpenApiParameter("action", OpenApiTypes.STR),
            OpenApiParameter("entity_type", OpenApiTypes.STR),
            OpenApiParameter("entity_id", OpenApiTypes.STR),
            OpenApiParameter("actor", OpenApiTypes.STR),
            OpenApiParameter("search", OpenApiTypes.STR),
            OpenApiParameter("date_from", OpenApiTypes.DATE),
            OpenApiParameter("date_to", OpenApiTypes.DATE),
            OpenApiParameter("ordering", OpenApiTypes.STR, enum=("timestamp", "-timestamp")),
            OpenApiParameter("page", OpenApiTypes.INT),
            OpenApiParameter("page_size", OpenApiTypes.INT),
        ],
        responses=PaginatedAuditEventsSerializer,
    )
    def get(self, request):
        queryset = AuditLog.objects.filter(
            organization_id=request.user.organization_id
        ).select_related("user")
        for parameter, field in (
            ("action", "action__iexact"),
            ("entity_type", "entity_type__iexact"),
            ("entity_id", "entity_id"),
        ):
            value = request.query_params.get(parameter)
            if value:
                if len(value) > 200:
                    raise ValidationError(
                        {parameter: "Keep filter values to 200 characters or fewer."}
                    )
                queryset = queryset.filter(**{field: value})

        actor = request.query_params.get("actor")
        search = request.query_params.get("search")
        for name, value in (("actor", actor), ("search", search)):
            if value and len(value) > 200:
                raise ValidationError({name: "Keep filter values to 200 characters or fewer."})
        if actor:
            queryset = queryset.filter(user__email__icontains=actor)
        if search:
            queryset = queryset.filter(
                Q(action__icontains=search)
                | Q(entity_type__icontains=search)
                | Q(entity_id__icontains=search)
                | Q(user__email__icontains=search)
            )

        for name, lookup in (
            ("date_from", "timestamp__date__gte"),
            ("date_to", "timestamp__date__lte"),
        ):
            raw = request.query_params.get(name)
            if raw:
                parsed = parse_date(raw)
                if not parsed:
                    raise ValidationError({name: "Enter a valid ISO date."})
                queryset = queryset.filter(**{lookup: parsed})
        if request.query_params.get("date_from") and request.query_params.get("date_to"):
            if parse_date(request.query_params["date_from"]) > parse_date(
                request.query_params["date_to"]
            ):
                raise ValidationError({"date_to": "Must be on or after date_from."})

        ordering = request.query_params.get("ordering", "-timestamp")
        if ordering not in {"timestamp", "-timestamp"}:
            raise ValidationError({"ordering": "Ordering must be timestamp or -timestamp."})
        queryset = queryset.order_by(ordering, "id" if ordering == "timestamp" else "-id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(AuditEventSerializer(page, many=True).data)
