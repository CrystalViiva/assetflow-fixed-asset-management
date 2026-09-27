from django.urls import include, path
from rest_framework.routers import SimpleRouter

from assurance.views import AssuranceFindingViewSet, AssuranceRunViewSet, AssuranceSummaryView

router = SimpleRouter()
router.register("assurance/runs", AssuranceRunViewSet, basename="assurance-run")
router.register("assurance/findings", AssuranceFindingViewSet, basename="assurance-finding")

urlpatterns = [
    path("assurance/summary/", AssuranceSummaryView.as_view(), name="assurance-summary"),
    path("", include(router.urls)),
]
