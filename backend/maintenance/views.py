from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from maintenance.permissions import MaintenancePermission
from maintenance.selectors import (
    costs_for_organization,
    plans_for_organization,
    records_for_organization,
    work_orders_for_organization,
)
from maintenance.serializers import (
    AssignWorkOrderSerializer,
    CancelWorkOrderSerializer,
    CompleteWorkOrderSerializer,
    MaintenanceCostSerializer,
    MaintenancePlanSerializer,
    MaintenanceRecordSerializer,
    WorkOrderCompletionResultSerializer,
    WorkOrderSerializer,
)
from maintenance.services import (
    assign_work_order,
    cancel_work_order,
    complete_work_order,
    create_maintenance_cost,
    create_maintenance_plan,
    create_work_order,
    start_work_order,
    update_maintenance_plan,
)


def _ip(request):
    return request.META.get("REMOTE_ADDR")


_UUID_PATH_ID = [OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)]


def _service_error(exc):
    details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise ValidationError(details) from exc


def _date_filter(queryset, parameter, lookup):
    value = parameter[0]
    if not value:
        return queryset
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError({parameter[1]: "Use an ISO date in YYYY-MM-DD format."})
    return queryset.filter(**{lookup: parsed})


@extend_schema_view(
    retrieve=extend_schema(parameters=_UUID_PATH_ID),
    update=extend_schema(parameters=_UUID_PATH_ID),
    partial_update=extend_schema(parameters=_UUID_PATH_ID),
)
class MaintenancePlanViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = MaintenancePlanSerializer
    permission_classes = (MaintenancePermission,)
    http_method_names = ("get", "post", "put", "patch", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("asset__asset_tag", "asset__name", "instructions")
    ordering_fields = ("next_due_date", "maintenance_type", "active", "created_at")
    ordering = ("next_due_date",)

    def get_queryset(self):
        user = self.request.user
        queryset = plans_for_organization(user.organization_id, user)
        for param, field in (
            ("asset", "asset_id"),
            ("maintenance_type", "maintenance_type"),
            ("active", "active"),
        ):
            value = self.request.query_params.get(param)
            if value:
                if param == "active":
                    if value.lower() not in {"true", "false"}:
                        raise ValidationError({"active": "Use true or false."})
                    value = value.lower() == "true"
                queryset = queryset.filter(**{field: value})
        queryset = _date_filter(
            queryset,
            (self.request.query_params.get("next_due_date"), "next_due_date"),
            "next_due_date",
        )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        asset = values.pop("asset")
        try:
            plan = create_maintenance_plan(
                actor=request.user, asset_id=asset.pk, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        try:
            plan = update_maintenance_plan(
                plan_id=serializer.instance.pk,
                actor=self.request.user,
                changes=serializer.validated_data,
                ip_address=_ip(self.request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        serializer.instance = plan

    def destroy(self, request, *args, **kwargs):
        raise ValidationError("Maintenance plans are retained; deactivate them instead.")


@extend_schema_view(retrieve=extend_schema(parameters=_UUID_PATH_ID))
class WorkOrderViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = WorkOrderSerializer
    permission_classes = (MaintenancePermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = (
        "work_order_number",
        "asset__asset_tag",
        "asset__name",
        "description",
        "diagnosis",
    )
    ordering_fields = (
        "work_order_number",
        "status",
        "priority",
        "opened_at",
        "due_date",
        "completed_at",
    )
    ordering = ("-opened_at",)

    def get_queryset(self):
        user = self.request.user
        queryset = work_orders_for_organization(user.organization_id, user)
        mapping = (
            ("asset", "asset_id"),
            ("maintenance_type", "maintenance_type"),
            ("priority", "priority"),
            ("status", "status"),
            ("assigned_to", "assigned_to_id"),
            ("due_date", "due_date"),
        )
        for param, field in mapping:
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})
        queryset = _date_filter(
            queryset,
            (self.request.query_params.get("opened_after"), "opened_after"),
            "opened_at__date__gte",
        )
        queryset = _date_filter(
            queryset,
            (self.request.query_params.get("opened_before"), "opened_before"),
            "opened_at__date__lte",
        )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        asset = values.pop("asset")
        try:
            work_order = create_work_order(
                actor=request.user, asset_id=asset.pk, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(work_order).data, status=status.HTTP_201_CREATED)

    def _output(self, work_order):
        return Response(WorkOrderSerializer(work_order, context=self.get_serializer_context()).data)

    @extend_schema(
        parameters=_UUID_PATH_ID, request=AssignWorkOrderSerializer, responses=WorkOrderSerializer
    )
    @action(detail=True, methods=("post",), serializer_class=AssignWorkOrderSerializer)
    def assign(self, request, pk=None):
        work_order = self.get_object()
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            work_order = assign_work_order(
                work_order_id=work_order.pk,
                actor=request.user,
                ip_address=_ip(request),
                **data.validated_data,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return self._output(work_order)

    @extend_schema(parameters=_UUID_PATH_ID, request=None, responses=WorkOrderSerializer)
    @action(detail=True, methods=("post",))
    def start(self, request, pk=None):
        work_order = self.get_object()
        try:
            work_order = start_work_order(
                work_order_id=work_order.pk, actor=request.user, ip_address=_ip(request)
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return self._output(work_order)

    @extend_schema(
        parameters=_UUID_PATH_ID,
        request=CompleteWorkOrderSerializer,
        responses=WorkOrderCompletionResultSerializer,
    )
    @action(detail=True, methods=("post",), serializer_class=CompleteWorkOrderSerializer)
    def complete(self, request, pk=None):
        work_order = self.get_object()
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            work_order, record = complete_work_order(
                work_order_id=work_order.pk,
                actor=request.user,
                ip_address=_ip(request),
                **data.validated_data,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(
            {
                "work_order": WorkOrderSerializer(
                    work_order, context=self.get_serializer_context()
                ).data,
                "maintenance_record": MaintenanceRecordSerializer(record).data,
            }
        )

    @extend_schema(
        parameters=_UUID_PATH_ID, request=CancelWorkOrderSerializer, responses=WorkOrderSerializer
    )
    @action(detail=True, methods=("post",), serializer_class=CancelWorkOrderSerializer)
    def cancel(self, request, pk=None):
        work_order = self.get_object()
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            work_order = cancel_work_order(
                work_order_id=work_order.pk,
                actor=request.user,
                ip_address=_ip(request),
                **data.validated_data,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return self._output(work_order)


@extend_schema_view(retrieve=extend_schema(parameters=_UUID_PATH_ID))
class MaintenanceCostViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = MaintenanceCostSerializer
    permission_classes = (MaintenancePermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = (
        "description",
        "vendor_reference",
        "work_order__work_order_number",
        "work_order__asset__asset_tag",
    )
    ordering_fields = ("incurred_at", "total_cost", "cost_type", "created_at")
    ordering = ("-incurred_at",)

    def get_queryset(self):
        queryset = costs_for_organization(self.request.user.organization_id, self.request.user)
        if self.request.query_params.get("work_order"):
            queryset = queryset.filter(work_order_id=self.request.query_params["work_order"])
        if self.request.query_params.get("cost_type"):
            queryset = queryset.filter(cost_type=self.request.query_params["cost_type"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        work_order = values.pop("work_order")
        try:
            cost = create_maintenance_cost(
                actor=request.user, work_order_id=work_order.pk, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(cost).data, status=status.HTTP_201_CREATED)


@extend_schema_view(retrieve=extend_schema(parameters=_UUID_PATH_ID))
class MaintenanceRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = MaintenanceRecordSerializer
    permission_classes = (MaintenancePermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("asset__asset_tag", "asset__name", "work_order__work_order_number", "summary")
    ordering_fields = ("maintenance_date", "maintenance_type", "total_cost")
    ordering = ("-maintenance_date",)

    def get_queryset(self):
        queryset = records_for_organization(self.request.user.organization_id, self.request.user)
        for param, field in (("asset", "asset_id"), ("maintenance_type", "maintenance_type")):
            if self.request.query_params.get(param):
                queryset = queryset.filter(**{field: self.request.query_params[param]})
        return _date_filter(
            queryset,
            (self.request.query_params.get("maintenance_date"), "maintenance_date"),
            "maintenance_date",
        )
