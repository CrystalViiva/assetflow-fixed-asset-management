from decimal import Decimal, InvalidOperation

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

from disposals.models import DisposalMethod, DisposalStatus
from disposals.permissions import DisposalPermission
from disposals.selectors import disposals_for_organization
from disposals.serializers import DisposalReasonSerializer, DisposalSerializer
from disposals.services import (
    approve_disposal,
    cancel_disposal,
    complete_disposal,
    create_disposal,
    reject_disposal,
    submit_disposal,
    update_disposal,
)

_UUID_PATH_ID = [OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)]


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _service_error(exc):
    details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise ValidationError(details) from exc


@extend_schema_view(
    retrieve=extend_schema(parameters=_UUID_PATH_ID),
    update=extend_schema(parameters=_UUID_PATH_ID),
    partial_update=extend_schema(parameters=_UUID_PATH_ID),
)
class DisposalViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = DisposalSerializer
    permission_classes = (DisposalPermission,)
    http_method_names = ("get", "post", "patch", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("asset__asset_tag", "asset__name", "reason")
    ordering_fields = (
        "disposal_date",
        "status",
        "disposal_method",
        "proceeds",
        "gain_or_loss",
        "created_at",
    )
    ordering = ("-disposal_date",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from disposals.models import Disposal

            return Disposal.objects.none()
        queryset = disposals_for_organization(user.organization_id, user)
        for parameter, field in (
            ("asset", "asset_id"),
            ("status", "status"),
            ("disposal_method", "disposal_method"),
            ("requested_by", "requested_by_id"),
            ("approved_by", "approved_by_id"),
            ("department", "asset__department_id"),
            ("location", "asset__location_id"),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                if parameter == "status" and value not in DisposalStatus.values:
                    raise ValidationError({"status": "Select a valid disposal status."})
                if parameter == "disposal_method" and value not in DisposalMethod.values:
                    raise ValidationError({"disposal_method": "Select a valid disposal method."})
                queryset = queryset.filter(**{field: value})
        disposal_date = self.request.query_params.get("disposal_date")
        if disposal_date:
            parsed = parse_date(disposal_date)
            if parsed is None:
                raise ValidationError({"disposal_date": "Use YYYY-MM-DD format."})
            queryset = queryset.filter(disposal_date=parsed)
        for parameter, lookup in (
            ("gain_or_loss_min", "gain_or_loss__gte"),
            ("gain_or_loss_max", "gain_or_loss__lte"),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                try:
                    amount = Decimal(value)
                except InvalidOperation, TypeError, ValueError:
                    raise ValidationError({parameter: "Provide a valid decimal amount."}) from None
                queryset = queryset.filter(**{lookup: amount})
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        asset = values.pop("asset")
        try:
            disposal = create_disposal(
                actor=request.user, asset_id=asset.pk, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(disposal).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        try:
            disposal = update_disposal(
                disposal_id=serializer.instance.pk,
                actor=self.request.user,
                changes=serializer.validated_data,
                ip_address=_ip(self.request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        serializer.instance = disposal

    def _transition(self, request, pk, service, *, reason_serializer=False):
        disposal = self.get_object()
        reason = ""
        if reason_serializer:
            serializer = DisposalReasonSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            reason = serializer.validated_data["reason"]
        try:
            changed = service(
                disposal_id=disposal.pk,
                actor=request.user,
                ip_address=_ip(request),
                **({"reason": reason} if reason_serializer else {}),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(changed).data)

    @extend_schema(parameters=_UUID_PATH_ID, request=None, responses=DisposalSerializer)
    @action(detail=True, methods=("post",))
    def submit(self, request, pk=None):
        return self._transition(request, pk, submit_disposal)

    @extend_schema(parameters=_UUID_PATH_ID, request=None, responses=DisposalSerializer)
    @action(detail=True, methods=("post",))
    def approve(self, request, pk=None):
        return self._transition(request, pk, approve_disposal)

    @extend_schema(
        parameters=_UUID_PATH_ID, request=DisposalReasonSerializer, responses=DisposalSerializer
    )
    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        return self._transition(request, pk, reject_disposal, reason_serializer=True)

    @extend_schema(
        parameters=_UUID_PATH_ID, request=DisposalReasonSerializer, responses=DisposalSerializer
    )
    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        return self._transition(request, pk, cancel_disposal, reason_serializer=True)

    @extend_schema(parameters=_UUID_PATH_ID, request=None, responses=DisposalSerializer)
    @action(detail=True, methods=("post",))
    def complete(self, request, pk=None):
        return self._transition(request, pk, complete_disposal)
