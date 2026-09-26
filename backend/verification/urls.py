from rest_framework.routers import SimpleRouter

from verification.views import (
    CampaignViewSet,
    PhysicalVerificationViewSet,
    VerificationEvidenceViewSet,
    VerificationExceptionViewSet,
)

router = SimpleRouter()
router.register("verification/campaigns", CampaignViewSet, basename="verification-campaign")
router.register("verification/records", PhysicalVerificationViewSet, basename="verification-record")
router.register(
    "verification/exceptions", VerificationExceptionViewSet, basename="verification-exception"
)
router.register(
    "verification/evidence", VerificationEvidenceViewSet, basename="verification-evidence"
)

urlpatterns = router.urls
