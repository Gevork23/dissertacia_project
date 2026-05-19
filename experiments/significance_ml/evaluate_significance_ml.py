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

    from documents.services.significance_ml_experiment import (
        DEFAULT_OUTPUT_DIR,
        run_significance_ml_experiment,
    )

    summary = run_significance_ml_experiment(output_dir=DEFAULT_OUTPUT_DIR)
    print("ML / Hybrid significance experiment completed")
    print(f"Dataset source: {summary['dataset_source']}")
    print(f"Total examples: {summary['total_examples']}")
    print(f"Models evaluated: {', '.join(summary['models_evaluated'])}")
    print(
        "Rule-based high-priority recall: "
        f"{summary['binary_high_priority_metrics'].get('rule_based_baseline', {}).get('high_priority_recall', 0):.4f}"
    )
    print(
        "ML macro F1: "
        f"{summary.get('ml_metrics', {}).get('macro_f1', 0):.4f}"
    )
    print(
        "Hybrid macro F1: "
        f"{summary.get('hybrid_metrics', {}).get('macro_f1', 0):.4f}"
    )
    print(f"Disagreement count: {summary.get('disagreement_count', 0)}")
    print(f"Summary artifact: {summary['output_files']['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
