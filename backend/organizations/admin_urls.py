from django.urls import path

from organizations.admin_api import (
    DepartmentAdminDetail,
    DepartmentAdminList,
    LocationAdminDetail,
    LocationAdminList,
)

urlpatterns = [
    path("admin/departments/", DepartmentAdminList.as_view(), name="admin-department-list"),
    path(
        "admin/departments/<uuid:id>/",
        DepartmentAdminDetail.as_view(),
        name="admin-department-detail",
    ),
    path("admin/locations/", LocationAdminList.as_view(), name="admin-location-list"),
    path("admin/locations/<uuid:id>/", LocationAdminDetail.as_view(), name="admin-location-detail"),
]
