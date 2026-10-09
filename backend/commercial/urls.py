from django.urls import path

from commercial import api

urlpatterns = [
    path("public/config/", api.PublicConfig.as_view()),
    path("public/leads/", api.LeadCapture.as_view()),
    path("auth/signup/", api.SignupView.as_view()),
    path("auth/signup/verify/", api.VerifySignup.as_view()),
    path("billing/", api.BillingOverview.as_view()),
    path("billing/checkout/", api.CheckoutView.as_view()),
    path("billing/checkout/<uuid:pk>/simulate/", api.SandboxPayment.as_view()),
    path("billing/cancel/", api.CancelSubscription.as_view()),
    path("billing/webhook/", api.BillingWebhook.as_view()),
    path("platform/tenants/", api.PlatformOverview.as_view()),
    path("platform/tenants/<uuid:pk>/state/", api.TenantState.as_view()),
    path("platform/tenants/<uuid:pk>/invitation/", api.ResendManagedInvitation.as_view()),
    path("platform/leads/", api.SalesInbox.as_view()),
]
