"""Minimal cleanup for uploads abandoned during synchronous evidence handling."""

from datetime import timedelta

from celery import shared_task

from verification.services import cleanup_stale_evidence_uploads


@shared_task
def clean_stale_evidence_uploads():
    return cleanup_stale_evidence_uploads(older_than=timedelta(minutes=30))
