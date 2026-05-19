from __future__ import annotations

from django.core.management.base import BaseCommand

from documents.services.supervised_ml_corpus import (
    DEFAULT_OUTPUT_DIR,
    train_baseline_ml_models,
)


class Command(BaseCommand):
    help = "Train baseline ML models on the prepared supervised ML corpus."

    def handle(self, *args, **options):
        summary = train_baseline_ml_models(corpus_dir=DEFAULT_OUTPUT_DIR)
        self.stdout.write(self.style.SUCCESS("Baseline ML models trained"))
        self.stdout.write(f"Train size: {summary['train_size']}")
        self.stdout.write(f"Test size: {summary['test_size']}")
        self.stdout.write(f"Results: {summary['output_files']['results']}")
