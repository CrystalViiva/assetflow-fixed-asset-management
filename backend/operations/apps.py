from django.apps import AppConfig


class OperationsConfig(AppConfig):
    name = "operations"

    def ready(self):
        from operations import signals  # noqa: F401
