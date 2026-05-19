from __future__ import annotations

from typing import Any, Iterable

REGRESSION_LABELS = ("critical", "important", "minor")


def safe_divide(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def round_metric(value: int | float) -> float:
    return round(float(value), 4)


def compute_accuracy(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_results)
    correct = sum(1 for item in case_results if item.get("correct"))
    return {
        "value": round_metric(safe_divide(correct, total)),
        "correct": correct,
        "total": total,
    }


def compute_per_class_f1(
    case_results: list[dict[str, Any]],
    labels: Iterable[str] = REGRESSION_LABELS,
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for label in labels:
        tp = sum(
            1
            for item in case_results
            if item.get("expected_label") == label
            and item.get("predicted_label") == label
        )
        fp = sum(
            1
            for item in case_results
            if item.get("expected_label") != label
            and item.get("predicted_label") == label
        )
        fn = sum(
            1
            for item in case_results
            if item.get("expected_label") == label
            and item.get("predicted_label") != label
        )
        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        f1 = safe_divide(2 * precision * recall, precision + recall)
        metrics[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round_metric(precision),
            "recall": round_metric(recall),
            "f1": round_metric(f1),
        }
    return metrics


def compute_fallback_ratio(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    fallback_chunks = sum(
        int((item.get("chunking") or {}).get("fallback_chunks", 0))
        for item in case_results
    )
    total_chunks = sum(
        int((item.get("chunking") or {}).get("total_chunks", 0))
        for item in case_results
    )
    return {
        "value": round_metric(safe_divide(fallback_chunks, total_chunks)),
        "fallback_chunks": fallback_chunks,
        "total_chunks": total_chunks,
    }


def compute_average_unmatched_chunk_ratio(
    case_results: list[dict[str, Any]],
) -> float:
    if not case_results:
        return 0.0
    values = [
        float((item.get("chunking") or {}).get("unmatched_chunk_ratio", 0.0))
        for item in case_results
    ]
    return round_metric(sum(values) / len(values))


def compute_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accuracy": compute_accuracy(case_results),
        "f1_by_label": compute_per_class_f1(case_results),
        "fallback_ratio": compute_fallback_ratio(case_results),
        "average_unmatched_chunk_ratio": compute_average_unmatched_chunk_ratio(
            case_results
        ),
    }
