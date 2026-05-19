import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from documents import research_dashboard


class ResearchDashboardHelpersTests(TestCase):
    def test_safe_read_json_returns_missing_for_absent_file(self):
        result = research_dashboard.safe_read_json(Path("Z:/missing/file.json"))

        self.assertFalse(result["available"])
        self.assertIn("missing", result["warning"])

    def test_safe_read_csv_preview_returns_missing_for_absent_file(self):
        result = research_dashboard.safe_read_csv_preview(Path("Z:/missing/file.csv"))

        self.assertFalse(result["available"])
        self.assertEqual(result["headers"], [])
        self.assertEqual(result["rows"], [])

    def test_collect_final_metrics_reads_existing_summary(self):
        result = research_dashboard.collect_final_metrics()

        self.assertEqual(result["status"], "available")
        self.assertTrue(result["metrics"])

    def test_collect_figure_artifacts_collects_png_from_directory(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "stage_view.png").write_bytes(b"fake-png")
            with mock.patch.object(research_dashboard, "FINAL_FIGURES_DIR", temp_dir):
                result = research_dashboard.collect_figure_artifacts()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(result["status"], "available")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["title"], "Stage View")


class ResearchDashboardViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.client.force_login(self.admin_user)

    def test_research_dashboard_page_returns_200(self):
        response = self.client.get(reverse("demo-research-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research Dashboard")

    def test_research_dashboard_handles_missing_optional_artifacts(self):
        temp_root = Path(tempfile.mkdtemp())
        try:
            temp_final = temp_root / "experiments" / "final"
            temp_visuals = temp_root / "experiments" / "final_visuals"
            temp_figures = temp_visuals / "figures"
            temp_tables = temp_visuals / "tables"
            temp_docs = temp_root / "docs" / "experiments"
            for path in (temp_final, temp_figures, temp_tables, temp_docs):
                path.mkdir(parents=True, exist_ok=True)

            with mock.patch.multiple(
                research_dashboard,
                PROJECT_ROOT=temp_root,
                FINAL_DIR=temp_final,
                FINAL_VISUALS_DIR=temp_visuals,
                FINAL_FIGURES_DIR=temp_figures,
                FINAL_TABLES_DIR=temp_tables,
                DOCS_EXPERIMENTS_DIR=temp_docs,
                ARTIFACT_ROOTS=(temp_final, temp_figures, temp_tables, temp_docs),
            ):
                response = self.client.get(reverse("demo-research-dashboard"))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "artifact missing / not available")
