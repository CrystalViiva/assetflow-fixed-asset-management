from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.viewsets import GenericViewSet

from accounts.models import UserRole
from assets.filters import AssetFilterBackend
from assets.models import Asset, AssetCategory
from assets.permissions import AssetDomainPermission
from assets.selectors import active_assets, assets_for_organization, categories_for_organization
from assets.serializers import AssetCategorySerializer, AssetSerializer
from assets.services import create_asset, update_asset


def _request_ip(request):
    return request.META.get("REMOTE_ADDR")


class AssetViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = AssetSerializer
    permission_classes = (AssetDomainPermission,)
    filter_backends = (AssetFilterBackend, SearchFilter, OrderingFilter)
    search_fields = (
        "asset_tag",
        "name",
        "serial_number",
        "model_number",
        "manufacturer",
        "description",
    )
    ordering_fields = (
        "asset_tag",
        "name",
        "status",
        "acquisition_date",
        "purchase_cost",
        "current_book_value",
        "created_at",
    )
    ordering = ("asset_tag",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            return Asset.objects.none()
        queryset = assets_for_organization(user.organization_id)
        if user.role == UserRole.DEPARTMENT_MANAGER:
            if not user.department_id:
                return queryset.none()
            return queryset.filter(
                department_id=user.department_id,
                department__organization_id=user.organization_id,
            )
        if user.role == UserRole.EMPLOYEE:
            return active_assets(user.organization_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = create_asset(
            actor=request.user,
            data=serializer.validated_data,
            ip_address=_request_ip(request),
        )
        output = self.get_serializer(asset)
        return Response(
            output.data, status=HTTP_201_CREATED, headers=self.get_success_headers(output.data)
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        asset = self.get_object()
        serializer = self.get_serializer(asset, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_asset = update_asset(
            asset_id=asset.pk,
            actor=request.user,
            data=serializer.validated_data,
            ip_address=_request_ip(request),
        )
        return Response(self.get_serializer(updated_asset).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=("get",), url_path=r"by-tag/(?P<asset_tag>[^/.]+)")
    def by_tag(self, request, asset_tag=None):
        asset = get_object_or_404(self.filter_queryset(self.get_queryset()), asset_tag=asset_tag)
        self.check_object_permissions(request, asset)
        return Response(self.get_serializer(asset).data)


class AssetCategoryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = AssetCategorySerializer
    permission_classes = (AssetDomainPermission,)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("name", "code", "description")
    ordering_fields = ("name", "code", "default_useful_life_months", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or not user.organization_id:
            return AssetCategory.objects.none()
        return categories_for_organization(user.organization_id)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
