"""OpenAPI schema for the organization-aware JWT authenticator."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class OrganizationJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.OrganizationJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
