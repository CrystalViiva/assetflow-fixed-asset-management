from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from verification.models import (
    CampaignScope,
    CampaignStatus,
    EvidenceType,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionType,
    PhysicalCondition,
    VerificationResult,
)
from verification.permissions import VerificationPermission
from verification.selectors import (
    campaigns_for_organization,
    evidence_for_organization,
    exceptions_for_organization,
    verifications_for_organization,
)
from verification.serializers import (
    ExceptionAssignmentSerializer,
    ExceptionResolutionSerializer,
    ManualVerificationExceptionSerializer,
    MissingReconciliationResultSerializer,
    PhysicalVerificationSerializer,
    VerificationCampaignSerializer,
    VerificationEvidenceSerializer,
    VerificationExceptionSerializer,
)
from verification.services import (
    accept_exception,
    assign_exception,
    cancel_campaign,
    complete_campaign,
    create_campaign,
    create_evidence,
    create_manual_exception,
    create_verification,
    reconcile_missing_assets,
    reject_exception,
    resolve_exception,
    start_campaign,
    start_exception_review,
    update_campaign,
)

_UUID_ID = [OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)]


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _service_error(exc):
    details = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    raise ValidationError(details) from exc


class CampaignViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = VerificationCampaignSerializer
    permission_classes = (VerificationPermission,)
    http_method_names = ("get", "post", "patch", "put", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("name", "description", "department__name", "location__name")
    ordering_fields = ("name", "status", "scope_type", "start_date", "due_date", "created_at")
    ordering = ("-start_date", "name")

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from verification.models import VerificationCampaign

            return VerificationCampaign.objects.none()
        queryset = campaigns_for_organization(user.organization_id, user)
        for name, field, choices in (
            ("status", "status", CampaignStatus.values),
            ("scope_type", "scope_type", CampaignScope.values),
            ("department", "department_id", None),
            ("location", "location_id", None),
        ):
            value = self.request.query_params.get(name)
            if value:
                if choices and value not in choices:
                    raise ValidationError({name: "Select a valid choice."})
                queryset = queryset.filter(**{field: value})
        return queryset

    def _serialized_campaign(self, campaign_id):
        campaign = self.get_queryset().get(pk=campaign_id)
        return self.get_serializer(campaign).data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campaign = create_campaign(
                actor=request.user, ip_address=_ip(request), **serializer.validated_data
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self._serialized_campaign(campaign.pk), status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        try:
            update_campaign(
                campaign_id=serializer.instance.pk,
                actor=self.request.user,
                changes=serializer.validated_data,
                ip_address=_ip(self.request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        response.data = self._serialized_campaign(kwargs["pk"])
        return response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        response.data = self._serialized_campaign(kwargs["pk"])
        return response

    def _transition(self, request, pk, service):
        campaign = self.get_object()
        try:
            changed = service(campaign_id=campaign.pk, actor=request.user, ip_address=_ip(request))
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self._serialized_campaign(changed.pk))

    @extend_schema(parameters=_UUID_ID, request=None, responses=VerificationCampaignSerializer)
    @action(detail=True, methods=("post",))
    def start(self, request, pk=None):
        return self._transition(request, pk, start_campaign)

    @extend_schema(parameters=_UUID_ID, request=None, responses=VerificationCampaignSerializer)
    @action(detail=True, methods=("post",))
    def complete(self, request, pk=None):
        return self._transition(request, pk, complete_campaign)

    @extend_schema(parameters=_UUID_ID, request=None, responses=VerificationCampaignSerializer)
    @action(detail=True, methods=("post",))
    def cancel(self, request, pk=None):
        return self._transition(request, pk, cancel_campaign)

    @extend_schema(
        parameters=_UUID_ID, request=None, responses=MissingReconciliationResultSerializer
    )
    @action(detail=True, methods=("post",), url_path="reconcile-missing")
    def reconcile_missing(self, request, pk=None):
        campaign = self.get_object()
        try:
            created_count = reconcile_missing_assets(
                campaign_id=campaign.pk, actor=request.user, ip_address=_ip(request)
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response({"created_count": created_count})


class PhysicalVerificationViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = PhysicalVerificationSerializer
    permission_classes = (VerificationPermission,)
    http_method_names = ("get", "post", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("observed_asset_tag", "observed_description", "notes", "asset__asset_tag")
    ordering_fields = ("verified_at", "result", "observed_condition", "created_at")
    ordering = ("-verified_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from verification.models import PhysicalVerification

            return PhysicalVerification.objects.none()
        queryset = verifications_for_organization(user.organization_id, user).prefetch_related(
            "exceptions"
        )
        for name, field, choices in (
            ("campaign", "campaign_id", None),
            ("asset", "asset_id", None),
            ("observed_department", "observed_department_id", None),
            ("observed_location", "observed_location_id", None),
            ("observed_custodian", "observed_custodian_id", None),
            ("result", "result", VerificationResult.values),
            ("observed_condition", "observed_condition", PhysicalCondition.values),
        ):
            value = self.request.query_params.get(name)
            if value:
                if choices and value not in choices:
                    raise ValidationError({name: "Select a valid choice."})
                queryset = queryset.filter(**{field: value})
        verified_after = self.request.query_params.get("verified_after")
        verified_before = self.request.query_params.get("verified_before")
        for value, parameter in (
            (verified_after, "verified_after"),
            (verified_before, "verified_before"),
        ):
            if value and parse_date(value) is None:
                raise ValidationError({parameter: "Use YYYY-MM-DD format."})
        if verified_after:
            queryset = queryset.filter(verified_at__date__gte=parse_date(verified_after))
        if verified_before:
            queryset = queryset.filter(verified_at__date__lte=parse_date(verified_before))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        campaign = values.pop("campaign")
        asset = values.pop("asset", None)
        try:
            verification = create_verification(
                actor=request.user,
                campaign_id=campaign.pk,
                asset_id=asset.pk if asset else None,
                ip_address=_ip(request),
                **values,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        result = self.get_queryset().get(pk=verification.pk)
        return Response(self.get_serializer(result).data, status=status.HTTP_201_CREATED)


class VerificationExceptionViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = VerificationExceptionSerializer
    permission_classes = (VerificationPermission,)
    http_method_names = ("get", "post", "head", "options")
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("description", "asset__asset_tag", "resolution_notes", "resolution_reference")
    ordering_fields = ("exception_type", "severity", "status", "created_at", "resolved_at")
    ordering = ("-created_at",)

    @extend_schema(
        request=ManualVerificationExceptionSerializer,
        responses={201: VerificationExceptionSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = ManualVerificationExceptionSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        verification = values.pop("verification")
        try:
            exception = create_manual_exception(
                actor=request.user,
                verification_id=verification.pk,
                ip_address=_ip(request),
                **values,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(exception).data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from verification.models import VerificationException

            return VerificationException.objects.none()
        queryset = exceptions_for_organization(user.organization_id, user)
        for name, field, choices in (
            ("campaign", "campaign_id", None),
            ("asset", "asset_id", None),
            ("status", "status", ExceptionStatus.values),
            ("exception_type", "exception_type", ExceptionType.values),
            ("severity", "severity", ExceptionSeverity.values),
            ("assigned_to", "assigned_to_id", None),
        ):
            value = self.request.query_params.get(name)
            if value:
                if choices and value not in choices:
                    raise ValidationError({name: "Select a valid choice."})
                queryset = queryset.filter(**{field: value})
        for name, field in (
            ("department", "verification__observed_department_id"),
            ("location", "verification__observed_location_id"),
        ):
            value = self.request.query_params.get(name)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def _action(self, request, pk, service, *, payload_serializer=None, extra=None):
        exception = self.get_object()
        values = {}
        if payload_serializer:
            serializer = payload_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
        try:
            changed = service(
                exception_id=exception.pk, actor=request.user, ip_address=_ip(request), **values
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(changed).data)

    @extend_schema(
        parameters=_UUID_ID,
        request=ExceptionAssignmentSerializer,
        responses=VerificationExceptionSerializer,
    )
    @action(detail=True, methods=("post",))
    def assign(self, request, pk=None):
        return self._action(
            request, pk, assign_exception, payload_serializer=ExceptionAssignmentSerializer
        )

    @extend_schema(parameters=_UUID_ID, request=None, responses=VerificationExceptionSerializer)
    @action(detail=True, methods=("post",), url_path="start-review")
    def start_review(self, request, pk=None):
        return self._action(request, pk, start_exception_review)

    @extend_schema(
        parameters=_UUID_ID,
        request=ExceptionResolutionSerializer,
        responses=VerificationExceptionSerializer,
    )
    @action(detail=True, methods=("post",))
    def resolve(self, request, pk=None):
        return self._action(
            request, pk, resolve_exception, payload_serializer=ExceptionResolutionSerializer
        )

    @extend_schema(
        parameters=_UUID_ID,
        request=ExceptionResolutionSerializer,
        responses=VerificationExceptionSerializer,
    )
    @action(detail=True, methods=("post",))
    def accept(self, request, pk=None):
        return self._action(
            request, pk, accept_exception, payload_serializer=ExceptionResolutionSerializer
        )

    @extend_schema(
        parameters=_UUID_ID,
        request=ExceptionResolutionSerializer,
        responses=VerificationExceptionSerializer,
    )
    @action(detail=True, methods=("post",))
    def reject(self, request, pk=None):
        return self._action(
            request, pk, reject_exception, payload_serializer=ExceptionResolutionSerializer
        )


class VerificationEvidenceViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    serializer_class = VerificationEvidenceSerializer
    permission_classes = (VerificationPermission,)
    http_method_names = ("get", "post", "head", "options")
    filter_backends = (OrderingFilter,)
    ordering_fields = ("captured_at", "evidence_type", "created_at")
    ordering = ("-captured_at",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            from verification.models import VerificationEvidence

            return VerificationEvidence.objects.none()
        queryset = evidence_for_organization(user.organization_id, user)
        for name, field in (
            ("verification", "verification_id"),
            ("exception", "exception_id"),
            ("evidence_type", "evidence_type"),
        ):
            value = self.request.query_params.get(name)
            if value:
                if name == "evidence_type" and value not in EvidenceType.values:
                    raise ValidationError({name: "Select a valid evidence type."})
                queryset = queryset.filter(**{field: value})
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        verification = values.pop("verification")
        exception = values.pop("exception", None)
        try:
            evidence = create_evidence(
                actor=request.user,
                verification_id=verification.pk,
                exception=exception,
                ip_address=_ip(request),
                **values,
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(evidence).data, status=status.HTTP_201_CREATED)
