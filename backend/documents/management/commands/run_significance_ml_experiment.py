from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from documents.services.significance_ml_experiment import (
    DEFAULT_DATASET_CSV,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RANDOM_SEED,
    run_significance_ml_experiment,
)


class Command(BaseCommand):
    help = "Run the offline ML / hybrid significance experiment."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset-csv",
            default=str(DEFAULT_DATASET_CSV),
            help="Path to the labeled significance dataset CSV.",
        )
        parser.add_argument(
            "--output-dir",
            default=str(DEFAULT_OUTPUT_DIR),
            help="Directory where experiment artifacts will be written.",
        )
        parser.add_argument(
            "--random-seed",
            type=int,
            default=DEFAULT_RANDOM_SEED,
            help="Random seed for split generation and model training.",
        )

    def handle(self, *args, **options):
        summary = run_significance_ml_experiment(
            dataset_csv_path=Path(options["dataset_csv"]).resolve(),
            output_dir=Path(options["output_dir"]).resolve(),
            random_seed=int(options["random_seed"]),
        )
        self.stdout.write(self.style.SUCCESS("ML / Hybrid significance experiment completed"))
        self.stdout.write(f"Dataset source: {summary['dataset_source']}")
        self.stdout.write(f"Total examples: {summary['total_examples']}")
        self.stdout.write(f"Models evaluated: {', '.join(summary['models_evaluated'])}")
        self.stdout.write(
            "Rule-based high-priority recall: "
            f"{summary['binary_high_priority_metrics'].get('rule_based_baseline', {}).get('high_priority_recall', 0):.4f}"
        )
        self.stdout.write(
            "ML macro F1: "
            f"{summary.get('ml_metrics', {}).get('macro_f1', 0):.4f}"
        )
        self.stdout.write(
            "Hybrid macro F1: "
            f"{summary.get('hybrid_metrics', {}).get('macro_f1', 0):.4f}"
        )
        self.stdout.write(f"Summary artifact: {summary['output_files']['summary']}")
