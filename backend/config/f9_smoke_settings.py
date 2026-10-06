"""Isolated F9 settings: eager tasks and private export storage outside the repository."""

import os

from .settings import *  # noqa: F403

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
ASSETFLOW_PRIVATE_STORAGE_OPTIONS = {"location": os.environ["F9_SMOKE_PRIVATE_ROOT"]}
STORAGES["assetflow_private"] = {  # noqa: F405
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": ASSETFLOW_PRIVATE_STORAGE_OPTIONS,
}
