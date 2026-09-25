from rest_framework import serializers

from accounts.models import User


class AuthenticatedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role")
        read_only_fields = fields
