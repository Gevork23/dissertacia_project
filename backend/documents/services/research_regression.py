from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from documents.domain.change_enrichment import enrich_compare_payload
from documents.domain.diff import build_version_diff, iter_ordered_change_entries
from documents.domain.diff_quiz import build_quiz_from_summary
from documents.domain.diff_summary import build_brief_summary
from documents.domain.text_processing import (
    chunk_by_structure_ru,
    normalize_document_text,
    sha256_hex,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "experiments" / "real_world"
DEFAULT_RUSLAWOD_CASES_PATH = PROJECT_ROOT / "regression" / "ruslawod_test_cases.json"
DEFAULT_DEMO_CORPUS_DIR = PROJECT_ROOT / "data" / "demo_corpus"
DEFAULT_MANUAL_FALLBACK_DIR = PROJECT_ROOT / "data" / "manual_samples"


@dataclass(frozen=True)
class RealWorldPair:
    pair_id: str
    source: str
    old_file: Path
    new_file: Path
    title: str = ""
    weak_label: str = ""
    metadata: dict[str, Any] | None = None


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


def rel_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _truncate(text: str, limit: int = 160) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def _load_ruslawod_pairs(path: Path) -> list[RealWorldPair]:
    if not path.exists():
        return []
    payload = _read_json(path)
    raw_pairs = payload.get("cases", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_pairs, list):
        return []

    discovered: list[RealWorldPair] = []
    for item in raw_pairs:
        if not isinstance(item, dict):
            continue
        old_file = Path(str(item.get("v1_path") or ""))
        new_file = Path(str(item.get("v2_path") or ""))
        if not old_file.is_absolute():
            old_file = PROJECT_ROOT / old_file
        if not new_file.is_absolute():
            new_file = PROJECT_ROOT / new_file
        if not old_file.exists() or not new_file.exists():
            continue
        discovered.append(
            RealWorldPair(
                pair_id=str(item.get("id") or old_file.parent.name),
                source="ruslawod_weak_regression",
                old_file=old_file,
                new_file=new_file,
                title=str(item.get("name") or ""),
                weak_label=str(item.get("expected_significance_label") or ""),
                metadata={
                    "group_key": item.get("group_key"),
                    "annotation_status": item.get("annotation_status"),
                    "v1_document_id": item.get("v1_document_id"),
                    "v2_document_id": item.get("v2_document_id"),
                },
            )
        )
    return discovered


def _load_demo_pairs(directory: Path) -> list[RealWorldPair]:
    if not directory.exists():
        return []
    discovered: list[RealWorldPair] = []
    for pair_dir in sorted(path for path in directory.iterdir() if path.is_dir()):
        old_file = pair_dir / "old.txt"
        new_file = pair_dir / "new.txt"
        if not old_file.exists() or not new_file.exists():
            continue
        title = pair_dir.name
        metadata_path = pair_dir / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                metadata = _read_json(metadata_path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                metadata = {}
            title = str(metadata.get("title") or metadata.get("name") or title)
        discovered.append(
            RealWorldPair(
                pair_id=pair_dir.name,
                source="demo_fallback_regression",
                old_file=old_file,
                new_file=new_file,
                title=title,
                weak_label=str(metadata.get("expected_significance_label") or ""),
                metadata=metadata,
            )
        )
    return discovered


def _load_manual_fallback_pairs(directory: Path) -> list[RealWorldPair]:
    old_file = directory / "version_stub_v1.txt"
    new_file = directory / "version_stub_v2.txt"
    if not old_file.exists() or not new_file.exists():
        return []
    return [
        RealWorldPair(
            pair_id="manual_samples_pair_0001",
            source="manual_samples_fallback",
            old_file=old_file,
            new_file=new_file,
            title="Manual samples fallback pair",
            metadata={},
        )
    ]


def discover_regression_pairs(
    *,
    ruslawod_cases_path: Path = DEFAULT_RUSLAWOD_CASES_PATH,
    demo_corpus_dir: Path = DEFAULT_DEMO_CORPUS_DIR,
    manual_fallback_dir: Path = DEFAULT_MANUAL_FALLBACK_DIR,
    limit: int | None = None,
) -> tuple[list[RealWorldPair], str, list[str]]:
    warnings: list[str] = []

    ruslawod_pairs = _load_ruslawod_pairs(ruslawod_cases_path)
    if ruslawod_pairs:
        selected = ruslawod_pairs[:limit] if limit is not None else ruslawod_pairs
        return selected, "ruslawod_weak_regression", warnings

    warnings.append(
        "RusLawOD weak regression pairs were not available; falling back to demo corpus pairs."
    )
    demo_pairs = _load_demo_pairs(demo_corpus_dir)
    if demo_pairs:
        selected = demo_pairs[:limit] if limit is not None else demo_pairs
        return selected, "demo_fallback_regression", warnings

    warnings.append(
        "Demo corpus pairs were not available; falling back to minimal manual samples."
    )
    manual_pairs = _load_manual_fallback_pairs(manual_fallback_dir)
    selected = manual_pairs[:limit] if limit is not None else manual_pairs
    return selected, "manual_samples_fallback", warnings


def build_in_memory_version(
    *,
    document: SimpleNamespace,
    version_id: int,
    version_number: int,
    source_path: Path,
    chunk_id_start: int,
) -> SimpleNamespace:
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


def _pair_status_from_warnings(warnings: list[str], failed: bool = False) -> str:
    if failed:
        return "failed"
    if warnings:
        return "partial"
    return "ok"


def evaluate_pair(pair: RealWorldPair, *, pair_index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pair_warnings: list[str] = []
    document = SimpleNamespace(id=pair_index, title=pair.title or pair.pair_id)
    try:
        from_version = build_in_memory_version(
            document=document,
            version_id=pair_index * 10 + 1,
            version_number=1,
            source_path=pair.old_file,
            chunk_id_start=pair_index * 10000,
        )
        to_version = build_in_memory_version(
            document=document,
            version_id=pair_index * 10 + 2,
            version_number=2,
            source_path=pair.new_file,
            chunk_id_start=pair_index * 10000 + 5000,
        )
        raw_diff = build_version_diff(from_version, to_version)
        diff_payload = enrich_compare_payload(raw_diff)
    except Exception as exc:
        pair_result = {
            "pair_id": pair.pair_id,
            "source": pair.source,
            "title": pair.title,
            "old_file": rel_repo_path(pair.old_file),
            "new_file": rel_repo_path(pair.new_file),
            "old_length": 0,
            "new_length": 0,
            "chunk_count_old": 0,
            "chunk_count_new": 0,
            "change_count_total": 0,
            "change_count_added": 0,
            "change_count_removed": 0,
            "change_count_modified": 0,
            "change_count_moved": 0,
            "significant_count": 0,
            "critical_count": 0,
            "important_count": 0,
            "informational_count": 0,
            "editorial_count": 0,
            "quiz_question_count": 0,
            "summary_highlight_count": 0,
            "warnings": f"pipeline failure: {exc}",
            "status": "failed",
        }
        return pair_result, []

    summary_payload = None
    try:
        summary_payload = build_brief_summary(diff_payload)
        summary_highlight_count = len(summary_payload.get("highlights") or [])
    except Exception as exc:
        pair_warnings.append(f"summary generation unavailable: {exc}")
        summary_highlight_count = 0

    try:
        if summary_payload is None:
            raise RuntimeError("summary payload missing")
        quiz_payload = build_quiz_from_summary(
            summary_payload=summary_payload,
            from_version=diff_payload["from_version"],
            to_version=diff_payload["to_version"],
            identical=bool(diff_payload.get("identical", False)),
            max_questions=10,
        )
        quiz_question_count = int(quiz_payload.get("questions_count") or 0)
    except Exception as exc:
        pair_warnings.append(f"quiz generation unavailable: {exc}")
        quiz_question_count = 0

    summary = diff_payload.get("summary") or {}
    significance = summary.get("by_significance") or {}
    critical_count = int(significance.get("critical") or 0)
    important_count = int(significance.get("important") or 0)
    informational_count = int(significance.get("informational") or 0)
    editorial_count = int(significance.get("editorial") or 0)
    significant_count = critical_count + important_count + informational_count

    pair_result = {
        "pair_id": pair.pair_id,
        "source": pair.source,
        "title": pair.title,
        "old_file": rel_repo_path(pair.old_file),
        "new_file": rel_repo_path(pair.new_file),
        "old_length": len(from_version.normalized_text or ""),
        "new_length": len(to_version.normalized_text or ""),
        "chunk_count_old": from_version.chunks.count(),
        "chunk_count_new": to_version.chunks.count(),
        "change_count_total": int(summary.get("added") or 0)
        + int(summary.get("removed") or 0)
        + int(summary.get("modified") or 0)
        + int(summary.get("moved") or 0),
        "change_count_added": int(summary.get("added") or 0),
        "change_count_removed": int(summary.get("removed") or 0),
        "change_count_modified": int(summary.get("modified") or 0),
        "change_count_moved": int(summary.get("moved") or 0),
        "significant_count": significant_count,
        "critical_count": critical_count,
        "important_count": important_count,
        "informational_count": informational_count,
        "editorial_count": editorial_count,
        "quiz_question_count": quiz_question_count,
        "summary_highlight_count": summary_highlight_count,
        "warnings": " | ".join(pair_warnings),
        "status": _pair_status_from_warnings(pair_warnings),
    }

    trace_rows: list[dict[str, Any]] = []
    for change_index, (operation_type, payload) in enumerate(
        iter_ordered_change_entries(diff_payload),
        start=1,
    ):
        old_text = ""
        new_text = ""
        if operation_type in {"modified", "moved"}:
            old_text = str((payload.get("from_chunk") or {}).get("text") or "")
            new_text = str((payload.get("to_chunk") or {}).get("text") or "")
        elif operation_type == "removed":
            old_text = str(payload.get("text") or "")
        else:
            new_text = str(payload.get("text") or "")
        trace_rows.append(
            {
                "pair_id": pair.pair_id,
                "change_index": change_index,
                "operation_type": operation_type,
                "semantic_type": payload.get("semantic_type", "unclassified"),
                "significance_label": payload.get("significance_label", "not_evaluated"),
                "requires_manual_review": bool(payload.get("requires_manual_review", False)),
                "old_preview": _truncate(old_text),
                "new_preview": _truncate(new_text),
                "explanation": _truncate(str(payload.get("significance_reason") or ""), 220),
                "warning": pair_result["warnings"],
            }
        )
    return pair_result, trace_rows


def _safe_divide(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def build_stage_summary_rows(
    *,
    corpus_source: str,
    total_pairs: int,
    processed_pairs: int,
    failed_pairs: int,
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_rows = [
        {
            "stage": "pair_discovery",
            "component": corpus_source,
            "status": "available" if total_pairs else "missing",
            "main_metric": "pairs_discovered",
            "value": total_pairs,
            "interpretation": "Discovered candidate real-world or fallback regression pairs.",
        },
        {
            "stage": "extraction",
            "component": "plain_text_pair_loading",
            "status": "partial",
            "main_metric": "processed_pairs",
            "value": processed_pairs,
            "interpretation": "The suite loads prepared plain-text pairs; binary extraction is not exercised here.",
        },
        {
            "stage": "chunking",
            "component": "structural_chunking",
            "status": "available" if processed_pairs else "missing",
            "main_metric": "average_chunks_old",
            "value": metrics["average_chunks_old"],
            "interpretation": "Average number of structural chunks in source versions.",
        },
        {
            "stage": "diff",
            "component": "version_comparison",
            "status": "available" if processed_pairs else "missing",
            "main_metric": "average_changes_per_pair",
            "value": metrics["average_changes_per_pair"],
            "interpretation": "Average number of detected change items per processed pair.",
        },
        {
            "stage": "significance",
            "component": "rule_based_prioritization",
            "status": "available" if processed_pairs else "missing",
            "main_metric": "significant_change_rate",
            "value": metrics["significant_change_rate"],
            "interpretation": "Share of non-editorial changes among all detected changes.",
        },
        {
            "stage": "summary",
            "component": "brief_summary_generation",
            "status": "available" if metrics["summary_generation_available"] else "partial",
            "main_metric": "summary_generation_available",
            "value": metrics["summary_generation_available"],
            "interpretation": "Coverage of pairs for which summary generation completed in offline mode.",
        },
        {
            "stage": "quiz",
            "component": "quiz_generation",
            "status": "available" if metrics["quiz_generation_available"] else "partial",
            "main_metric": "quiz_generation_available",
            "value": metrics["quiz_generation_available"],
            "interpretation": "Coverage of pairs for which quiz generation completed in offline mode.",
        },
        {
            "stage": "end_to_end",
            "component": "offline_regression_pipeline",
            "status": "available" if processed_pairs and not failed_pairs else ("partial" if processed_pairs else "missing"),
            "main_metric": "pipeline_success_rate",
            "value": metrics["pipeline_success_rate"],
            "interpretation": "Fraction of discovered pairs processed without fatal pipeline failure.",
        },
    ]
    return summary_rows


def build_limitations(corpus_source: str, discovery_warnings: list[str]) -> list[str]:
    limitations = [
        "This suite is a regression/stability layer and does not claim strict gold accuracy in the absence of manual labels.",
        "The dashboard and saved artifacts visualize already computed outputs and do not re-run the regression suite during HTTP requests.",
        "The suite exercises normalized plain-text pair artifacts; binary extraction robustness must be validated separately.",
    ]
    if corpus_source == "ruslawod_weak_regression":
        limitations.append(
            "RusLawOD pairs are treated as weak real-world regression material; pair construction depends on heuristic version-family grouping rather than authoritative legal lineage."
        )
    if corpus_source == "demo_fallback_regression":
        limitations.append(
            "The current run used demo corpus fallback pairs. This is suitable for realistic regression smoke checks, but it is not a full real-world benchmark."
        )
    if corpus_source == "manual_samples_fallback":
        limitations.append(
            "The current run used only minimal manual fallback pairs because broader real-world artifacts were unavailable."
        )
    limitations.extend(discovery_warnings)
    return limitations


def run_real_world_regression_suite(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    ruslawod_cases_path: Path = DEFAULT_RUSLAWOD_CASES_PATH,
    demo_corpus_dir: Path = DEFAULT_DEMO_CORPUS_DIR,
    manual_fallback_dir: Path = DEFAULT_MANUAL_FALLBACK_DIR,
    limit: int | None = None,
) -> dict[str, Any]:
    pairs, corpus_source, discovery_warnings = discover_regression_pairs(
        ruslawod_cases_path=ruslawod_cases_path,
        demo_corpus_dir=demo_corpus_dir,
        manual_fallback_dir=manual_fallback_dir,
        limit=limit,
    )

    pair_results: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        pair_result, pair_trace_rows = evaluate_pair(pair, pair_index=index)
        pair_results.append(pair_result)
        trace_rows.extend(pair_trace_rows)

    total_pairs = len(pairs)
    processed_pairs = sum(1 for row in pair_results if row["status"] != "failed")
    failed_pairs = total_pairs - processed_pairs
    total_changes = sum(int(row["change_count_total"]) for row in pair_results)
    total_significant = sum(int(row["significant_count"]) for row in pair_results)
    total_critical_or_important = sum(
        int(row["critical_count"]) + int(row["important_count"]) for row in pair_results
    )
    warning_count = sum(
        1 for row in pair_results if str(row.get("warnings") or "").strip()
    ) + len(discovery_warnings)
    summary_available_count = sum(
        1 for row in pair_results if int(row.get("summary_highlight_count") or 0) > 0 or row["status"] != "failed"
    )
    quiz_available_count = sum(
        1 for row in pair_results if int(row.get("quiz_question_count") or 0) >= 0 and row["status"] != "failed"
    )

    metrics = {
        "total_pairs": total_pairs,
        "processed_pairs": processed_pairs,
        "failed_pairs": failed_pairs,
        "total_changes": total_changes,
        "average_changes_per_pair": round(total_changes / processed_pairs, 2)
        if processed_pairs
        else 0.0,
        "average_chunks_old": round(
            sum(int(row["chunk_count_old"]) for row in pair_results) / processed_pairs, 2
        )
        if processed_pairs
        else 0.0,
        "average_chunks_new": round(
            sum(int(row["chunk_count_new"]) for row in pair_results) / processed_pairs, 2
        )
        if processed_pairs
        else 0.0,
        "significant_change_rate": _safe_divide(total_significant, total_changes),
        "critical_or_important_rate": _safe_divide(
            total_critical_or_important,
            total_changes,
        ),
        "summary_generation_available": _safe_divide(
            summary_available_count,
            total_pairs,
        ),
        "quiz_generation_available": _safe_divide(
            quiz_available_count,
            total_pairs,
        ),
        "warning_count": warning_count,
        "pipeline_success_rate": _safe_divide(processed_pairs, total_pairs),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "real_world_summary.json"
    pair_results_path = output_dir / "real_world_pair_results.csv"
    trace_path = output_dir / "real_world_trace.csv"
    stage_summary_path = output_dir / "real_world_stage_summary.csv"

    stage_summary_rows = build_stage_summary_rows(
        corpus_source=corpus_source,
        total_pairs=total_pairs,
        processed_pairs=processed_pairs,
        failed_pairs=failed_pairs,
        metrics=metrics,
    )
    limitations = build_limitations(corpus_source, discovery_warnings)

    summary_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "corpus_source": corpus_source,
        "total_pairs": total_pairs,
        "processed_pairs": processed_pairs,
        "failed_pairs": failed_pairs,
        "metrics": metrics,
        "limitations": limitations,
        "warnings": discovery_warnings + [row["warnings"] for row in pair_results if row["warnings"]],
        "output_files": {
            "summary": rel_repo_path(summary_path),
            "pair_results": rel_repo_path(pair_results_path),
            "trace": rel_repo_path(trace_path),
            "stage_summary": rel_repo_path(stage_summary_path),
        },
    }
    _write_json(summary_path, summary_payload)
    _write_csv(
        pair_results_path,
        pair_results,
        headers=[
            "pair_id",
            "source",
            "title",
            "old_file",
            "new_file",
            "old_length",
            "new_length",
            "chunk_count_old",
            "chunk_count_new",
            "change_count_total",
            "change_count_added",
            "change_count_removed",
            "change_count_modified",
            "change_count_moved",
            "significant_count",
            "critical_count",
            "important_count",
            "informational_count",
            "editorial_count",
            "quiz_question_count",
            "summary_highlight_count",
            "warnings",
            "status",
        ],
    )
    _write_csv(
        trace_path,
        trace_rows,
        headers=[
            "pair_id",
            "change_index",
            "operation_type",
            "semantic_type",
            "significance_label",
            "requires_manual_review",
            "old_preview",
            "new_preview",
            "explanation",
            "warning",
        ],
    )
    _write_csv(
        stage_summary_path,
        stage_summary_rows,
        headers=[
            "stage",
            "component",
            "status",
            "main_metric",
            "value",
            "interpretation",
        ],
    )
    return summary_payload
