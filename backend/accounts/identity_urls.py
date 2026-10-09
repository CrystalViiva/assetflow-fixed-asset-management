from django.urls import path

from accounts import identity_api as api

urlpatterns = [
    path("auth/password-reset/", api.ResetRequest.as_view()),
    path("auth/password-reset/complete/", api.ResetComplete.as_view()),
    path("auth/invitations/accept/", api.InvitationComplete.as_view()),
    path("auth/password-change/", api.PasswordChange.as_view()),
    path("auth/logout/", api.LogoutView.as_view()),
    path("auth/profile/", api.ProfileView.as_view()),
    path("admin/organization/", api.OrganizationProfile.as_view()),
    path("admin/invitations/", api.InvitationList.as_view()),
    path("admin/invitations/<uuid:pk>/revoke/", api.InvitationRevoke.as_view()),
    path("platform/provision/", api.ProvisionView.as_view()),
]
