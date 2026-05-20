from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def configure_django() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def main() -> int:
    configure_django()

    from documents.services.supervised_ml_corpus import (
        DEFAULT_OUTPUT_DIR,
        build_supervised_ml_corpus,
    )

    profile = build_supervised_ml_corpus(output_dir=DEFAULT_OUTPUT_DIR)
    print("Supervised ML corpus built")
    print(f"Total examples: {profile['total_examples']}")
    print(f"Strict examples: {profile['strict_examples']}")
    print(f"Weak examples: {profile['weak_examples']}")
    print(f"Balanced split passed: {profile['balanced_split_passed']}")
    print(f"Train size: {profile['split']['train_size']}")
    print(f"Test size: {profile['split']['test_size']}")
    print(f"Validation size: {profile['split']['validation_size']}")
    print(f"Train labels: {profile['split']['train_label_distribution']}")
    print(f"Validation labels: {profile['split']['validation_label_distribution']}")
    print(f"Test labels: {profile['split']['test_label_distribution']}")
    if profile['split'].get('warnings'):
        print(f"Split warnings: {profile['split']['warnings']}")
    print(f"Output dir: {DEFAULT_OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
