"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.serializers import AuthenticatedUserSerializer
from audit.api import AuditEventListView
from config.views import health_check
from organizations.api import CustodianReferenceList, DepartmentReferenceList, LocationReferenceList


class AuthenticatedUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AuthenticatedUserSerializer)
    def get(self, request):
        return Response(AuthenticatedUserSerializer(request.user).data)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/audit/events/", AuditEventListView.as_view(), name="audit-event-list"),
    # Specific nested routes must precede the assets router's catch-all detail route.
    path("api/v1/", include("transfers.urls")),
    path("api/v1/", include("accounts.admin_urls")),
    path("api/v1/", include("organizations.admin_urls")),
    path("api/v1/", include("maintenance.urls")),
    path("api/v1/", include("disposals.urls")),
    path("api/v1/", include("verification.urls")),
    path("api/v1/", include("assurance.urls")),
    path("api/v1/", include("reporting.urls")),
    path("api/v1/", include("assets.urls")),
    path("api/v1/", include("depreciation.urls")),
    path("api/v1/departments/", DepartmentReferenceList.as_view(), name="department-list"),
    path("api/v1/locations/", LocationReferenceList.as_view(), name="location-list"),
    path("api/v1/custodians/", CustodianReferenceList.as_view(), name="custodian-list"),
    path("api/v1/health/", health_check, name="health-check"),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/v1/auth/me/", AuthenticatedUserView.as_view(), name="authenticated-user"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
