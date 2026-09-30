from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import StandardResultsPagination
from reporting.models import ReportSnapshot, ReportSnapshotRow, SnapshotStatus
from reporting.permissions import ReportingPermission
from reporting.selectors import (
    DEFINITIONS,
    available_report_types,
    report_queryset,
    report_rows,
    serialize_report_row,
    snapshots_for_user,
    supported_filters,
)
from reporting.serializers import (
    PaginatedReportRowsSerializer,
    PaginatedReportSnapshotRowsSerializer,
    PaginatedReportSnapshotsSerializer,
    ReportCatalogSerializer,
    ReportSnapshotRequestSerializer,
    ReportSnapshotRowSerializer,
    ReportSnapshotSerializer,
)
from reporting.services import _safe_value, request_snapshot


class ReportCatalogView(APIView):
    permission_classes = (ReportingPermission,)

    @extend_schema(responses=ReportCatalogSerializer(many=True))
    def get(self, request):
        rows = [
            {
                "report_type": report_type,
                "label": definition.label,
                "result_url": f"/api/v1/reports/{report_type}/",
                "snapshot_supported": True,
                "columns": list(definition.fields),
                "filters": supported_filters(report_type),
            }
            for report_type, definition in DEFINITIONS.items()
            if report_type in available_report_types(request.user)
        ]
        return Response(ReportCatalogSerializer(rows, many=True).data)


class LiveReportView(APIView):
    permission_classes = (ReportingPermission,)
    pagination_class = StandardResultsPagination

    @extend_schema(
        parameters=[
            OpenApiParameter("report_type", OpenApiTypes.STR, OpenApiParameter.PATH),
            OpenApiParameter("department", OpenApiTypes.UUID, OpenApiParameter.QUERY),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("date_from", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("date_to", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("asset_tag", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
        responses=PaginatedReportRowsSerializer,
    )
    def get(self, request, report_type):
        filters = {
            key: request.query_params[key]
            for key in ("department", "status", "date_from", "date_to", "asset_tag", "search")
            if request.query_params.get(key) not in (None, "")
        }
        try:
            queryset = report_queryset(
                report_type, request.user.organization_id, request.user, filters
            )
        except DjangoValidationError as exc:
            details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError(details) from exc
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc

        rows = report_rows(queryset, report_type)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        data = [
            {
                key: _safe_value(value)
                for key, value in serialize_report_row(row, report_type).items()
            }
            for row in page
        ]
        return paginator.get_paginated_response(data)


class ReportSnapshotListCreateView(APIView):
    permission_classes = (ReportingPermission,)
    pagination_class = StandardResultsPagination

    @extend_schema(
        operation_id="report_snapshot_list", responses=PaginatedReportSnapshotsSerializer
    )
    def get(self, request):
        queryset = snapshots_for_user(request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(ReportSnapshotSerializer(page, many=True).data)

    @extend_schema(
        operation_id="report_snapshot_create",
        request=ReportSnapshotRequestSerializer,
        responses={202: ReportSnapshotSerializer, 200: ReportSnapshotSerializer},
    )
    def post(self, request):
        serializer = ReportSnapshotRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            snapshot, created = request_snapshot(
                user=request.user,
                report_type=serializer.validated_data["report_type"],
                filters=serializer.validated_data["filters"],
                idempotency_key=serializer.validated_data["idempotency_key"],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except DjangoValidationError as exc:
            details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError(details) from exc
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(
            ReportSnapshotSerializer(snapshot).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


class ReportSnapshotDetailView(APIView):
    permission_classes = (ReportingPermission,)

    def _get_snapshot(self, request, snapshot_id):
        queryset = snapshots_for_user(request.user)
        try:
            snapshot = queryset.get(pk=snapshot_id)
        except ReportSnapshot.DoesNotExist as exc:
            raise PermissionDenied("Snapshot is outside your report scope.") from exc
        self.check_object_permissions(request, snapshot)
        return snapshot

    @extend_schema(operation_id="report_snapshot_retrieve", responses=ReportSnapshotSerializer)
    def get(self, request, snapshot_id):
        snapshot = self._get_snapshot(request, snapshot_id)
        return Response(ReportSnapshotSerializer(snapshot).data)


class ReportSnapshotRowsView(ReportSnapshotDetailView):
    @extend_schema(
        operation_id="report_snapshot_rows_list",
        responses=PaginatedReportSnapshotRowsSerializer,
    )
    def get(self, request, snapshot_id):
        snapshot = self._get_snapshot(request, snapshot_id)
        if snapshot.status != SnapshotStatus.COMPLETED:
            return Response(
                {"detail": "Snapshot rows are available after generation completes."},
                status=status.HTTP_409_CONFLICT,
            )
        queryset = ReportSnapshotRow.objects.filter(snapshot=snapshot)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(ReportSnapshotRowSerializer(page, many=True).data)
