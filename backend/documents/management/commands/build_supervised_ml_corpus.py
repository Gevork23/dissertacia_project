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
        split = profile.get("split", {})
        self.stdout.write(self.style.SUCCESS("Supervised ML corpus built"))
        self.stdout.write(f"Total examples: {profile['total_examples']}")
        self.stdout.write(f"Balanced split passed: {profile.get('balanced_split_passed', split.get('balanced_split_passed', 'n/a'))}")
        self.stdout.write(
            f"Leakage audit passed: {profile.get('leakage_audit', {}).get('passed', 'n/a')}"
        )
        self.stdout.write(f"Train size: {split.get('train_size', 'n/a')}")
        self.stdout.write(f"Test size: {split.get('test_size', 'n/a')}")
        self.stdout.write(f"Validation size: {split.get('validation_size', 'n/a')}")
        if "train_label_distribution" in split:
            self.stdout.write(f"Train labels: {split.get('train_label_distribution')}")
        if "validation_label_distribution" in split:
            self.stdout.write(f"Validation labels: {split.get('validation_label_distribution')}")
        if "test_label_distribution" in split:
            self.stdout.write(f"Test labels: {split.get('test_label_distribution')}")
        self.stdout.write(f"Output dir: {DEFAULT_OUTPUT_DIR}")
