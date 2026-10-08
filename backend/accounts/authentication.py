"""JWT authentication that enforces organization suspension on every API request."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class OrganizationJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        organization_id = user.organization_id
        if organization_id and not user.is_superuser:
            if not user.organization.is_active:
                raise AuthenticationFailed("This organization is currently unavailable.")
        return user
