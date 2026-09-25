from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from transfers.models import AssetAssignment, AssetTransfer, TransferStatus
from transfers.permissions import CustodyTransferPermission
from transfers.selectors import (
    assignments_for_organization,
    transfers_for_organization,
    visible_assignments,
    visible_transfers,
)
from transfers.serializers import AssetAssignmentSerializer, AssetTransferSerializer
from transfers.services import (
    approve_transfer,
    assign_asset,
    cancel_transfer,
    complete_transfer,
    reject_transfer,
    request_transfer,
    return_asset,
)


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _service_error(exc):
    raise ValidationError(
        exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    ) from exc


class AssignmentViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = AssetAssignmentSerializer
    permission_classes = (CustodyTransferPermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("asset__asset_tag", "asset__name", "assigned_to__email", "notes")
    ordering_fields = ("assigned_at", "returned_at", "created_at", "asset__asset_tag")
    ordering = ("-assigned_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            return AssetAssignment.objects.none()
        queryset = assignments_for_organization(user.organization_id)
        queryset = visible_assignments(queryset, user)
        for parameter, field in (
            ("asset", "asset_id"),
            ("assigned_to", "assigned_to_id"),
            ("department", "department_id"),
            ("location", "location_id"),
        ):
            if self.request.query_params.get(parameter):
                queryset = queryset.filter(**{field: self.request.query_params[parameter]})
        if self.request.query_params.get("active") in {"true", "false"}:
            queryset = queryset.filter(
                returned_at__isnull=self.request.query_params["active"] == "true"
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        asset = values.pop("asset")
        try:
            assignment = assign_asset(
                asset_id=asset.pk, actor=request.user, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        output = self.get_serializer(assignment)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="return")
    def return_assignment(self, request, pk=None):
        assignment = self.get_object()
        try:
            closed = return_asset(
                asset_id=assignment.asset_id,
                assignment_id=assignment.pk,
                actor=request.user,
                ip_address=_ip(request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(closed).data)


class TransferViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = AssetTransferSerializer
    permission_classes = (CustodyTransferPermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("asset__asset_tag", "asset__name", "reason", "notes")
    ordering_fields = ("requested_at", "completed_at", "status", "asset__asset_tag")
    ordering = ("-requested_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            return AssetTransfer.objects.none()
        queryset = transfers_for_organization(user.organization_id)
        queryset = visible_transfers(queryset, user)
        if self.request.query_params.get("asset"):
            queryset = queryset.filter(asset_id=self.request.query_params["asset"])
        transfer_status = self.request.query_params.get("status")
        if transfer_status:
            if transfer_status not in TransferStatus.values:
                raise ValidationError({"status": "Select a valid transfer status."})
            queryset = queryset.filter(status=transfer_status)
        for parameter, field in (
            ("from_department", "from_department_id"),
            ("to_department", "to_department_id"),
            ("from_location", "from_location_id"),
            ("to_location", "to_location_id"),
        ):
            if self.request.query_params.get(parameter):
                queryset = queryset.filter(**{field: self.request.query_params[parameter]})
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        asset = values.pop("asset")
        try:
            transfer = request_transfer(
                asset_id=asset.pk, actor=request.user, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(transfer).data, status=status.HTTP_201_CREATED)

    def _transition(self, request, pk, service):
        transfer = self.get_object()
        try:
            changed = service(transfer_id=transfer.pk, actor=request.user, ip_address=_ip(request))
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(changed).data)

    @action(detail=True, methods=("post",))
    def approve(self, request, pk=None):
        return self._transition(request, pk, approve_transfer)

    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        return self._transition(request, pk, reject_transfer)

    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        return self._transition(request, pk, cancel_transfer)

    @action(detail=True, methods=("post",))
    def complete(self, request, pk=None):
        return self._transition(request, pk, complete_transfer)
