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
from documents.services import significance_ml_experiment


def _write_dataset_csv(path: Path) -> None:
    rows = [
        {
            "pair_id": "pair-1",
            "change_id": "chg-1",
            "operation": "modified",
            "change_type": "deadline_change",
            "semantic_type": "deadline",
            "predicted_semantic_type": "deadline",
            "expected_importance": "critical",
            "predicted_importance": "critical",
            "old_text": "Срок составляет 10 рабочих дней.",
            "new_text": "Срок составляет 5 рабочих дней.",
            "description": "Срок сокращен.",
            "notes": "",
            "requires_manual_review": "False",
        },
        {
            "pair_id": "pair-2",
            "change_id": "chg-1",
            "operation": "added",
            "change_type": "added_obligation",
            "semantic_type": "obligation",
            "predicted_semantic_type": "obligation",
            "expected_importance": "critical",
            "predicted_importance": "critical",
            "old_text": "",
            "new_text": "Сотрудник обязан уведомить заявителя.",
            "description": "Новая обязанность.",
            "notes": "",
            "requires_manual_review": "False",
        },
        {
            "pair_id": "pair-3",
            "change_id": "chg-1",
            "operation": "modified",
            "change_type": "procedure_change",
            "semantic_type": "procedure",
            "predicted_semantic_type": "procedure",
            "expected_importance": "important",
            "predicted_importance": "important",
            "old_text": "Заявление подается на бумаге.",
            "new_text": "Заявление можно подать через портал.",
            "description": "Изменен канал подачи.",
            "notes": "",
            "requires_manual_review": "True",
        },
        {
            "pair_id": "pair-4",
            "change_id": "chg-1",
            "operation": "added",
            "change_type": "informational_change",
            "semantic_type": "informational",
            "predicted_semantic_type": "informational",
            "expected_importance": "informational",
            "predicted_importance": "important",
            "old_text": "",
            "new_text": "Справочная информация доступна на портале.",
            "description": "Добавлено справочное указание.",
            "notes": "",
            "requires_manual_review": "True",
        },
        {
            "pair_id": "pair-5",
            "change_id": "chg-1",
            "operation": "modified",
            "change_type": "editorial_wording",
            "semantic_type": "editorial",
            "predicted_semantic_type": "editorial",
            "expected_importance": "editorial",
            "predicted_importance": "important",
            "old_text": "Сотрудник осуществляет проверку документов.",
            "new_text": "Сотрудник выполняет проверку документов.",
            "description": "Редакционная правка.",
            "notes": "",
            "requires_manual_review": "True",
        },
        {
            "pair_id": "pair-6",
            "change_id": "chg-1",
            "operation": "moved",
            "change_type": "structure_reorder",
            "semantic_type": "structure",
            "predicted_semantic_type": "editorial",
            "expected_importance": "editorial",
            "predicted_importance": "editorial",
            "old_text": "Контроль проводится до регистрации.",
            "new_text": "Контроль проводится до регистрации.",
            "description": "Перенос без изменения содержания.",
            "notes": "",
            "requires_manual_review": "False",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class SignificanceMlHelpersTests(SimpleTestCase):
    def test_collect_significance_dataset_reads_rows(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            dataset_path = temp_dir / "significance_results.csv"
            _write_dataset_csv(dataset_path)
            examples, metadata = significance_ml_experiment.collect_significance_dataset(
                dataset_path
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(len(examples), 6)
        self.assertEqual(metadata["label_distribution"]["critical"], 2)

    def test_extract_ml_features_handles_empty_texts(self):
        example = significance_ml_experiment.SignificanceExample(
            example_id="e1",
            pair_id="p1",
            change_id="c1",
            true_label="editorial",
            rule_based_label="editorial",
            operation="modified",
            change_type="editorial_wording",
            semantic_type="editorial",
            predicted_semantic_type="editorial",
            old_text="",
            new_text="",
            description="",
            notes="",
            requires_manual_review=False,
            source="fixture.csv",
        )

        features = significance_ml_experiment.extract_ml_features(example)

        self.assertIn("old_length", features)
        self.assertEqual(features["old_length"], 0.0)
        self.assertEqual(significance_ml_experiment.map_high_priority("critical"), 1)
        self.assertEqual(significance_ml_experiment.map_high_priority("editorial"), 0)


class SignificanceMlExecutionTests(TestCase):
    def test_run_significance_ml_experiment_writes_outputs(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            dataset_path = temp_dir / "significance_results.csv"
            output_dir = temp_dir / "outputs"
            supervised_dir = temp_dir / "missing_supervised_corpus"
            _write_dataset_csv(dataset_path)

            summary = significance_ml_experiment.run_significance_ml_experiment(
                dataset_csv_path=dataset_path,
                output_dir=output_dir,
                supervised_corpus_dir=supervised_dir,
            )

            summary_path = output_dir / "significance_ml_summary.json"
            predictions_path = output_dir / "significance_ml_predictions.csv"
            confusion_path = output_dir / "significance_ml_confusion_matrix.csv"
            persisted = json.loads(summary_path.read_text(encoding="utf-8"))
            predictions_exists = predictions_path.exists()
            confusion_exists = confusion_path.exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(summary["total_examples"], 6)
        self.assertEqual(persisted["total_examples"], 6)
        self.assertTrue(predictions_exists)
        self.assertTrue(confusion_exists)

    def test_management_command_is_available(self):
        fake_summary = {
            "dataset_source": "experiments/significance/significance_results.csv",
            "total_examples": 6,
            "models_evaluated": [
                "rule_based_baseline",
                "ml_text_model",
                "hybrid_model",
            ],
            "binary_high_priority_metrics": {
                "rule_based_baseline": {"high_priority_recall": 1.0}
            },
            "ml_metrics": {"macro_f1": 0.5},
            "hybrid_metrics": {"macro_f1": 0.6},
            "output_files": {
                "summary": "experiments/significance_ml/significance_ml_summary.json"
            },
        }
        with mock.patch(
            "documents.management.commands.run_significance_ml_experiment.run_significance_ml_experiment",
            return_value=fake_summary,
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command("run_significance_ml_experiment", stdout=stdout)
                stdout.seek(0)
                output = stdout.read()

        self.assertIn("ML / Hybrid significance experiment completed", output)
        self.assertIn("Total examples: 6", output)


class SignificanceMlDashboardTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.client.force_login(self.admin_user)

    def test_collect_significance_ml_experiment_reads_artifacts(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "significance_ml_summary.json").write_text(
                json.dumps(
                    {
                        "total_examples": 6,
                        "models_evaluated": ["rule_based_baseline", "ml_text_model"],
                        "label_distribution": {"critical": 2},
                        "rule_based_metrics": {"accuracy": 0.7},
                        "ml_metrics": {"macro_f1": 0.5},
                        "hybrid_metrics": {"macro_f1": 0.6},
                        "binary_high_priority_metrics": {
                            "hybrid_model": {"important_critical_miss_count": 0}
                        },
                        "disagreement_count": 2,
                        "limitations": ["Small corpus."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_predictions.csv").write_text(
                "example_id,true_label\nex-1,critical\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_confusion_matrix.csv").write_text(
                "model,true_label,predicted_label,count\nml_text_model,critical,critical,1\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_feature_report.csv").write_text(
                "model,class_label,rank,feature_name,feature_type,coefficient\nml_text_model,critical,1,tfidf:срок,tfidf,0.5\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_error_examples.csv").write_text(
                "example_id,error_type\nex-1,rule_ml_disagreement\n",
                encoding="utf-8",
            )

            with mock.patch.object(research_dashboard, "SIGNIFICANCE_ML_DIR", temp_dir):
                result = research_dashboard.collect_significance_ml_experiment()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["total_examples"], 6)

    def test_research_dashboard_shows_ml_block_when_artifacts_exist(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            (temp_dir / "significance_ml_summary.json").write_text(
                json.dumps(
                    {
                        "total_examples": 6,
                        "models_evaluated": [
                            "rule_based_baseline",
                            "ml_text_model",
                            "hybrid_model",
                        ],
                        "label_distribution": {"critical": 2},
                        "rule_based_metrics": {"accuracy": 0.7},
                        "ml_metrics": {"macro_f1": 0.5},
                        "hybrid_metrics": {"macro_f1": 0.6},
                        "binary_high_priority_metrics": {
                            "rule_based_baseline": {"high_priority_recall": 1.0, "high_priority_f1": 0.85},
                            "hybrid_model": {"important_critical_miss_count": 0},
                        },
                        "disagreement_count": 2,
                        "limitations": ["Small corpus."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_predictions.csv").write_text(
                "example_id,true_label\nex-1,critical\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_confusion_matrix.csv").write_text(
                "model,true_label,predicted_label,count\nml_text_model,critical,critical,1\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_feature_report.csv").write_text(
                "model,class_label,rank,feature_name,feature_type,coefficient\nml_text_model,critical,1,tfidf:срок,tfidf,0.5\n",
                encoding="utf-8",
            )
            (temp_dir / "significance_ml_error_examples.csv").write_text(
                "example_id,error_type\nex-1,rule_ml_disagreement\n",
                encoding="utf-8",
            )

            roots = (
                research_dashboard.FINAL_DIR,
                research_dashboard.FINAL_FIGURES_DIR,
                research_dashboard.FINAL_TABLES_DIR,
                research_dashboard.REAL_WORLD_DIR,
                temp_dir,
                research_dashboard.DOCS_EXPERIMENTS_DIR,
            )
            with mock.patch.multiple(
                research_dashboard,
                SIGNIFICANCE_ML_DIR=temp_dir,
                ARTIFACT_ROOTS=roots,
            ):
                response = self.client.get(reverse("demo-research-dashboard"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ML / Hybrid significance experiment")
        self.assertContains(response, "6")
