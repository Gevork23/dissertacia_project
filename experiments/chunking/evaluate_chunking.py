#!/usr/bin/env python
"""Evaluate structural chunking quality on the Phase 13 evaluation corpus.

The experiment compares three methods:
1. paragraph_baseline: split by blank-line paragraph boundaries;
2. heading_article_baseline: split by major headings and numbered clauses;
3. hybrid_structural: the current project implementation, ``chunk_by_structure_ru``.

The script intentionally does not modify the production chunking algorithm.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from documents.domain.text_processing import (  # noqa: E402
    FRAGMENT_TYPE_ARTICLE,
    FRAGMENT_TYPE_CHAPTER,
    FRAGMENT_TYPE_FALLBACK_BLOCK,
    FRAGMENT_TYPE_PARAGRAPH,
    FRAGMENT_TYPE_POINT,
    FRAGMENT_TYPE_SECTION,
    FRAGMENT_TYPE_SUBPOINT,
    chunk_by_structure_ru,
    materialize_document_text,
    normalize_text,
    sha256_hex,
)

CORPUS_DIR = ROOT_DIR / "data" / "evaluation_corpus"
RESULTS_CSV = ROOT_DIR / "experiments" / "chunking" / "chunking_results.csv"
SUMMARY_JSON = ROOT_DIR / "experiments" / "chunking" / "chunking_summary.json"
F1_PNG = ROOT_DIR / "experiments" / "chunking" / "chunking_f1.png"

METHOD_PARAGRAPH = "paragraph_baseline"
METHOD_HEADING_ARTICLE = "heading_article_baseline"
METHOD_HYBRID = "hybrid_structural"

MAJOR_HEADING_RE = re.compile(
    r"^(?P<kind>раздел|глава|статья)\s+"
    r"(?P<num>[0-9IVXLCА-ЯЁA-Z]+(?:\.[0-9]+)*)"
    r"(?:[.)])?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
TEXTUAL_CLAUSE_RE = re.compile(
    r"^(?P<kind>пункт|абзац)\s+"
    r"(?P<num>[0-9IVXLCА-ЯЁA-Zа-яёa-z-]+(?:\.[0-9]+)*)"
    r"(?:[.)])?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
NUMBERED_CLAUSE_RE = re.compile(r"^(?P<label>\d+(?:\.\d+)*)\.\s*(?P<body>.*)$")


@dataclass(frozen=True)
class EvalChunk:
    chunk_index: int
    text: str
    fragment_type: str
    heading: str = ""
    section_path: str = ""
    canonical_label: str = ""
    path_key: str = ""
    text_hash: str = ""


@dataclass(frozen=True)
class ExpectedChunk:
    chunk_id: str
    version: str
    fragment: str
    expected_type: str
    boundary_text: str
    is_key_chunk: bool


@dataclass(frozen=True)
class MethodSpec:
    name: str
    role: str
    description: str
    chunker: Callable[[str], list[EvalChunk]]


@dataclass
class MatchResult:
    correct_boundaries: int
    key_correct_boundaries: int
    matched_expected_ids: list[str]
    missed_expected_ids: list[str]
    merged_expected_ids: list[str]
    empty_boundary_ids: list[str]


def normalize_for_match(value: str) -> str:
    """Normalize text for boundary containment checks."""

    normalized = normalize_text(value or "").casefold()
    return " ".join(normalized.split())


def safe_divide(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def calculate_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def paragraph_baseline(text: str) -> list[EvalChunk]:
    """Naive paragraph split by empty lines."""

    normalized = materialize_document_text(text, extension=".txt").normalized_text
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    chunks: list[EvalChunk] = []
    for index, block in enumerate(blocks, start=1):
        chunks.append(
            EvalChunk(
                chunk_index=index,
                text=block,
                fragment_type=FRAGMENT_TYPE_PARAGRAPH,
                heading=f"Paragraph {index}",
                section_path=f"Paragraph {index}",
                canonical_label=f"Paragraph {index}",
                path_key=f"paragraph:{index}",
                text_hash=sha256_hex(block),
            )
        )
    return chunks


def classify_heading_article_line(line: str) -> tuple[bool, str, str]:
    """Return whether a line starts a baseline chunk and its coarse type/label."""

    major_match = MAJOR_HEADING_RE.match(line)
    if major_match:
        kind = major_match.group("kind").casefold()
        fragment_type = {
            "раздел": FRAGMENT_TYPE_SECTION,
            "глава": FRAGMENT_TYPE_CHAPTER,
            "статья": FRAGMENT_TYPE_ARTICLE,
        }.get(kind, "heading")
        label = f"{major_match.group('kind').title()} {major_match.group('num')}"
        return True, fragment_type, label

    textual_match = TEXTUAL_CLAUSE_RE.match(line)
    if textual_match:
        kind = textual_match.group("kind").casefold()
        fragment_type = FRAGMENT_TYPE_POINT if kind == "пункт" else FRAGMENT_TYPE_PARAGRAPH
        label = f"{textual_match.group('kind').title()} {textual_match.group('num')}"
        return True, fragment_type, label

    numbered_match = NUMBERED_CLAUSE_RE.match(line)
    if numbered_match:
        label = numbered_match.group("label")
        fragment_type = FRAGMENT_TYPE_POINT if "." not in label else FRAGMENT_TYPE_SUBPOINT
        label_name = "Пункт" if fragment_type == FRAGMENT_TYPE_POINT else "Подпункт"
        return True, fragment_type, f"{label_name} {label}"

    return False, "heading_article_block", ""


def flush_heading_article_buffer(
    *,
    chunks: list[EvalChunk],
    buffer: list[str],
    fragment_type: str,
    label: str,
) -> None:
    block = "\n".join(buffer).strip()
    if not block:
        return
    index = len(chunks) + 1
    canonical_label = label or f"Heading/article block {index}"
    chunks.append(
        EvalChunk(
            chunk_index=index,
            text=block,
            fragment_type=fragment_type,
            heading=canonical_label,
            section_path=canonical_label,
            canonical_label=canonical_label,
            path_key=f"heading_article:{index}",
            text_hash=sha256_hex(block),
        )
    )


def heading_article_baseline(text: str) -> list[EvalChunk]:
    """Coarse rule baseline using only headings and numbered clauses.

    It does not detect Russian lettered subpoints such as ``а)`` and does not apply
    the production fallback strategy for weakly structured documents.
    """

    normalized = materialize_document_text(text, extension=".txt").normalized_text
    if not normalized:
        return []

    chunks: list[EvalChunk] = []
    buffer: list[str] = []
    current_type = "heading_article_block"
    current_label = ""
    found_boundary = False

    for raw_line in normalized.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue

        is_boundary, fragment_type, label = classify_heading_article_line(stripped)
        if is_boundary:
            found_boundary = True
            if buffer:
                flush_heading_article_buffer(
                    chunks=chunks,
                    buffer=buffer,
                    fragment_type=current_type,
                    label=current_label,
                )
                buffer = []
            current_type = fragment_type
            current_label = label

        buffer.append(stripped)

    if buffer:
        flush_heading_article_buffer(
            chunks=chunks,
            buffer=buffer,
            fragment_type=current_type,
            label=current_label,
        )

    if not found_boundary:
        # Deliberately coarse fallback for the baseline: one document-level block.
        return [
            EvalChunk(
                chunk_index=1,
                text=normalized,
                fragment_type=FRAGMENT_TYPE_FALLBACK_BLOCK,
                heading="Document-level fallback block",
                section_path="Document-level fallback block",
                canonical_label="Document-level fallback block",
                path_key="heading_article:fallback:document",
                text_hash=sha256_hex(normalized),
            )
        ]

    return chunks


def hybrid_structural(text: str) -> list[EvalChunk]:
    """Call the current production structural chunking implementation."""

    normalized = materialize_document_text(text, extension=".txt").normalized_text
    chunk_specs = chunk_by_structure_ru(normalized)
    return [
        EvalChunk(
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            fragment_type=chunk.fragment_type,
            heading=chunk.heading,
            section_path=chunk.section_path,
            canonical_label=chunk.canonical_label,
            path_key=chunk.path_key,
            text_hash=chunk.text_hash,
        )
        for chunk in chunk_specs
    ]


def load_annotation(pair_dir: Path) -> dict:
    return json.loads((pair_dir / "annotation.json").read_text(encoding="utf-8"))


def iter_expected_chunks(annotation: dict, version: str) -> list[ExpectedChunk]:
    expected: list[ExpectedChunk] = []
    for chunk in annotation.get("expected_chunks", []):
        chunk_version = str(chunk.get("version") or "new")
        if chunk_version != version:
            continue
        expected.append(
            ExpectedChunk(
                chunk_id=str(chunk.get("id") or ""),
                version=chunk_version,
                fragment=str(chunk.get("fragment") or ""),
                expected_type=str(chunk.get("expected_type") or ""),
                boundary_text=str(chunk.get("expected_boundary_text") or ""),
                is_key_chunk=bool(chunk.get("is_key_chunk")),
            )
        )
    return expected


def annotated_versions(annotation: dict) -> list[str]:
    versions = sorted({str(chunk.get("version") or "new") for chunk in annotation.get("expected_chunks", [])})
    return [version for version in ("old", "new") if version in versions]


def match_expected_chunks(
    *,
    expected_chunks: list[ExpectedChunk],
    found_chunks: list[EvalChunk],
) -> MatchResult:
    """Match expected chunks to found chunks using one-to-one containment.

    A boundary is correct if its normalized expected_boundary_text is contained in
    exactly one unused found chunk. If several expected chunks are merged into the
    same found chunk, only the first one can be counted as correct; the rest are
    recorded as merged/undersegmented. This keeps precision and recall bounded.
    """

    found_norm = {
        chunk.chunk_index: normalize_for_match(chunk.text) for chunk in found_chunks
    }
    found_len = {index: len(text) for index, text in found_norm.items()}
    used_found_indices: set[int] = set()

    matched_expected_ids: list[str] = []
    missed_expected_ids: list[str] = []
    merged_expected_ids: list[str] = []
    empty_boundary_ids: list[str] = []
    key_correct_boundaries = 0

    for expected in expected_chunks:
        boundary = normalize_for_match(expected.boundary_text)
        if not boundary:
            empty_boundary_ids.append(expected.chunk_id)
            missed_expected_ids.append(expected.chunk_id)
            continue

        candidate_indices = [
            chunk.chunk_index
            for chunk in found_chunks
            if boundary in found_norm.get(chunk.chunk_index, "")
        ]
        unused_candidates = [
            chunk_index
            for chunk_index in candidate_indices
            if chunk_index not in used_found_indices
        ]

        if unused_candidates:
            best_index = min(unused_candidates, key=lambda item: found_len[item])
            used_found_indices.add(best_index)
            matched_expected_ids.append(expected.chunk_id)
            if expected.is_key_chunk:
                key_correct_boundaries += 1
        elif candidate_indices:
            merged_expected_ids.append(expected.chunk_id)
            missed_expected_ids.append(expected.chunk_id)
        else:
            missed_expected_ids.append(expected.chunk_id)

    return MatchResult(
        correct_boundaries=len(matched_expected_ids),
        key_correct_boundaries=key_correct_boundaries,
        matched_expected_ids=matched_expected_ids,
        missed_expected_ids=missed_expected_ids,
        merged_expected_ids=merged_expected_ids,
        empty_boundary_ids=empty_boundary_ids,
    )


def build_notes(match_result: MatchResult) -> str:
    notes: list[str] = []
    if match_result.merged_expected_ids:
        notes.append("merged=" + ",".join(match_result.merged_expected_ids))
    if match_result.missed_expected_ids:
        missed_only = [
            item
            for item in match_result.missed_expected_ids
            if item not in match_result.merged_expected_ids
        ]
        if missed_only:
            notes.append("missed=" + ",".join(missed_only))
    if match_result.empty_boundary_ids:
        notes.append("empty_boundary=" + ",".join(match_result.empty_boundary_ids))
    return "; ".join(notes) if notes else "ok"


def evaluate_method(
    *,
    pair_id: str,
    document_version: str,
    title: str,
    method: MethodSpec,
    text: str,
    expected_chunks: list[ExpectedChunk],
) -> dict:
    found_chunks = method.chunker(text)
    match_result = match_expected_chunks(
        expected_chunks=expected_chunks,
        found_chunks=found_chunks,
    )
    expected_blocks = len(expected_chunks)
    found_blocks = len(found_chunks)
    correct_boundaries = match_result.correct_boundaries
    precision = safe_divide(correct_boundaries, found_blocks)
    recall = safe_divide(correct_boundaries, expected_blocks)
    f1 = calculate_f1(precision, recall)
    key_expected_blocks = sum(1 for chunk in expected_chunks if chunk.is_key_chunk)
    key_recall = safe_divide(match_result.key_correct_boundaries, key_expected_blocks)
    oversegmentation_ratio = safe_divide(found_blocks, expected_blocks)

    return {
        "pair_id": pair_id,
        "document_version": document_version,
        "title": title,
        "method": method.name,
        "expected_blocks": expected_blocks,
        "found_blocks": found_blocks,
        "correct_boundaries": correct_boundaries,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "oversegmentation_ratio": oversegmentation_ratio,
        "boundary_delta": found_blocks - expected_blocks,
        "key_expected_blocks": key_expected_blocks,
        "key_correct_boundaries": match_result.key_correct_boundaries,
        "key_recall": key_recall,
        "matched_expected_ids": ",".join(match_result.matched_expected_ids),
        "missed_expected_ids": ",".join(match_result.missed_expected_ids),
        "merged_expected_ids": ",".join(match_result.merged_expected_ids),
        "notes": build_notes(match_result),
    }


def round_metric(value: float) -> float:
    return round(value, 4)


def aggregate_rows(rows: list[dict], method_order: list[str]) -> dict[str, dict]:
    aggregate: dict[str, dict] = {}
    row_methods = {row["method"] for row in rows}
    methods = [method for method in method_order if method in row_methods]

    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        expected_total = sum(int(row["expected_blocks"]) for row in method_rows)
        found_total = sum(int(row["found_blocks"]) for row in method_rows)
        correct_total = sum(int(row["correct_boundaries"]) for row in method_rows)
        key_expected_total = sum(int(row["key_expected_blocks"]) for row in method_rows)
        key_correct_total = sum(int(row["key_correct_boundaries"]) for row in method_rows)

        micro_precision = safe_divide(correct_total, found_total)
        micro_recall = safe_divide(correct_total, expected_total)
        micro_f1 = calculate_f1(micro_precision, micro_recall)
        macro_precision = statistics.fmean(row["precision"] for row in method_rows)
        macro_recall = statistics.fmean(row["recall"] for row in method_rows)
        macro_f1 = statistics.fmean(row["f1"] for row in method_rows)
        macro_key_recall = statistics.fmean(row["key_recall"] for row in method_rows)

        aggregate[method] = {
            "documents_evaluated": len(method_rows),
            "micro": {
                "expected_blocks": expected_total,
                "found_blocks": found_total,
                "correct_boundaries": correct_total,
                "precision": round_metric(micro_precision),
                "recall": round_metric(micro_recall),
                "f1": round_metric(micro_f1),
                "key_expected_blocks": key_expected_total,
                "key_correct_boundaries": key_correct_total,
                "key_recall": round_metric(
                    safe_divide(key_correct_total, key_expected_total)
                ),
            },
            "macro": {
                "precision": round_metric(macro_precision),
                "recall": round_metric(macro_recall),
                "f1": round_metric(macro_f1),
                "key_recall": round_metric(macro_key_recall),
                "found_blocks_mean": round_metric(
                    statistics.fmean(row["found_blocks"] for row in method_rows)
                ),
                "expected_blocks_mean": round_metric(
                    statistics.fmean(row["expected_blocks"] for row in method_rows)
                ),
                "oversegmentation_ratio_mean": round_metric(
                    statistics.fmean(row["oversegmentation_ratio"] for row in method_rows)
                ),
            },
        }

    return aggregate


def write_results_csv(rows: list[dict]) -> None:
    fieldnames = [
        "pair_id",
        "document_version",
        "title",
        "method",
        "expected_blocks",
        "found_blocks",
        "correct_boundaries",
        "precision",
        "recall",
        "f1",
        "oversegmentation_ratio",
        "boundary_delta",
        "key_expected_blocks",
        "key_correct_boundaries",
        "key_recall",
        "matched_expected_ids",
        "missed_expected_ids",
        "merged_expected_ids",
        "notes",
    ]
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_CSV.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            printable_row = dict(row)
            for metric in (
                "precision",
                "recall",
                "f1",
                "oversegmentation_ratio",
                "key_recall",
            ):
                printable_row[metric] = f"{row[metric]:.4f}"
            writer.writerow(printable_row)


def build_corpus_audit(pair_dirs: Iterable[Path]) -> list[dict]:
    audit: list[dict] = []
    for pair_dir in pair_dirs:
        annotation = load_annotation(pair_dir)
        expected_chunks = annotation.get("expected_chunks", [])
        versions = {}
        for chunk in expected_chunks:
            version = str(chunk.get("version") or "new")
            versions[version] = versions.get(version, 0) + 1
        audit.append(
            {
                "pair_id": pair_dir.name,
                "title": annotation.get("title", ""),
                "old_file_exists": (pair_dir / str(annotation.get("old_file", "old.txt"))).exists(),
                "new_file_exists": (pair_dir / str(annotation.get("new_file", "new.txt"))).exists(),
                "annotation_exists": (pair_dir / "annotation.json").exists(),
                "expected_chunks": len(expected_chunks),
                "expected_changes": len(annotation.get("expected_changes", [])),
                "expected_chunk_versions": versions,
                "known_difficulties": annotation.get("known_difficulties", []),
                "usable_for_chunking_evaluation": bool(expected_chunks),
            }
        )
    return audit


def write_summary_json(rows: list[dict], method_specs: list[MethodSpec]) -> dict:
    pair_dirs = sorted(path for path in CORPUS_DIR.iterdir() if path.is_dir())
    aggregate = aggregate_rows(rows, [spec.name for spec in method_specs])
    evaluated_documents = sorted(
        {f"{row['pair_id']}:{row['document_version']}" for row in rows}
    )
    summary = {
        "experiment": "structural_chunking_evaluation",
        "phase": 14,
        "corpus_dir": str(CORPUS_DIR.relative_to(ROOT_DIR)),
        "pairs_found": len(pair_dirs),
        "evaluated_documents": len(evaluated_documents),
        "methods": {
            spec.name: {"role": spec.role, "description": spec.description}
            for spec in method_specs
        },
        "annotation_scope": (
            "expected_chunks are manually selected target/key chunks, not a complete "
            "full-document segmentation gold standard"
        ),
        "matching_rule": (
            "An expected chunk is counted as correct if its normalized "
            "expected_boundary_text is contained in one unused found chunk. If multiple "
            "expected chunks are merged into the same found chunk, only the first "
            "one-to-one match is counted and the rest are marked as merged."
        ),
        "aggregate_by_method": aggregate,
        "corpus_audit": build_corpus_audit(pair_dirs),
        "outputs": {
            "csv": str(RESULTS_CSV.relative_to(ROOT_DIR)),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT_DIR)),
            "f1_png": str(F1_PNG.relative_to(ROOT_DIR)),
        },
        "limitations": [
            "Expected chunks cover target/key fragments and do not annotate every valid chunk in each document.",
            "Precision is therefore a conservative proxy: non-annotated but valid chunks are counted in found_blocks.",
            "Boundary matching is based on normalized text containment, not expert semantic equivalence.",
            "The experiment evaluates structural chunking only and does not evaluate diff, significance, summary, or quiz generation.",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def write_f1_plot(summary: dict) -> None:
    import matplotlib.pyplot as plt

    methods = list(summary["aggregate_by_method"].keys())
    f1_values = [summary["aggregate_by_method"][method]["macro"]["f1"] for method in methods]

    plt.figure(figsize=(8, 4.5))
    plt.bar(methods, f1_values)
    plt.ylabel("Macro F1")
    plt.xlabel("Chunking method")
    plt.title("Structural chunking evaluation: average F1 by method")
    plt.ylim(0, 1)
    plt.xticks(rotation=15, ha="right")
    for index, value in enumerate(f1_values):
        plt.text(index, value + 0.02, f"{value:.3f}", ha="center")
    plt.tight_layout()
    F1_PNG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(F1_PNG, dpi=180)
    plt.close()


def print_console_summary(summary: dict) -> None:
    print("Structural chunking evaluation: PASS")
    print(f"Pairs found: {summary['pairs_found']}")
    print(f"Evaluated documents: {summary['evaluated_documents']}")
    print("\nAggregate macro metrics:")
    for method, payload in summary["aggregate_by_method"].items():
        macro = payload["macro"]
        micro = payload["micro"]
        print(
            "- {method}: macro P={p:.4f} R={r:.4f} F1={f:.4f}; "
            "micro P={mp:.4f} R={mr:.4f} F1={mf:.4f}".format(
                method=method,
                p=macro["precision"],
                r=macro["recall"],
                f=macro["f1"],
                mp=micro["precision"],
                mr=micro["recall"],
                mf=micro["f1"],
            )
        )
    print("\nOutputs:")
    for output in summary["outputs"].values():
        print(f"- {output}")


def main() -> int:
    if not CORPUS_DIR.exists():
        print(f"Missing evaluation corpus directory: {CORPUS_DIR}", file=sys.stderr)
        return 1

    method_specs = [
        MethodSpec(
            name=METHOD_PARAGRAPH,
            role="baseline",
            description="Naive split by empty-line paragraph boundaries.",
            chunker=paragraph_baseline,
        ),
        MethodSpec(
            name=METHOD_HEADING_ARTICLE,
            role="stronger baseline",
            description=(
                "Rule split by major headings and numeric clauses; no lettered "
                "subpoints and no production fallback strategy."
            ),
            chunker=heading_article_baseline,
        ),
        MethodSpec(
            name=METHOD_HYBRID,
            role="proposed method",
            description="Current production hybrid structural chunking via chunk_by_structure_ru.",
            chunker=hybrid_structural,
        ),
    ]

    rows: list[dict] = []
    pair_dirs = sorted(path for path in CORPUS_DIR.iterdir() if path.is_dir())
    for pair_dir in pair_dirs:
        annotation = load_annotation(pair_dir)
        for version in annotated_versions(annotation):
            expected_chunks = iter_expected_chunks(annotation, version)
            if not expected_chunks:
                continue
            source_file = pair_dir / f"{version}.txt"
            text = source_file.read_text(encoding="utf-8")
            for method in method_specs:
                rows.append(
                    evaluate_method(
                        pair_id=pair_dir.name,
                        document_version=version,
                        title=str(annotation.get("title") or ""),
                        method=method,
                        text=text,
                        expected_chunks=expected_chunks,
                    )
                )

    write_results_csv(rows)
    summary = write_summary_json(rows, method_specs)
    write_f1_plot(summary)
    print_console_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
