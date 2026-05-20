from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from documents.models import Document
from documents.services.importance import classify_change_importance
from documents.services.supervised_ml_corpus import build_supervised_ml_corpus
from documents.services.supervised_ml_corpus import pd as corpus_pd
from documents.services.supervised_ml_corpus import train_baseline_ml_models


class Command(BaseCommand):
    help = "Run an end-to-end smoke test for settings, DB, demo data and offline ML pipeline."

    def handle(self, *args, **options):
        report = {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "settings": self._check_settings(),
            "database": self._check_database(),
            "demo_dataset": self._ensure_demo_dataset(),
        }

        smoke_root = Path(settings.BASE_DIR) / "smoke_test_artifacts"
        corpus_dir = smoke_root / "ml_corpus"
        corpus_profile = build_supervised_ml_corpus(output_dir=corpus_dir)
        baseline_summary = train_baseline_ml_models(corpus_dir=corpus_dir)
        quick_prediction = self._run_single_prediction(corpus_dir)

        report["training"] = {
            "total_examples": corpus_profile.get("total_examples", 0),
            "balanced_split_passed": corpus_profile.get("balanced_split_passed", False),
            "leakage_audit": corpus_profile.get("leakage_audit", {}),
            "baseline_results": baseline_summary.get("results_rows", []),
        }
        report["prediction"] = {
            **quick_prediction,
            "output_files": baseline_summary.get("output_files", {}),
        }
        report["status"] = (
            "passed"
            if report["settings"]["passed"]
            and report["database"]["passed"]
            and report["training"]["balanced_split_passed"]
            and report["training"]["leakage_audit"].get("passed", False)
            else "failed"
        )

        smoke_root.mkdir(parents=True, exist_ok=True)
        report_path = smoke_root / "smoke_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(self.style.SUCCESS(f"Smoke test {report['status']}"))
        self.stdout.write(f"Report: {report_path}")
        self.stdout.write(
            "Quick prediction: "
            f"{report['prediction'].get('predicted_label', 'n/a')} "
            f"(true={report['prediction'].get('true_label', 'n/a')}, "
            f"confidence={report['prediction'].get('confidence', 'n/a')})"
        )

    def _check_settings(self) -> dict[str, object]:
        checks = {
            "debug_disabled": settings.DEBUG is False,
            "csrf_cookie_httponly": bool(settings.CSRF_COOKIE_HTTPONLY),
            "secure_content_type_nosniff": bool(settings.SECURE_CONTENT_TYPE_NOSNIFF),
            "secret_key_present": bool(settings.SECRET_KEY),
        }
        return {"passed": all(checks.values()), "checks": checks}

    def _check_database(self) -> dict[str, object]:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        return {"passed": row == (1,), "echo": row}

    def _ensure_demo_dataset(self) -> dict[str, object]:
        before = Document.objects.count()
        if before == 0:
            try:
                call_command("load_demo_corpus")
            except Exception:
                call_command("load_demo_pairs")
        after = Document.objects.count()
        return {"passed": after > 0, "documents_before": before, "documents_after": after}

    def _run_single_prediction(self, corpus_dir: Path) -> dict[str, object]:
        test_df = corpus_pd.read_csv(corpus_dir / "test.csv")
        if test_df.empty:
            return {"passed": False, "detail": "test split is empty"}
        row = test_df.iloc[0].to_dict()
        result = classify_change_importance(
            old_text=str(row.get("old_text") or ""),
            new_text=str(row.get("new_text") or ""),
            change_type=str(row.get("semantic_type") or row.get("change_type") or ""),
            diff_text=f"OLD: {row.get('old_text', '')}\nNEW: {row.get('new_text', '')}",
        )
        return {
            "passed": True,
            "document_id": str(row.get("document_id") or ""),
            "true_label": str(row.get("y_significance") or ""),
            "predicted_label": result.label,
            "confidence": float(result.confidence),
        }
