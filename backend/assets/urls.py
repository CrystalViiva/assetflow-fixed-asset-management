from rest_framework.routers import SimpleRouter

from assets.views import AcquisitionViewSet, AssetCategoryViewSet, AssetViewSet

router = SimpleRouter()
router.register("assets/categories", AssetCategoryViewSet, basename="asset-category")
router.register("assets/acquisitions", AcquisitionViewSet, basename="acquisition")
router.register("assets", AssetViewSet, basename="asset")

urlpatterns = router.urls
