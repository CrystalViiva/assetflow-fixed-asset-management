from rest_framework.routers import SimpleRouter

from disposals.views import DisposalViewSet

router = SimpleRouter()
router.register("assets/disposals", DisposalViewSet, basename="disposal")

urlpatterns = router.urls
