from __future__ import annotations

from django.core.management.base import BaseCommand

from documents.services.supervised_ml_corpus import (
    DEFAULT_OUTPUT_DIR,
    build_supervised_ml_corpus,
)


class Command(BaseCommand):
    help = "Build supervised ML corpus artifacts for offline significance experiments."

    def handle(self, *args, **options):
        profile = build_supervised_ml_corpus(output_dir=DEFAULT_OUTPUT_DIR)
        self.stdout.write(self.style.SUCCESS("Supervised ML corpus built"))
        self.stdout.write(f"Total examples: {profile['total_examples']}")
        self.stdout.write(f"Train size: {profile['split']['train_size']}")
        self.stdout.write(f"Test size: {profile['split']['test_size']}")
        self.stdout.write(f"Validation size: {profile['split']['validation_size']}")
        self.stdout.write(f"Output dir: {DEFAULT_OUTPUT_DIR}")
