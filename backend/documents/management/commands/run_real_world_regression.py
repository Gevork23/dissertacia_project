from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from documents.services.research_regression import (
    DEFAULT_DEMO_CORPUS_DIR,
    DEFAULT_MANUAL_FALLBACK_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUSLAWOD_CASES_PATH,
    run_real_world_regression_suite,
)


class Command(BaseCommand):
    help = "Run the offline real-world regression suite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of discovered pairs to process.",
        )
        parser.add_argument(
            "--output-dir",
            default=str(DEFAULT_OUTPUT_DIR),
            help="Directory where summary and CSV artifacts will be written.",
        )
        parser.add_argument(
            "--ruslawod-cases",
            default=str(DEFAULT_RUSLAWOD_CASES_PATH),
            help="Path to weak real-world pair definitions.",
        )
        parser.add_argument(
            "--demo-corpus-dir",
            default=str(DEFAULT_DEMO_CORPUS_DIR),
            help="Fallback demo corpus directory.",
        )
        parser.add_argument(
            "--manual-fallback-dir",
            default=str(DEFAULT_MANUAL_FALLBACK_DIR),
            help="Minimal fallback directory used when richer corpora are unavailable.",
        )

    def handle(self, *args, **options):
        summary = run_real_world_regression_suite(
            output_dir=Path(options["output_dir"]).resolve(),
            ruslawod_cases_path=Path(options["ruslawod_cases"]).resolve(),
            demo_corpus_dir=Path(options["demo_corpus_dir"]).resolve(),
            manual_fallback_dir=Path(options["manual_fallback_dir"]).resolve(),
            limit=options["limit"],
        )
        metrics = summary["metrics"]
        self.stdout.write(self.style.SUCCESS("Real-world regression suite completed"))
        self.stdout.write(f"Corpus source: {summary['corpus_source']}")
        self.stdout.write(
            f"Processed pairs: {summary['processed_pairs']}/{summary['total_pairs']}"
        )
        self.stdout.write(f"Failed pairs: {summary['failed_pairs']}")
        self.stdout.write(f"Total changes: {metrics['total_changes']}")
        self.stdout.write(
            f"Pipeline success rate: {metrics['pipeline_success_rate']:.2f}"
        )
        self.stdout.write(
            f"Significant change rate: {metrics['significant_change_rate']:.2f}"
        )
        self.stdout.write(f"Summary artifact: {summary['output_files']['summary']}")
