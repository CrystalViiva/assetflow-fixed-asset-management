"""Claim M10.8 tenant runs and stage Spark's small input manifests."""

import json

from django.core.management.base import BaseCommand, CommandError

from analytics.curated_processing import CuratedProcessingError, prepare_curated_runs


class Command(BaseCommand):
    help = "Prepare fenced, organization-scoped PySpark processing runs."

    def handle(self, *args, **options):
        try:
            results = prepare_curated_runs()
        except CuratedProcessingError as exc:
            raise CommandError("Could not prepare curated analytics processing.") from exc
        self.stdout.write(json.dumps(results, sort_keys=True, separators=(",", ":")))
