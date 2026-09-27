from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from assurance.models import (
    AssuranceRunStatus,
    AssuranceRunType,
    FindingSeverity,
    FindingSource,
    FindingStatus,
    FindingType,
)
from assurance.permissions import AssurancePermission
from assurance.selectors import (
    assurance_summary,
    findings_for_user,
    run_findings_for_user,
    runs_for_user,
)
from assurance.serializers import (
    AssuranceFindingSerializer,
    AssuranceRunSerializer,
    AssuranceSummarySerializer,
    FindingResolutionSerializer,
)
from assurance.services import (
    accept_finding,
    cancel_run,
    create_run,
    execute_run,
    reject_finding,
    resolve_finding,
    review_finding,
)
from common.pagination import StandardResultsPagination

_UUID_ID = [OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)]


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _service_error(exc):
    details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise ValidationError(details) from exc


class AssuranceRunViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = AssuranceRunSerializer
    permission_classes = (AssurancePermission,)
    pagination_class = StandardResultsPagination
    http_method_names = ("get", "post", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("status", "run_type", "id")
    ordering_fields = ("run_type", "status", "started_at", "completed_at", "created_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from assurance.models import AssuranceRun

            return AssuranceRun.objects.none()
        queryset = runs_for_user(user.organization_id, user)
        for parameter, field, allowed in (
            ("run_type", "run_type", AssuranceRunType.values),
            ("status", "status", AssuranceRunStatus.values),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                if value not in allowed:
                    raise ValidationError({parameter: f"Select a valid {parameter}."})
                queryset = queryset.filter(**{field: value})
        campaign_id = self.request.query_params.get("verification_campaign")
        if campaign_id:
            queryset = queryset.filter(verification_campaign_id=campaign_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            run = create_run(actor=request.user, ip_address=_ip(request), **data)
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    def _transition(self, request, pk, service):
        self.get_object()
        try:
            run = service(run_id=pk, actor=request.user, ip_address=_ip(request))
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(run).data)

    @extend_schema(parameters=_UUID_ID, request=None, responses=AssuranceRunSerializer)
    @action(detail=True, methods=("post",))
    def execute(self, request, pk=None):
        return self._transition(request, pk, execute_run)

    @extend_schema(parameters=_UUID_ID, request=None, responses=AssuranceRunSerializer)
    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        return self._transition(request, pk, cancel_run)

    @extend_schema(parameters=_UUID_ID, responses=AssuranceFindingSerializer(many=True))
    @action(detail=True, methods=("get",), pagination_class=StandardResultsPagination)
    def findings(self, request, pk=None):
        run = self.get_object()
        queryset = run_findings_for_user(run, request.user)
        page = self.paginate_queryset(queryset)
        serializer = AssuranceFindingSerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class AssuranceFindingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = AssuranceFindingSerializer
    permission_classes = (AssurancePermission,)
    pagination_class = StandardResultsPagination
    http_method_names = ("get", "post", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = (
        "asset__asset_tag",
        "asset__name",
        "finding_type",
        "description",
        "expected_value",
        "observed_value",
    )
    ordering_fields = (
        "finding_type",
        "severity",
        "status",
        "source",
        "first_detected_at",
        "last_detected_at",
        "occurrence_count",
        "created_at",
    )
    ordering = ("-last_detected_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from assurance.models import AssuranceFinding

            return AssuranceFinding.objects.none()
        queryset = findings_for_user(user.organization_id, user).prefetch_related("occurrences")
        for parameter, field, allowed in (
            ("finding_type", "finding_type", FindingType.values),
            ("severity", "severity", FindingSeverity.values),
            ("status", "status", FindingStatus.values),
            ("source", "source", FindingSource.values),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                if value not in allowed:
                    raise ValidationError({parameter: f"Select a valid {parameter}."})
                queryset = queryset.filter(**{field: value})
        for parameter, field in (
            ("run", "last_detected_run_id"),
            ("asset", "asset_id"),
            ("department", "asset__department_id"),
            ("location", "asset__location_id"),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def _transition(self, request, pk, service, *, needs_notes):
        self.get_object()
        values = {}
        if needs_notes:
            serializer = FindingResolutionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values["resolution_notes"] = serializer.validated_data["resolution_notes"]
        try:
            finding = service(
                finding_id=pk,
                actor=request.user,
                ip_address=_ip(request),
                **values,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(finding).data)

    @extend_schema(parameters=_UUID_ID, request=None, responses=AssuranceFindingSerializer)
    @action(detail=True, methods=("post",))
    def review(self, request, pk=None):
        return self._transition(request, pk, review_finding, needs_notes=False)

    @extend_schema(
        parameters=_UUID_ID,
        request=FindingResolutionSerializer,
        responses=AssuranceFindingSerializer,
    )
    @action(detail=True, methods=("post",))
    def resolve(self, request, pk=None):
        return self._transition(request, pk, resolve_finding, needs_notes=True)

    @extend_schema(
        parameters=_UUID_ID,
        request=FindingResolutionSerializer,
        responses=AssuranceFindingSerializer,
    )
    @action(detail=True, methods=("post",))
    def accept(self, request, pk=None):
        return self._transition(request, pk, accept_finding, needs_notes=True)

    @extend_schema(
        parameters=_UUID_ID,
        request=FindingResolutionSerializer,
        responses=AssuranceFindingSerializer,
    )
    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        return self._transition(request, pk, reject_finding, needs_notes=True)


class AssuranceSummaryView(APIView):
    permission_classes = (AssurancePermission,)

    @extend_schema(responses=AssuranceSummarySerializer)
    def get(self, request):
        return Response(assurance_summary(request.user.organization_id, request.user))
