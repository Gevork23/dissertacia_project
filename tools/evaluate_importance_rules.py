from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from documents.importance_service import LABELS, classify_change_row  # noqa: E402


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_metrics(actual: list[str], predicted: list[str]) -> tuple[float, float, dict[str, dict[str, float]], dict[str, dict[str, int]]]:
    labels = list(LABELS)
    confusion = {true_label: {pred_label: 0 for pred_label in labels} for true_label in labels}

    for true_label, pred_label in zip(actual, predicted):
        if true_label not in confusion:
            confusion[true_label] = {pred_label_inner: 0 for pred_label_inner in labels}
        if pred_label not in confusion[true_label]:
            for true_label_inner in confusion:
                confusion[true_label_inner].setdefault(pred_label, 0)
        confusion[true_label][pred_label] += 1

    total = len(actual)
    correct = sum(1 for true_label, pred_label in zip(actual, predicted) if true_label == pred_label)
    accuracy = safe_div(correct, total)

    per_label: dict[str, dict[str, float]] = {}
    f1_values: list[float] = []

    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other_label][label] for other_label in labels if other_label != label)
        fn = sum(confusion[label][other_label] for other_label in labels if other_label != label)

        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        support = sum(confusion[label].values())

        per_label[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(support),
        }
        f1_values.append(f1)

    macro_f1 = safe_div(sum(f1_values), len(f1_values))
    return accuracy, macro_f1, per_label, confusion


def print_confusion_matrix(confusion: dict[str, dict[str, int]]) -> None:
    labels = list(LABELS)
    header = ["true\\pred"] + labels
    widths = [max(len(col), 14) for col in header]

    def fmt_row(values: list[str]) -> str:
        padded = [value.ljust(width) for value, width in zip(values, widths)]
        return " | ".join(padded)

    print("\nConfusion matrix:")
    print(fmt_row(header))
    print("-" * (sum(widths) + 3 * (len(widths) - 1)))

    for true_label in labels:
        row = [true_label] + [str(confusion[true_label][pred_label]) for pred_label in labels]
        print(fmt_row(row))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate rule-based importance classifier on CSV dataset.")
    parser.add_argument(
        "--dataset",
        default=str(ROOT_DIR / "data" / "importance_dataset" / "changes_seed_v1.csv"),
        help="Path to CSV dataset.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"[ERROR] dataset not found: {dataset_path}")

    with dataset_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise SystemExit("[ERROR] dataset is empty")

    predictions: list[dict[str, str]] = []
    actual_labels: list[str] = []
    predicted_labels: list[str] = []

    for row in rows:
        prediction = classify_change_row(row)
        true_label = row["importance_label"]
        pred_label = prediction.label

        actual_labels.append(true_label)
        predicted_labels.append(pred_label)

        enriched_row = dict(row)
        enriched_row["predicted_label"] = pred_label
        enriched_row["confidence"] = f"{prediction.confidence:.2f}"
        enriched_row["triggered_rules"] = json.dumps(prediction.triggered_rules, ensure_ascii=False)
        enriched_row["explanation"] = prediction.explanation
        enriched_row["is_correct"] = "1" if true_label == pred_label else "0"
        predictions.append(enriched_row)

    accuracy, macro_f1, per_label, confusion = compute_metrics(actual_labels, predicted_labels)

    predictions_path = dataset_path.with_name(f"{dataset_path.stem}_predictions.csv")
    errors_path = dataset_path.with_name(f"{dataset_path.stem}_errors.csv")

    fieldnames = list(predictions[0].keys())

    with predictions_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(predictions)

    error_rows = [row for row in predictions if row["is_correct"] == "0"]
    with errors_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(error_rows)

    print(f"[OK] dataset: {dataset_path}")
    print(f"[OK] rows: {len(rows)}")
    print(f"[OK] accuracy: {accuracy:.4f}")
    print(f"[OK] macro_f1: {macro_f1:.4f}")
    print("\nPer-label metrics:")
    for label in LABELS:
        metrics = per_label[label]
        print(
            f"- {label:<13} "
            f"P={metrics['precision']:.4f} "
            f"R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f} "
            f"support={int(metrics['support'])}"
        )

    print_confusion_matrix(confusion)
    print(f"\n[OK] predictions: {predictions_path}")
    print(f"[OK] errors: {errors_path} ({len(error_rows)} rows)")


if __name__ == "__main__":
    main()