from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.models import UserRole
from depreciation.permissions import DepreciationPermission
from depreciation.selectors import (
    entries_for_organization,
    periods_for_organization,
    schedules_for_organization,
)
from depreciation.serializers import (
    AccountingPeriodSerializer,
    DepreciationEntrySerializer,
    DepreciationScheduleSerializer,
    PostDepreciationSerializer,
    ScheduleCreateSerializer,
)
from depreciation.services import (
    close_accounting_period,
    create_accounting_period,
    generate_depreciation_schedule,
    post_depreciation,
)


def _service_error(exc):
    raise ValidationError(
        exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    ) from exc


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _apply_ordering(queryset, request, allowed):
    requested = request.query_params.get("ordering", "")
    fields = []
    for item in requested.split(","):
        field = item.lstrip("-")
        if field in allowed:
            fields.append(("-" if item.startswith("-") else "") + allowed[field])
    return queryset.order_by(*fields) if fields else queryset


class DepreciationScheduleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = DepreciationScheduleSerializer
    permission_classes = (DepreciationPermission,)
    lookup_value_converter = "uuid"

    def get_queryset(self):
        qs = schedules_for_organization(self.request.user.organization_id)
        if self.request.user.role == UserRole.DEPARTMENT_MANAGER:
            if not self.request.user.department_id:
                return qs.none()
            qs = qs.filter(asset__department_id=self.request.user.department_id)
        for field in ("asset", "method", "status"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{f"{field}_id" if field == "asset" else field: value})
        if self.request.query_params.get("asset_tag"):
            qs = qs.filter(asset__asset_tag__iexact=self.request.query_params["asset_tag"])
        if self.request.query_params.get("search"):
            term = self.request.query_params["search"]
            qs = qs.filter(Q(asset__asset_tag__icontains=term) | Q(asset__name__icontains=term))
        for parameter, lookup in (
            ("start_date_after", "start_date__gte"),
            ("start_date_before", "start_date__lte"),
        ):
            if self.request.query_params.get(parameter):
                qs = qs.filter(**{lookup: self.request.query_params[parameter]})
        return _apply_ordering(
            qs,
            self.request,
            {"asset_tag": "asset__asset_tag", "start_date": "start_date", "end_date": "end_date"},
        )

    def create(self, request, *args, **kwargs):
        data = ScheduleCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            schedule = generate_depreciation_schedule(
                asset_id=data.validated_data["asset_id"],
                actor=request.user,
                ip_address=_ip(request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(schedule).data, status=status.HTTP_201_CREATED)


class DepreciationEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = DepreciationEntrySerializer
    permission_classes = (DepreciationPermission,)
    lookup_value_converter = "uuid"

    def get_queryset(self):
        qs = entries_for_organization(self.request.user.organization_id)
        if self.request.user.role == UserRole.DEPARTMENT_MANAGER:
            if not self.request.user.department_id:
                return qs.none()
            qs = qs.filter(asset__department_id=self.request.user.department_id)
        for field in ("asset", "accounting_period"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{f"{field}_id": value})
        if self.request.query_params.get("asset_tag"):
            qs = qs.filter(asset__asset_tag__iexact=self.request.query_params["asset_tag"])
        if self.request.query_params.get("search"):
            term = self.request.query_params["search"]
            qs = qs.filter(Q(asset__asset_tag__icontains=term) | Q(asset__name__icontains=term))
        if self.request.query_params.get("year"):
            qs = qs.filter(accounting_period__year=self.request.query_params["year"])
        if self.request.query_params.get("month"):
            qs = qs.filter(accounting_period__month=self.request.query_params["month"])
        if self.request.query_params.get("method"):
            qs = qs.filter(schedule__method=self.request.query_params["method"])
        period = self.request.query_params.get("period")
        if period:
            try:
                year, month = (int(part) for part in period.split("-", maxsplit=1))
                if not 1 <= month <= 12:
                    raise ValueError
            except ValueError:
                raise ValidationError({"period": "Use a valid YYYY-MM calendar period."}) from None
            qs = qs.filter(accounting_period__year=year, accounting_period__month=month)
        for parameter, comparison in (("period_after", "gte"), ("period_before", "lte")):
            raw_date = self.request.query_params.get(parameter)
            if raw_date:
                try:
                    cutoff = date.fromisoformat(raw_date)
                except ValueError:
                    raise ValidationError({parameter: "Use an ISO date (YYYY-MM-DD)."}) from None
                year_comparison = "gt" if comparison == "gte" else "lt"
                condition = Q(**{f"accounting_period__year__{year_comparison}": cutoff.year}) | Q(
                    accounting_period__year=cutoff.year,
                    **{f"accounting_period__month__{comparison}": cutoff.month},
                )
                qs = qs.filter(condition)
        return _apply_ordering(
            qs,
            self.request,
            {
                "asset_tag": "asset__asset_tag",
                "posted_at": "posted_at",
                "depreciation_amount": "depreciation_amount",
            },
        )

    @action(detail=False, methods=("post",), url_path="post")
    def post_entry(self, request):
        data = PostDepreciationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            entry = post_depreciation(
                **data.validated_data, actor=request.user, ip_address=_ip(request)
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)


class AccountingPeriodViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = AccountingPeriodSerializer
    permission_classes = (DepreciationPermission,)
    lookup_value_converter = "uuid"

    def get_queryset(self):
        qs = periods_for_organization(self.request.user.organization_id)
        for field in ("year", "month", "status"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return _apply_ordering(
            qs, self.request, {"year": "year", "month": "month", "status": "status"}
        )

    def create(self, request, *args, **kwargs):
        serializer = AccountingPeriodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            period = create_accounting_period(
                actor=request.user,
                year=serializer.validated_data["year"],
                month=serializer.validated_data["month"],
                ip_address=_ip(request),
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(period).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="close")
    def close(self, request, pk=None):
        period = self.get_object()
        try:
            period = close_accounting_period(
                period_id=period.pk, actor=request.user, ip_address=_ip(request)
            )
        except DjangoValidationError as exc:
            _service_error(exc)
        return Response(self.get_serializer(period).data)
