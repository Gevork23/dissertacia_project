from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from documents import research_dashboard
from documents.services import research_regression


class RealWorldRegressionDiscoveryTests(SimpleTestCase):
    def test_discover_regression_pairs_prefers_ruslawod_cases(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            old_file = temp_dir / "old.txt"
            new_file = temp_dir / "new.txt"
            old_file.write_text("Старая редакция\n", encoding="utf-8")
            new_file.write_text("Новая редакция\n", encoding="utf-8")
            cases_path = temp_dir / "ruslawod_test_cases.json"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "pair-1",
                            "name": "Weak pair",
                            "v1_path": str(old_file),
                            "v2_path": str(new_file),
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            pairs, source, warnings = research_regression.discover_regression_pairs(
                ruslawod_cases_path=cases_path,
                demo_corpus_dir=temp_dir / "missing-demo",
                manual_fallback_dir=temp_dir / "missing-manual",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(source, "ruslawod_weak_regression")
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].pair_id, "pair-1")
        self.assertEqual(warnings, [])


class RealWorldRegressionExecutionTests(TestCase):
    def test_run_real_world_regression_suite_writes_outputs(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            old_file = temp_dir / "old.txt"
            new_file = temp_dir / "new.txt"
            old_file.write_text(
                "Статья 1. Срок рассмотрения составляет 10 рабочих дней.\n",
                encoding="utf-8",
            )
            new_file.write_text(
                "Статья 1. Срок рассмотрения составляет 5 рабочих дней.\n",
                encoding="utf-8",
            )
            cases_path = temp_dir / "ruslawod_test_cases.json"
            cases_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "pair-1",
                            "name": "Weak pair",
                            "v1_path": str(old_file),
                            "v2_path": str(new_file),
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output_dir = temp_dir / "outputs"

            summary = research_regression.run_real_world_regression_suite(
                output_dir=output_dir,
                ruslawod_cases_path=cases_path,
                demo_corpus_dir=temp_dir / "missing-demo",
                manual_fallback_dir=temp_dir / "missing-manual",
            )

            summary_path = output_dir / "real_world_summary.json"
            pair_results_path = output_dir / "real_world_pair_results.csv"
            trace_path = output_dir / "real_world_trace.csv"
            stage_summary_path = output_dir / "real_world_stage_summary.csv"
        finally:
            if temp_dir.exists():
                persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                with pair_results_path.open("r", encoding="utf-8", newline="") as handle:
                    pair_rows = list(csv.DictReader(handle))
                shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(summary["total_pairs"], 1)
        self.assertEqual(summary["processed_pairs"], 1)
        self.assertIn("metrics", summary)
        self.assertEqual(persisted_summary["metrics"]["total_pairs"], 1)
        self.assertTrue(pair_results_path.name.endswith(".csv"))
        self.assertTrue(trace_path.name.endswith(".csv"))
        self.assertTrue(stage_summary_path.name.endswith(".csv"))
        self.assertEqual(len(pair_rows), 1)

    def test_run_real_world_regression_command_outputs_summary(self):
        fake_summary = {
            "corpus_source": "ruslawod_weak_regression",
            "processed_pairs": 2,
            "total_pairs": 2,
            "failed_pairs": 0,
            "output_files": {"summary": "experiments/real_world/real_world_summary.json"},
            "metrics": {
                "total_changes": 11,
                "pipeline_success_rate": 1.0,
                "significant_change_rate": 0.5,
            },
        }
        with mock.patch(
            "documents.management.commands.run_real_world_regression.run_real_world_regression_suite",
            return_value=fake_summary,
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command("run_real_world_regression", stdout=stdout)
                stdout.seek(0)
                output = stdout.read()

        self.assertIn("Real-world regression suite completed", output)
        self.assertIn("Processed pairs: 2/2", output)


class RealWorldRegressionDashboardTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.client.force_login(self.admin_user)

    def test_collect_real_world_regression_reads_existing_summary(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "real_world_summary.json").write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_pairs": 3,
                            "processed_pairs": 3,
                            "failed_pairs": 0,
                            "total_changes": 12,
                            "pipeline_success_rate": 1.0,
                            "significant_change_rate": 0.75,
                        },
                        "limitations": ["Weak labels only."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (temp_dir / "real_world_pair_results.csv").write_text(
                "pair_id,status\npair-1,ok\n",
                encoding="utf-8",
            )
            (temp_dir / "real_world_stage_summary.csv").write_text(
                "stage,status\nchunking,available\n",
                encoding="utf-8",
            )
            (temp_dir / "real_world_trace.csv").write_text(
                "pair_id,change_index\npair-1,1\n",
                encoding="utf-8",
            )

            with mock.patch.object(research_dashboard, "REAL_WORLD_DIR", temp_dir):
                result = research_dashboard.collect_real_world_regression()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["metrics"]["total_pairs"], 3)

    def test_research_dashboard_shows_real_world_block_when_artifacts_exist(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "real_world_summary.json").write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_pairs": 2,
                            "processed_pairs": 2,
                            "failed_pairs": 0,
                            "total_changes": 4,
                            "pipeline_success_rate": 1.0,
                            "significant_change_rate": 0.5,
                        },
                        "limitations": ["Weak labels only."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (temp_dir / "real_world_pair_results.csv").write_text(
                "pair_id,status\npair-1,ok\n",
                encoding="utf-8",
            )
            (temp_dir / "real_world_stage_summary.csv").write_text(
                "stage,status\nchunking,available\n",
                encoding="utf-8",
            )
            (temp_dir / "real_world_trace.csv").write_text(
                "pair_id,change_index\npair-1,1\n",
                encoding="utf-8",
            )

            roots = (
                research_dashboard.FINAL_DIR,
                research_dashboard.FINAL_FIGURES_DIR,
                research_dashboard.FINAL_TABLES_DIR,
                temp_dir,
                research_dashboard.DOCS_EXPERIMENTS_DIR,
            )
            with mock.patch.multiple(
                research_dashboard,
                REAL_WORLD_DIR=temp_dir,
                ARTIFACT_ROOTS=roots,
            ):
                response = self.client.get(reverse("demo-research-dashboard"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Real-world regression suite")
        self.assertContains(response, "2")
