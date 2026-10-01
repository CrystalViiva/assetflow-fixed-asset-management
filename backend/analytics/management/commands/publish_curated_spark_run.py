"""Publish a fully verified tenant-scoped Spark output manifest."""

from django.core.management.base import BaseCommand, CommandError

from analytics.curated_processing import (
    CuratedProcessingError,
    fail_curated_run,
    publish_curated_run,
)


class Command(BaseCommand):
    help = "Publish verified M10.8 Parquet outputs or record a failed Spark attempt."

    def add_arguments(self, parser):
        parser.add_argument("--run-id", required=True, type=int)
        parser.add_argument("--attempt-token", required=True)
        parser.add_argument("--failed", action="store_true")

    def handle(self, *args, **options):
        try:
            if options["failed"]:
                fail_curated_run(run_id=options["run_id"], attempt_token=options["attempt_token"])
                self.stdout.write("failed")
                return
            publication = publish_curated_run(
                run_id=options["run_id"], attempt_token=options["attempt_token"]
            )
        except CuratedProcessingError as exc:
            raise CommandError("Could not publish curated analytics output.") from exc
        self.stdout.write(str(publication.pk))
