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
        train_baseline_ml_models,
    )

    summary = train_baseline_ml_models(corpus_dir=DEFAULT_OUTPUT_DIR)
    print("Baseline ML models trained")
    print(f"Train size: {summary['train_size']}")
    print(f"Test size: {summary['test_size']}")
    print(f"Results: {summary['output_files']['results']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
