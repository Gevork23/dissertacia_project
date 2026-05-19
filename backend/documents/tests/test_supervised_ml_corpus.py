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
from documents.services import supervised_ml_corpus


def _write_significance_seed(path: Path) -> None:
    rows = [
        {
            "pair_id": "seed-1",
            "change_id": "chg-1",
            "operation": "modified",
            "semantic_type": "deadline_change",
            "expected_importance": "critical",
            "old_text": "Срок составляет 10 рабочих дней.",
            "new_text": "Срок составляет 5 рабочих дней.",
            "description": "Сокращение срока.",
        },
        {
            "pair_id": "seed-2",
            "change_id": "chg-1",
            "operation": "modified",
            "semantic_type": "procedure_change",
            "expected_importance": "important",
            "old_text": "Заявление подается на бумаге.",
            "new_text": "Заявление подается через портал.",
            "description": "Изменен способ подачи.",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_evaluation_corpus(directory: Path) -> None:
    pair_dir = directory / "pair_eval_01"
    pair_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pair_id": "pair_eval_01",
        "expected_changes": [
            {
                "id": "chg-1",
                "type": "modified",
                "old_text": "Сотрудник осуществляет проверку документов.",
                "new_text": "Сотрудник выполняет проверку документов.",
                "importance": "editorial",
                "semantic_type": "terminology_change",
                "description": "Редакционная замена глагола.",
            },
            {
                "id": "chg-2",
                "type": "added",
                "old_text": "",
                "new_text": "Справочная информация доступна на портале.",
                "importance": "informational",
                "semantic_type": "contact_or_channel_change",
                "description": "Добавлено справочное указание.",
            },
        ],
    }
    (pair_dir / "annotation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_real_world_trace(path: Path) -> None:
    rows = [
        {
            "pair_id": "weak-1",
            "change_index": 1,
            "operation_type": "modified",
            "semantic_type": "deadline_change",
            "significance_label": "critical",
            "requires_manual_review": "False",
            "old_preview": "Срок составляет 12 дней.",
            "new_preview": "Срок составляет 7 дней.",
            "explanation": "Weak real-world example.",
            "warning": "",
        }
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class SupervisedMlCorpusTests(SimpleTestCase):
    def test_builder_creates_dataset_split_and_figures(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            output_dir = temp_dir / "ml_corpus"
            significance_path = temp_dir / "significance_results.csv"
            evaluation_dir = temp_dir / "evaluation_corpus"
            trace_path = temp_dir / "real_world_trace.csv"
            _write_significance_seed(significance_path)
            _write_evaluation_corpus(evaluation_dir)
            _write_real_world_trace(trace_path)

            with mock.patch(
                "documents.services.supervised_ml_corpus.collect_annotation_examples_from_db",
                return_value=([], []),
            ), mock.patch(
                "documents.services.supervised_ml_corpus.collect_annotation_examples_from_exports",
                return_value=([], []),
            ):
                profile = supervised_ml_corpus.build_supervised_ml_corpus(
                    output_dir=output_dir,
                    significance_results_path=significance_path,
                    evaluation_corpus_dir=evaluation_dir,
                    real_world_trace_path=trace_path,
                )

            full_df = supervised_ml_corpus.pd.read_csv(output_dir / "full_dataset.csv")
            train_df = supervised_ml_corpus.pd.read_csv(output_dir / "train.csv")
            test_df = supervised_ml_corpus.pd.read_csv(output_dir / "test.csv")
            profile_exists = (output_dir / "dataset_profile.json").exists()
            split_exists = (output_dir / "split_metadata.json").exists()
            figure_exists = (output_dir / "figures" / "label_distribution.png").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertGreaterEqual(profile["total_examples"], 100)
        self.assertFalse(full_df["y_significance"].isna().any())
        self.assertTrue(set(["critical", "important", "informational", "editorial"]).issubset(set(full_df["y_significance"].unique())))
        self.assertFalse(train_df["is_weak"].any())
        self.assertFalse(test_df["is_weak"].any())
        self.assertTrue(profile_exists)
        self.assertTrue(split_exists)
        self.assertTrue(figure_exists)

    def test_baseline_training_creates_outputs(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            output_dir = temp_dir / "ml_corpus"
            significance_path = temp_dir / "significance_results.csv"
            evaluation_dir = temp_dir / "evaluation_corpus"
            trace_path = temp_dir / "real_world_trace.csv"
            _write_significance_seed(significance_path)
            _write_evaluation_corpus(evaluation_dir)
            _write_real_world_trace(trace_path)

            with mock.patch(
                "documents.services.supervised_ml_corpus.collect_annotation_examples_from_db",
                return_value=([], []),
            ), mock.patch(
                "documents.services.supervised_ml_corpus.collect_annotation_examples_from_exports",
                return_value=([], []),
            ):
                supervised_ml_corpus.build_supervised_ml_corpus(
                    output_dir=output_dir,
                    significance_results_path=significance_path,
                    evaluation_corpus_dir=evaluation_dir,
                    real_world_trace_path=trace_path,
                )
                summary = supervised_ml_corpus.train_baseline_ml_models(corpus_dir=output_dir)
                results_exists = (output_dir / "baseline_model_results.csv").exists()
                confusion_exists = (output_dir / "baseline_confusion_matrix.csv").exists()
                features_exists = (output_dir / "baseline_feature_importance.csv").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertGreater(summary["train_size"], 0)
        self.assertTrue(results_exists)
        self.assertTrue(confusion_exists)
        self.assertTrue(features_exists)


class SupervisedMlCorpusCommandTests(TestCase):
    def test_management_commands_are_available(self):
        fake_profile = {
            "total_examples": 160,
            "split": {"train_size": 128, "test_size": 32, "validation_size": 16},
        }
        fake_summary = {
            "train_size": 128,
            "test_size": 32,
            "output_files": {"results": "experiments/ml_corpus/baseline_model_results.csv"},
        }
        with mock.patch(
            "documents.management.commands.build_supervised_ml_corpus.build_supervised_ml_corpus",
            return_value=fake_profile,
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command("build_supervised_ml_corpus", stdout=stdout)
                stdout.seek(0)
                output = stdout.read()
            self.assertIn("Supervised ML corpus built", output)

        with mock.patch(
            "documents.management.commands.train_baseline_ml_models.train_baseline_ml_models",
            return_value=fake_summary,
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command("train_baseline_ml_models", stdout=stdout)
                stdout.seek(0)
                output = stdout.read()
            self.assertIn("Baseline ML models trained", output)


class SupervisedMlCorpusDashboardTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.client.force_login(self.admin_user)

    def test_collect_supervised_ml_corpus_reads_artifacts(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            figures_dir = temp_dir / "figures"
            figures_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "dataset_profile.json").write_text(
                json.dumps(
                    {
                        "total_examples": 160,
                        "strict_examples": 120,
                        "weak_examples": 40,
                        "label_distribution": {"critical": 40},
                        "semantic_type_distribution": {"deadline_change": 20},
                        "source_proportions": {"gold": 0.2, "synthetic": 0.7, "weak": 0.1},
                        "warnings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (temp_dir / "split_metadata.json").write_text(
                json.dumps({"train_size": 96, "test_size": 24, "validation_size": 12}, ensure_ascii=False),
                encoding="utf-8",
            )
            (temp_dir / "feature_schema.json").write_text(
                json.dumps({"target_columns": {"y_significance": ["critical"]}}, ensure_ascii=False),
                encoding="utf-8",
            )
            for name in ("full_dataset.csv", "train.csv", "test.csv", "weak_inference_dataset.csv", "label_distribution.csv"):
                (temp_dir / name).write_text("col1,col2\nx,y\n", encoding="utf-8")
            (temp_dir / "dataset_quality_report.md").write_text("# Report\n\nPreview\n", encoding="utf-8")
            (figures_dir / "label_distribution.png").write_bytes(b"fake-png")

            with mock.patch.object(research_dashboard, "ML_CORPUS_DIR", temp_dir):
                result = research_dashboard.collect_supervised_ml_corpus()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["total_examples"], 160)
        self.assertEqual(len(result["figures"]["items"]), 1)

    def test_research_dashboard_shows_supervised_ml_block(self):
        temp_root = Path(tempfile.mkdtemp())
        try:
            ml_dir = temp_root / "experiments" / "ml_corpus"
            final_dir = temp_root / "experiments" / "final"
            visuals = temp_root / "experiments" / "final_visuals"
            figures = visuals / "figures"
            tables = visuals / "tables"
            docs_dir = temp_root / "docs" / "experiments"
            real_world_dir = temp_root / "experiments" / "real_world"
            significance_ml_dir = temp_root / "experiments" / "significance_ml"
            for path in (ml_dir, final_dir, figures, tables, docs_dir, real_world_dir, significance_ml_dir):
                path.mkdir(parents=True, exist_ok=True)
            (ml_dir / "dataset_profile.json").write_text(
                json.dumps(
                    {
                        "total_examples": 160,
                        "strict_examples": 120,
                        "weak_examples": 40,
                        "label_distribution": {"critical": 40},
                        "semantic_type_distribution": {"deadline_change": 20},
                        "source_proportions": {"gold": 0.2, "synthetic": 0.7, "weak": 0.1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (ml_dir / "split_metadata.json").write_text(
                json.dumps({"train_size": 96, "test_size": 24, "validation_size": 12}, ensure_ascii=False),
                encoding="utf-8",
            )
            (ml_dir / "feature_schema.json").write_text("{}", encoding="utf-8")
            for name in ("full_dataset.csv", "train.csv", "test.csv", "weak_inference_dataset.csv", "label_distribution.csv"):
                (ml_dir / name).write_text("col1,col2\nx,y\n", encoding="utf-8")
            (ml_dir / "dataset_quality_report.md").write_text("# Report\n\nPreview\n", encoding="utf-8")
            (ml_dir / "figures").mkdir(exist_ok=True)
            (ml_dir / "figures" / "label_distribution.png").write_bytes(b"fake-png")

            with mock.patch.multiple(
                research_dashboard,
                PROJECT_ROOT=temp_root,
                FINAL_DIR=final_dir,
                FINAL_VISUALS_DIR=visuals,
                FINAL_FIGURES_DIR=figures,
                FINAL_TABLES_DIR=tables,
                REAL_WORLD_DIR=real_world_dir,
                SIGNIFICANCE_ML_DIR=significance_ml_dir,
                ML_CORPUS_DIR=ml_dir,
                DOCS_EXPERIMENTS_DIR=docs_dir,
                ARTIFACT_ROOTS=(final_dir, figures, tables, real_world_dir, significance_ml_dir, ml_dir, docs_dir),
            ):
                response = self.client.get(reverse("demo-research-dashboard"))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Supervised ML corpus")
