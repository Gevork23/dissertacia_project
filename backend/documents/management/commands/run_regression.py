from __future__ import annotations

import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run the document comparison regression harness."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cases",
            default="",
            help="Path to regression test_cases.json.",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=None,
            help="Minimum accuracy. Defaults to REGRESSION_MIN_ACCURACY.",
        )
        parser.add_argument(
            "--report",
            default="",
            help="Path for the latest regression_report.json.",
        )
        parser.add_argument(
            "--history-dir",
            default="",
            help="Directory for versioned regression history reports.",
        )

    def handle(self, *args, **options):
        project_dir = Path(settings.PROJECT_DIR)
        if str(project_dir) not in sys.path:
            sys.path.insert(0, str(project_dir))

        from regression.run_regression import (
            DEFAULT_CASES_PATH,
            DEFAULT_HISTORY_DIR,
            DEFAULT_REPORT_PATH,
            format_console_report,
            run_regression,
        )

        cases_path = Path(options["cases"]) if options["cases"] else DEFAULT_CASES_PATH
        report_path = (
            Path(options["report"]) if options["report"] else DEFAULT_REPORT_PATH
        )
        history_dir = (
            Path(options["history_dir"])
            if options["history_dir"]
            else DEFAULT_HISTORY_DIR
        )

        report = run_regression(
            cases_path=cases_path,
            min_accuracy=options["threshold"],
            report_path=report_path,
            history_dir=history_dir,
        )
        self.stdout.write(format_console_report(report))

        if not report["passed"]:
            metrics = report["metrics"]
            accuracy = metrics["accuracy"]["value"]
            threshold = report["thresholds"]["min_accuracy"]
            failed_cases = ", ".join(report.get("failed_cases") or [])
            raise CommandError(
                "Regression failed: "
                f"accuracy {accuracy:.2f} is below threshold {threshold:.2f}. "
                f"Failed cases: {failed_cases or 'none'}."
            )
