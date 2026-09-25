from rest_framework.routers import SimpleRouter

from maintenance.views import (
    MaintenanceCostViewSet,
    MaintenancePlanViewSet,
    MaintenanceRecordViewSet,
    WorkOrderViewSet,
)

router = SimpleRouter()
router.register("assets/maintenance-plans", MaintenancePlanViewSet, basename="maintenance-plan")
router.register("assets/work-orders", WorkOrderViewSet, basename="work-order")
router.register("assets/maintenance-costs", MaintenanceCostViewSet, basename="maintenance-cost")
router.register(
    "assets/maintenance-records", MaintenanceRecordViewSet, basename="maintenance-record"
)

urlpatterns = router.urls
