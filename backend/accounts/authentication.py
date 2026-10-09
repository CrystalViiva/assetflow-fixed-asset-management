"""JWT authentication that enforces organization suspension on every API request."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class OrganizationJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            from commercial.entitlements import enforce_request

            enforce_request(result[0], request)
        return result

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get("session_version", 0) != getattr(user, "session_version", 0):
            raise AuthenticationFailed("This session has ended. Sign in again.")
        organization_id = user.organization_id
        if organization_id:
            if not user.organization.is_active:
                raise AuthenticationFailed("This organization is currently unavailable.")
        return user
