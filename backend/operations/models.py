from django.db import models


class WorkerPulse(models.Model):
    name = models.CharField(max_length=40, primary_key=True)
    seen_at = models.DateTimeField()


class TaskFailure(models.Model):
    task_id = models.CharField(max_length=128, unique=True)
    task_name = models.CharField(max_length=240)
    error_type = models.CharField(max_length=100)
    occurred_at = models.DateTimeField(auto_now_add=True)
