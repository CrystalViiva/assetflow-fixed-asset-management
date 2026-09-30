"""Publish one report snapshot dataset for every active organization."""

import json

from django.core.management.base import BaseCommand, CommandError

from analytics.contracts import SNAPSHOT_REPORT_TYPES
from analytics.services import extract_report_snapshot_dataset
from organizations.models import Organization


class Command(BaseCommand):
    help = "Extract completed report snapshots to versioned analytics JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--report-type", required=True, choices=SNAPSHOT_REPORT_TYPES)
        parser.add_argument("--run-key", required=True)
        parser.add_argument(
            "--full-refresh",
            action="store_true",
            help="Replay all completed snapshots and republish their stable logical record IDs.",
        )

    def handle(self, *args, **options):
        report_type = options["report_type"]
        run_key = options["run_key"]
        results = []
        for organization_id in Organization.objects.order_by("pk").values_list("pk", flat=True):
            try:
                publication = extract_report_snapshot_dataset(
                    organization_id=organization_id,
                    report_type=report_type,
                    run_key=run_key,
                    full_refresh=options["full_refresh"],
                )
            except Exception as exc:
                raise CommandError(
                    f"Analytics extraction failed for organization {organization_id} "
                    f"and dataset {report_type}."
                ) from exc
            results.append(
                {
                    "organization_id": str(organization_id),
                    "dataset": publication.dataset,
                    "run_id": publication.run_id,
                    "logical_run_id": publication.run.run_key,
                    "status": publication.run.status,
                    "contract_version": publication.contract_version,
                    "row_count": publication.row_count,
                    "source_watermark_at": (
                        publication.source_watermark_at.isoformat()
                        if publication.source_watermark_at
                        else None
                    ),
                    "source_watermark_snapshot_id": (
                        str(publication.source_watermark_snapshot_id)
                        if publication.source_watermark_snapshot_id
                        else None
                    ),
                    "source_watermark_ordinal": publication.source_watermark_ordinal,
                    "published_at": publication.published_at.isoformat(),
                    "finished_at": publication.run.finished_at.isoformat(),
                    "full_refresh": publication.run.full_refresh,
                    "sha256": publication.sha256,
                    "byte_size": publication.byte_size,
                }
            )
        self.stdout.write(json.dumps(results, sort_keys=True, separators=(",", ":")))
