from django.urls import path

from accounts.admin_api import UserAdminDetail, UserAdminList

urlpatterns = [
    path("admin/users/", UserAdminList.as_view(), name="admin-user-list"),
    path("admin/users/<int:id>/", UserAdminDetail.as_view(), name="admin-user-detail"),
]
