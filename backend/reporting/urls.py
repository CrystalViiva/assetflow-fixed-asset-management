from django.urls import path

from reporting.views import (
    LiveReportView,
    ReportCatalogView,
    ReportExportDetailView,
    ReportExportDownloadView,
    ReportExportListCreateView,
    ReportSnapshotDetailView,
    ReportSnapshotListCreateView,
    ReportSnapshotRowsView,
)

urlpatterns = [
    path("reports/", ReportCatalogView.as_view(), name="report-catalog"),
    path("reports/<str:report_type>/", LiveReportView.as_view(), name="live-report"),
    path("report-snapshots/", ReportSnapshotListCreateView.as_view(), name="report-snapshot-list"),
    path("report-exports/", ReportExportListCreateView.as_view(), name="report-export-list"),
    path(
        "report-exports/<uuid:export_id>/",
        ReportExportDetailView.as_view(),
        name="report-export-detail",
    ),
    path(
        "report-exports/<uuid:export_id>/download/",
        ReportExportDownloadView.as_view(),
        name="report-export-download",
    ),
    path(
        "report-snapshots/<uuid:snapshot_id>/",
        ReportSnapshotDetailView.as_view(),
        name="report-snapshot-detail",
    ),
    path(
        "report-snapshots/<uuid:snapshot_id>/rows/",
        ReportSnapshotRowsView.as_view(),
        name="report-snapshot-rows",
    ),
]
