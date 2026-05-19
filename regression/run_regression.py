from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    from .metrics import REGRESSION_LABELS, compute_metrics
except ImportError:  # pragma: no cover - direct script execution
    from metrics import REGRESSION_LABELS, compute_metrics

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_CASES_PATH = ROOT_DIR / "regression" / "test_cases.json"
DEFAULT_REPORT_PATH = ROOT_DIR / "regression" / "regression_report.json"
DEFAULT_HISTORY_DIR = ROOT_DIR / "regression_history"

LABEL_PRIORITY = {
    "critical": 3,
    "important": 2,
    "minor": 1,
}
PRODUCTION_TO_REGRESSION_LABEL = {
    "critical": "critical",
    "important": "important",
    "informational": "minor",
    "editorial": "minor",
    "not_evaluated": "minor",
    "minor": "minor",
}


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    name: str
    v1_path: Path
    v2_path: Path
    expected_label: str
    expected_key_reason: str = ""


class ChunkCollection:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self._chunks = chunks

    def order_by(self, field_name: str) -> list[SimpleNamespace]:
        reverse = field_name.startswith("-")
        normalized_name = field_name.removeprefix("-")
        return sorted(
            self._chunks,
            key=lambda item: getattr(item, normalized_name),
            reverse=reverse,
        )

    def count(self) -> int:
        return len(self._chunks)


def configure_django() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def normalize_regression_label(label: str) -> str:
    normalized = (label or "").strip().lower()
    if normalized not in PRODUCTION_TO_REGRESSION_LABEL:
        raise ValueError(f"Unsupported significance label: {label!r}")
    return PRODUCTION_TO_REGRESSION_LABEL[normalized]


def load_test_cases(path: Path = DEFAULT_CASES_PATH) -> list[RegressionCase]:
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = (
        raw_payload.get("cases", raw_payload)
        if isinstance(raw_payload, dict)
        else raw_payload
    )
    if not isinstance(raw_cases, list):
        raise ValueError(
            "Regression test cases must be a list or an object with a cases list."
        )

    cases: list[RegressionCase] = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Regression case #{index} must be an object.")
        expected_label = normalize_regression_label(
            str(
                item.get("expected_significance_label")
                or item.get("significance_label")
                or ""
            )
        )
        case_id = str(item.get("id") or f"case_{index:03d}")
        cases.append(
            RegressionCase(
                case_id=case_id,
                name=str(item.get("name") or case_id),
                v1_path=resolve_project_path(str(item["v1_path"])),
                v2_path=resolve_project_path(str(item["v2_path"])),
                expected_label=expected_label,
                expected_key_reason=str(item.get("expected_key_reason") or ""),
            )
        )
    return cases


def resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def get_rule_version() -> str:
    configure_django()
    from django.conf import settings
    from documents.services import importance

    return str(
        getattr(settings, "SIGNIFICANCE_RULES_VERSION", "")
        or getattr(importance, "significance_rules_version", "")
        or "unknown"
    )


def get_min_accuracy(default: float = 0.85) -> float:
    configure_django()
    from django.conf import settings

    return float(getattr(settings, "REGRESSION_MIN_ACCURACY", default))


def build_in_memory_version(
    *,
    document: SimpleNamespace,
    version_id: int,
    version_number: int,
    source_path: Path,
    chunk_id_start: int,
) -> SimpleNamespace:
    from documents.domain.text_processing import (
        chunk_by_structure_ru,
        normalize_document_text,
        sha256_hex,
    )

    raw_text = source_path.read_text(encoding="utf-8")
    normalized_text = normalize_document_text(raw_text, extension=source_path.suffix)
    chunk_data = chunk_by_structure_ru(normalized_text)
    chunks = [
        SimpleNamespace(
            id=chunk_id_start + index,
            version_id=version_id,
            chunk_index=chunk.chunk_index,
            fragment_type=chunk.fragment_type,
            structure_level=chunk.structure_level,
            raw_label=chunk.raw_label,
            canonical_label=chunk.canonical_label,
            path_key=chunk.path_key,
            heading=chunk.heading,
            section_path=chunk.section_path,
            text=chunk.text,
            text_hash=chunk.text_hash or sha256_hex(chunk.text),
        )
        for index, chunk in enumerate(chunk_data, start=1)
    ]
    return SimpleNamespace(
        id=version_id,
        document_id=document.id,
        document=document,
        version_number=version_number,
        created_at=datetime.now(timezone.utc),
        source_filename=source_path.name,
        extracted_text=raw_text,
        normalized_text=normalized_text,
        content_hash=sha256_hex(normalized_text),
        chunks=ChunkCollection(chunks),
    )


def flatten_predicted_changes(diff_payload: dict[str, Any]) -> list[dict[str, Any]]:
    from documents.domain.diff import iter_ordered_change_entries

    changes: list[dict[str, Any]] = []
    for sort_order, (operation, payload) in enumerate(
        iter_ordered_change_entries(diff_payload),
        start=1,
    ):
        raw_label = str(payload.get("significance_label") or "not_evaluated")
        changes.append(
            {
                "sort_order": sort_order,
                "operation": operation,
                "predicted_raw_label": raw_label,
                "predicted_label": normalize_regression_label(raw_label),
                "semantic_type": payload.get("semantic_type", "unclassified"),
                "score": payload.get("significance_score", 0.0),
                "rules": payload.get("significance_rules", []),
                "reason": payload.get("significance_reason", ""),
                "old_text": payload.get("old_text", ""),
                "new_text": payload.get("new_text", ""),
            }
        )
    return changes


def select_pair_prediction(changes: list[dict[str, Any]]) -> dict[str, Any]:
    if not changes:
        return {
            "predicted_label": "minor",
            "predicted_raw_label": "not_evaluated",
            "semantic_type": "unclassified",
            "score": 0.0,
            "rules": [],
            "reason": "No changed chunks were produced by the comparison pipeline.",
        }
    return max(
        changes,
        key=lambda item: (
            LABEL_PRIORITY[item["predicted_label"]],
            float(item.get("score") or 0.0),
            -int(item.get("sort_order") or 0),
        ),
    )


def key_reason_matched(
    expected_key_reason: str,
    changes: list[dict[str, Any]],
) -> bool | None:
    expected = (expected_key_reason or "").strip().lower()
    if not expected:
        return None
    haystack = json.dumps(changes, ensure_ascii=False).lower()
    return expected in haystack


def build_chunking_stats(
    *,
    from_version: SimpleNamespace,
    to_version: SimpleNamespace,
    diff_payload: dict[str, Any],
) -> dict[str, Any]:
    old_chunks = from_version.chunks.order_by("chunk_index")
    new_chunks = to_version.chunks.order_by("chunk_index")
    all_chunks = [*old_chunks, *new_chunks]
    fallback_chunks = sum(
        1 for chunk in all_chunks if chunk.fragment_type == "fallback_block"
    )
    total_chunks = len(all_chunks)
    summary = diff_payload.get("summary") or {}
    unmatched_chunks = int(summary.get("added", 0) or 0) + int(
        summary.get("removed", 0) or 0
    )
    return {
        "old_chunks": len(old_chunks),
        "new_chunks": len(new_chunks),
        "total_chunks": total_chunks,
        "fallback_chunks": fallback_chunks,
        "fallback_ratio": round(fallback_chunks / total_chunks, 4)
        if total_chunks
        else 0.0,
        "unmatched_chunks": unmatched_chunks,
        "unmatched_chunk_ratio": round(unmatched_chunks / total_chunks, 4)
        if total_chunks
        else 0.0,
    }


def run_case(case: RegressionCase, *, case_index: int) -> dict[str, Any]:
    configure_django()
    from documents.domain.change_enrichment import enrich_compare_payload
    from documents.domain.diff import build_version_diff

    document = SimpleNamespace(id=case_index, title=case.name)
    from_version = build_in_memory_version(
        document=document,
        version_id=case_index * 10 + 1,
        version_number=1,
        source_path=case.v1_path,
        chunk_id_start=case_index * 10000,
    )
    to_version = build_in_memory_version(
        document=document,
        version_id=case_index * 10 + 2,
        version_number=2,
        source_path=case.v2_path,
        chunk_id_start=case_index * 10000 + 5000,
    )

    raw_diff_payload = build_version_diff(from_version, to_version)
    diff_payload = enrich_compare_payload(raw_diff_payload)
    changes = flatten_predicted_changes(diff_payload)
    prediction = select_pair_prediction(changes)
    predicted_label = prediction["predicted_label"]
    correct = predicted_label == case.expected_label

    return {
        "id": case.case_id,
        "name": case.name,
        "v1_path": display_path(case.v1_path),
        "v2_path": display_path(case.v2_path),
        "expected_label": case.expected_label,
        "expected_key_reason": case.expected_key_reason,
        "predicted_label": predicted_label,
        "predicted_raw_label": prediction["predicted_raw_label"],
        "predicted_semantic_type": prediction.get("semantic_type", "unclassified"),
        "correct": correct,
        "key_reason_matched": key_reason_matched(
            case.expected_key_reason,
            changes,
        ),
        "chunking": build_chunking_stats(
            from_version=from_version,
            to_version=to_version,
            diff_payload=diff_payload,
        ),
        "comparison_summary": diff_payload.get("summary", {}),
        "predicted_changes": changes,
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def save_report(
    report: dict[str, Any],
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_dir: Path = DEFAULT_HISTORY_DIR,
) -> tuple[Path, Path]:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(json_safe(report), ensure_ascii=False, indent=2)
    report_path.write_text(payload + "\n", encoding="utf-8")

    timestamp = report["generated_at"].replace("-", "").replace(":", "")
    timestamp = timestamp.replace("+0000", "Z").replace("+00:00", "Z")
    safe_rule_version = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in report["rule_version"]
    )
    history_path = history_dir / f"v{safe_rule_version}_{timestamp}.json"
    history_path.write_text(payload + "\n", encoding="utf-8")
    return report_path, history_path


def run_regression(
    *,
    cases_path: Path = DEFAULT_CASES_PATH,
    min_accuracy: float | None = None,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_dir: Path = DEFAULT_HISTORY_DIR,
) -> dict[str, Any]:
    threshold = get_min_accuracy() if min_accuracy is None else float(min_accuracy)
    rule_version = get_rule_version()
    cases = load_test_cases(cases_path)
    case_results = [
        run_case(case, case_index=index) for index, case in enumerate(cases, start=1)
    ]
    metrics = compute_metrics(case_results)
    accuracy = metrics["accuracy"]["value"]
    failed_cases = [
        item["id"] for item in case_results if not bool(item.get("correct"))
    ]
    passed = accuracy >= threshold
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report = {
        "generated_at": generated_at,
        "rule_version": rule_version,
        "thresholds": {
            "min_accuracy": threshold,
        },
        "passed": passed,
        "failed_cases": failed_cases,
        "metrics": metrics,
        "labels": list(REGRESSION_LABELS),
        "cases": case_results,
    }
    saved_report_path, history_path = save_report(
        report,
        report_path=report_path,
        history_dir=history_dir,
    )
    report["report_path"] = str(saved_report_path)
    report["history_path"] = str(history_path)
    return report


def format_case_table(report: dict[str, Any]) -> list[str]:
    rows = report.get("cases", [])
    if not rows:
        return ["No regression cases found."]

    header = (
        "Case                                  Expected   Predicted  "
        "OK  Fallback  Unmatched"
    )
    separator = (
        "----                                  --------   ---------  "
        "--  --------  ---------"
    )
    lines = [
        header,
        separator,
    ]
    for row in rows:
        name = str(row["id"])[:36]
        expected = str(row["expected_label"])
        predicted = str(row["predicted_label"])
        ok = "yes" if row.get("correct") else "no"
        chunking = row.get("chunking") or {}
        fallback = float(chunking.get("fallback_ratio", 0.0))
        unmatched = float(chunking.get("unmatched_chunk_ratio", 0.0))
        lines.append(
            f"{name:<36}  {expected:<9}  {predicted:<9}  {ok:<2}  "
            f"{fallback:<8.2f}  {unmatched:<9.2f}"
        )
    return lines


def format_console_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    accuracy = metrics["accuracy"]
    f1_by_label = metrics["f1_by_label"]
    threshold = float(report["thresholds"]["min_accuracy"])
    status_line = (
        f"Regression passed (threshold: {threshold:.2f})"
        if report["passed"]
        else f"Regression failed (threshold: {threshold:.2f})"
    )

    lines = []
    lines.extend(format_case_table(report))
    lines.append("")
    lines.append(
        f"Accuracy: {accuracy['value']:.2f} "
        f"({accuracy['correct']}/{accuracy['total']})"
    )
    lines.append(f"Critical F1: {f1_by_label['critical']['f1']:.2f}")
    lines.append(f"Important F1: {f1_by_label['important']['f1']:.2f}")
    lines.append(f"Minor F1: {f1_by_label['minor']['f1']:.2f}")
    lines.append(f"Fallback ratio: {metrics['fallback_ratio']['value']:.2f}")
    lines.append(
        "Average unmatched chunk ratio: "
        f"{metrics['average_unmatched_chunk_ratio']:.2f}"
    )
    lines.append(status_line)
    if report.get("failed_cases"):
        lines.append(f"Failed cases: {', '.join(report['failed_cases'])}")
    lines.append(f"Report: {report['report_path']}")
    lines.append(f"History: {report['history_path']}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the document comparison regression harness."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_regression(
        cases_path=args.cases,
        min_accuracy=args.threshold,
        report_path=args.report,
        history_dir=args.history_dir,
    )
    print(format_console_report(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
