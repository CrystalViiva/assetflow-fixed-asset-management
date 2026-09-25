from rest_framework.routers import SimpleRouter

from depreciation.views import (
    AccountingPeriodViewSet,
    DepreciationEntryViewSet,
    DepreciationScheduleViewSet,
)

router = SimpleRouter(use_regex_path=False)
router.register(
    "depreciation/schedules", DepreciationScheduleViewSet, basename="depreciation-schedule"
)
router.register("depreciation/entries", DepreciationEntryViewSet, basename="depreciation-entry")
router.register("depreciation/periods", AccountingPeriodViewSet, basename="accounting-period")

urlpatterns = router.urls
