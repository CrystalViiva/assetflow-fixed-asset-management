from rest_framework.routers import SimpleRouter

from transfers.views import AssignmentViewSet, TransferViewSet

router = SimpleRouter()
router.register("assets/assignments", AssignmentViewSet, basename="asset-assignment")
router.register("assets/transfers", TransferViewSet, basename="asset-transfer")

urlpatterns = router.urls
