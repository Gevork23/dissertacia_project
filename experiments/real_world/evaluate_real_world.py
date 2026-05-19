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

    from documents.services.research_regression import (
        DEFAULT_OUTPUT_DIR,
        run_real_world_regression_suite,
    )

    summary = run_real_world_regression_suite(output_dir=DEFAULT_OUTPUT_DIR)
    metrics = summary["metrics"]
    print("Real-world regression suite completed")
    print(f"Corpus source: {summary['corpus_source']}")
    print(f"Pairs: {summary['processed_pairs']}/{summary['total_pairs']} processed")
    print(f"Failed pairs: {summary['failed_pairs']}")
    print(f"Total changes: {metrics['total_changes']}")
    print(f"Pipeline success rate: {metrics['pipeline_success_rate']:.2f}")
    print(f"Significant change rate: {metrics['significant_change_rate']:.2f}")
    print(f"Summary coverage: {metrics['summary_generation_available']:.2f}")
    print(f"Quiz coverage: {metrics['quiz_generation_available']:.2f}")
    print(f"Summary artifact: {summary['output_files']['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
