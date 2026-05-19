from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from documents.ruslawod.build_test_cases import build_regression_pairs


class Command(BaseCommand):
    help = "Generate regression candidate pairs from imported RusLawOD documents."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--output",
            type=str,
            default=str(
                Path(__file__).resolve().parents[4]
                / "regression"
                / "ruslawod_test_cases.json"
            ),
        )
        parser.add_argument(
            "--export-dir",
            type=str,
            default=str(
                Path(__file__).resolve().parents[4]
                / "regression"
                / "ruslawod_pairs"
            ),
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"]).resolve()
        export_dir = Path(options["export_dir"]).resolve()
        pairs = build_regression_pairs(
            limit=options["limit"],
            output_path=output_path,
            export_dir=export_dir,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {len(pairs)} RusLawOD regression pairs in {output_path}"
            )
        )
