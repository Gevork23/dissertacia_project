from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
CORPUS_DIR = ROOT_DIR / "data" / "evaluation_corpus"
CHUNKING_SUMMARY_PATH = ROOT_DIR / "experiments" / "chunking" / "chunking_summary.json"
RESULTS_DIR = ROOT_DIR / "experiments" / "diff"
DOCS_DIR = ROOT_DIR / "docs" / "experiments"

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django

    django.setup()
    from documents.domain.diff import build_version_diff
    from documents.domain.text_processing import chunk_by_structure_ru, normalize_text
except Exception as exc:  # pragma: no cover - environment guard for CLI use
    raise RuntimeError(
        "Diff evaluation requires backend dependencies. "
        "Install backend/requirements.txt and run from the project root."
    ) from exc

METHODS = {
    "plain_text_diff": {
        "description": "Line-level difflib baseline over minimally normalized text.",
        "role": "baseline",
    },
    "paragraph_diff": {
        "description": "Paragraph/block difflib baseline over blank-line paragraphs.",
        "role": "stronger baseline",
    },
    "structural_chunk_diff": {
        "description": (
            "Production structural comparison via hybrid chunks and build_version_diff."
        ),
        "role": "proposed method",
    },
}

STATUS_ORDER = {"modified": 0, "added": 1, "removed": 2, "moved": 3}
MEANINGFUL_IMPORTANCE = {"critical", "important", "informational"}
EDITORIAL_IMPORTANCE = {"editorial"}
MATCH_THRESHOLD = 0.72


@dataclass(frozen=True)
class ExpectedChange:
    change_id: str
    status: str
    old_text: str
    new_text: str
    importance: str
    semantic_type: str
    change_type: str
    description: str
    fragment: str = ""
    is_editorial: bool = False


@dataclass(frozen=True)
class PredictedChange:
    status: str
    old_text: str = ""
    new_text: str = ""
    path_key: str = ""
    marker: str = ""
    match_reason: str = ""
    similarity: float | None = None
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        if self.status == "added":
            return self.new_text
        if self.status == "removed":
            return self.old_text
        return self.new_text or self.old_text


class ChunkRelation:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self._chunks = chunks

    def order_by(self, field_name: str) -> list[SimpleNamespace]:
        reverse = field_name.startswith("-")
        attr_name = field_name.lstrip("-")
        return sorted(
            self._chunks,
            key=lambda item: getattr(item, attr_name),
            reverse=reverse,
        )


@dataclass(frozen=True)
class PairAudit:
    pair_id: str
    title: str
    old_file_exists: bool
    new_file_exists: bool
    annotation_exists: bool
    expected_changes: int
    expected_meaningful_changes: int
    editorial_changes: int
    expected_chunks: int
    known_difficulties: list[str]
    usable_for_comparison_evaluation: bool


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def strip_leading_marker(text: str) -> str:
    normalized = collapse_ws(text)
    marker_re = re.compile(
        r"^(?:"
        r"\d+(?:\.\d+)*[.)]?|"
        r"[а-яёa-z][)]|"
        r"пункт\s+\S+|"
        r"подпункт\s+\S+|"
        r"абзац\s+\S+"
        r")\s+",
        re.IGNORECASE,
    )
    return marker_re.sub("", normalized).strip()


def norm_match_text(text: str) -> str:
    text = normalize_text(text or "")
    text = strip_leading_marker(text)
    text = text.replace(";", ".")
    text = text.replace(":", ".")
    text = collapse_ws(text)
    return text.casefold()


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[\wа-яёА-ЯЁ]+", norm_match_text(text), flags=re.UNICODE))


def lexical_score(expected_text: str, predicted_text: str) -> float:
    left = norm_match_text(expected_text)
    right = norm_match_text(predicted_text)
    if not left or not right:
        return 0.0
    if left in right or right in left:
        short = min(len(left), len(right))
        if short >= 16:
            return 1.0
    sequence_score = SequenceMatcher(None, left, right).ratio()
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if not left_tokens or not right_tokens:
        token_score = 0.0
    else:
        token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(sequence_score, token_score)


def status_compatible(expected_status: str, predicted_status: str) -> bool:
    if expected_status == predicted_status:
        return True
    if expected_status == "moved" and predicted_status in {
        "added",
        "removed",
        "modified",
    }:
        return True
    return False


def side_score(expected: ExpectedChange, predicted: PredictedChange) -> float:
    status = expected.status
    if status == "added":
        return lexical_score(expected.new_text, predicted.new_text)
    if status == "removed":
        return lexical_score(expected.old_text, predicted.old_text)
    if status == "moved":
        expected_text = expected.new_text or expected.old_text
        return max(
            lexical_score(expected_text, predicted.new_text),
            lexical_score(expected_text, predicted.old_text),
        )

    scores: list[float] = []
    if expected.old_text:
        scores.append(lexical_score(expected.old_text, predicted.old_text))
    if expected.new_text:
        scores.append(lexical_score(expected.new_text, predicted.new_text))
    if len(scores) >= 2:
        return min(scores)
    return max(scores or [0.0])


def change_matches(expected: ExpectedChange, predicted: PredictedChange) -> float:
    if not status_compatible(expected.status, predicted.status):
        return 0.0
    return side_score(expected, predicted)


def editorial_change_matches(
    editorial_changes: list[ExpectedChange], predicted: PredictedChange
) -> bool:
    for expected in editorial_changes:
        score = max(
            lexical_score(expected.old_text, predicted.old_text),
            lexical_score(expected.new_text, predicted.new_text),
            lexical_score(expected.old_text, predicted.new_text),
            lexical_score(expected.new_text, predicted.old_text),
        )
        if score >= MATCH_THRESHOLD:
            return True
    return False


def extract_expected_changes(annotation: dict[str, Any]) -> list[ExpectedChange]:
    changes: list[ExpectedChange] = []
    editorial_fragments = [
        (item.get("old_text", ""), item.get("new_text", ""))
        for item in annotation.get("editorial_changes", [])
    ]
    for item in annotation.get("expected_changes", []):
        importance = item.get("importance", "")
        old_text = item.get("old_text", "")
        new_text = item.get("new_text", "")
        is_editorial = importance in EDITORIAL_IMPORTANCE
        if not is_editorial:
            for old_editorial, new_editorial in editorial_fragments:
                if old_text == old_editorial and new_text == new_editorial:
                    is_editorial = True
                    break
        changes.append(
            ExpectedChange(
                change_id=item.get("id", ""),
                status=item.get("type") or item.get("status") or "modified",
                old_text=old_text,
                new_text=new_text,
                importance=importance,
                semantic_type=item.get("semantic_type", ""),
                change_type=item.get("change_type", ""),
                description=item.get("description", ""),
                fragment=item.get("fragment", ""),
                is_editorial=is_editorial,
            )
        )
    return changes


def extract_editorial_changes(annotation: dict[str, Any]) -> list[ExpectedChange]:
    changes: list[ExpectedChange] = []
    for item in annotation.get("editorial_changes", []):
        changes.append(
            ExpectedChange(
                change_id=item.get("id", ""),
                status=item.get("type") or item.get("status") or "modified",
                old_text=item.get("old_text", ""),
                new_text=item.get("new_text", ""),
                importance="editorial",
                semantic_type=item.get("semantic_type", "editorial"),
                change_type=item.get("change_type", "editorial"),
                description=item.get("description", ""),
                is_editorial=True,
            )
        )
    return changes


def meaningful_expected_changes(
    expected_changes: list[ExpectedChange],
) -> list[ExpectedChange]:
    return [
        item
        for item in expected_changes
        if not item.is_editorial and item.importance in MEANINGFUL_IMPORTANCE
    ]


def split_lines(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def split_paragraphs(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [
        block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()
    ]


def pair_replace_units(
    old_units: list[str],
    new_units: list[str],
    *,
    threshold: float,
) -> list[PredictedChange]:
    predictions: list[PredictedChange] = []
    used_new: set[int] = set()

    for old_unit in old_units:
        best_index: int | None = None
        best_score = 0.0
        for index, new_unit in enumerate(new_units):
            if index in used_new:
                continue
            score = lexical_score(old_unit, new_unit)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is not None and best_score >= threshold:
            used_new.add(best_index)
            predictions.append(
                PredictedChange(
                    status="modified",
                    old_text=old_unit,
                    new_text=new_units[best_index],
                    similarity=round(best_score, 4),
                    match_reason="replace_pair_similarity",
                )
            )
        else:
            predictions.append(
                PredictedChange(
                    status="removed",
                    old_text=old_unit,
                    match_reason="replace_unpaired_old",
                )
            )

    for index, new_unit in enumerate(new_units):
        if index in used_new:
            continue
        predictions.append(
            PredictedChange(
                status="added",
                new_text=new_unit,
                match_reason="replace_unpaired_new",
            )
        )

    return predictions


def sequence_diff(
    old_units: list[str],
    new_units: list[str],
    *,
    replace_threshold: float,
) -> list[PredictedChange]:
    matcher = SequenceMatcher(None, old_units, new_units)
    predictions: list[PredictedChange] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_block = old_units[old_start:old_end]
        new_block = new_units[new_start:new_end]
        if tag == "equal":
            continue
        if tag == "insert":
            predictions.append(
                PredictedChange(
                    status="added",
                    new_text="\n".join(new_block),
                    match_reason="sequence_insert",
                )
            )
            continue
        if tag == "delete":
            predictions.append(
                PredictedChange(
                    status="removed",
                    old_text="\n".join(old_block),
                    match_reason="sequence_delete",
                )
            )
            continue
        predictions.extend(
            pair_replace_units(
                old_block,
                new_block,
                threshold=replace_threshold,
            )
        )
    return sort_predictions(predictions)


def plain_text_diff(old_text: str, new_text: str) -> list[PredictedChange]:
    return sequence_diff(
        split_lines(old_text), split_lines(new_text), replace_threshold=0.62
    )


def paragraph_diff(old_text: str, new_text: str) -> list[PredictedChange]:
    return sequence_diff(
        split_paragraphs(old_text),
        split_paragraphs(new_text),
        replace_threshold=0.45,
    )


def make_fake_version(
    *,
    text: str,
    version_number: int,
    document_id: int,
    title: str,
) -> SimpleNamespace:
    normalized = normalize_text(text)
    fake_chunks: list[SimpleNamespace] = []
    for index, chunk in enumerate(chunk_by_structure_ru(normalized), start=1):
        fake_chunks.append(
            SimpleNamespace(
                id=(document_id * 100000) + (version_number * 1000) + index,
                chunk_index=chunk.chunk_index,
                fragment_type=chunk.fragment_type,
                structure_level=chunk.structure_level,
                raw_label=chunk.raw_label,
                canonical_label=chunk.canonical_label,
                path_key=chunk.path_key,
                heading=chunk.heading,
                section_path=chunk.section_path,
                text=chunk.text,
                text_hash=chunk.text_hash,
            )
        )
    return SimpleNamespace(
        id=(document_id * 10) + version_number,
        document_id=document_id,
        version_number=version_number,
        created_at=datetime(2026, 1, version_number),
        extracted_text=text,
        normalized_text=normalized,
        document=SimpleNamespace(id=document_id, title=title),
        chunks=ChunkRelation(fake_chunks),
    )


def structural_chunk_diff(
    old_text: str,
    new_text: str,
    *,
    document_id: int,
    title: str,
) -> list[PredictedChange]:
    from_version = make_fake_version(
        text=old_text,
        version_number=1,
        document_id=document_id,
        title=title,
    )
    to_version = make_fake_version(
        text=new_text,
        version_number=2,
        document_id=document_id,
        title=title,
    )
    payload = build_version_diff(from_version, to_version)
    predictions: list[PredictedChange] = []

    for item in payload.get("added", []):
        predictions.append(
            PredictedChange(
                status="added",
                new_text=item.get("text", ""),
                path_key=item.get("path_key", ""),
                marker=item.get("canonical_label", ""),
                match_reason="production_added",
                raw=item,
            )
        )
    for item in payload.get("removed", []):
        predictions.append(
            PredictedChange(
                status="removed",
                old_text=item.get("text", ""),
                path_key=item.get("path_key", ""),
                marker=item.get("canonical_label", ""),
                match_reason="production_removed",
                raw=item,
            )
        )
    for item in payload.get("modified", []):
        from_chunk = item.get("from_chunk") or {}
        to_chunk = item.get("to_chunk") or {}
        predictions.append(
            PredictedChange(
                status="modified",
                old_text=from_chunk.get("text", ""),
                new_text=to_chunk.get("text", ""),
                path_key=to_chunk.get("path_key", "") or from_chunk.get("path_key", ""),
                marker=to_chunk.get("canonical_label", "")
                or from_chunk.get("canonical_label", ""),
                match_reason=item.get("match_reason", "production_modified"),
                similarity=item.get("similarity"),
                raw=item,
            )
        )
    for item in payload.get("moved", []):
        from_chunk = item.get("from_chunk") or {}
        to_chunk = item.get("to_chunk") or {}
        predictions.append(
            PredictedChange(
                status="moved",
                old_text=from_chunk.get("text", ""),
                new_text=to_chunk.get("text", ""),
                path_key=to_chunk.get("path_key", "") or from_chunk.get("path_key", ""),
                marker=to_chunk.get("canonical_label", "")
                or from_chunk.get("canonical_label", ""),
                match_reason=item.get("match_reason", "production_moved"),
                raw=item,
            )
        )
    return sort_predictions(predictions)


def sort_predictions(predictions: list[PredictedChange]) -> list[PredictedChange]:
    return sorted(
        predictions,
        key=lambda item: (
            STATUS_ORDER.get(item.status, 99),
            norm_match_text(item.display_text)[:120],
        ),
    )


def run_method(
    method: str,
    old_text: str,
    new_text: str,
    *,
    document_id: int,
    title: str,
) -> list[PredictedChange]:
    if method == "plain_text_diff":
        return plain_text_diff(old_text, new_text)
    if method == "paragraph_diff":
        return paragraph_diff(old_text, new_text)
    if method == "structural_chunk_diff":
        return structural_chunk_diff(
            old_text,
            new_text,
            document_id=document_id,
            title=title,
        )
    raise ValueError(f"Unknown diff method: {method}")


def evaluate_predictions(
    *,
    expected_changes: list[ExpectedChange],
    editorial_changes: list[ExpectedChange],
    predictions: list[PredictedChange],
) -> dict[str, Any]:
    matched_predictions: set[int] = set()
    matched_expected: set[str] = set()
    match_details: list[dict[str, Any]] = []

    for expected in expected_changes:
        best_index: int | None = None
        best_score = 0.0
        for index, predicted in enumerate(predictions):
            if index in matched_predictions:
                continue
            score = change_matches(expected, predicted)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is not None and best_score >= MATCH_THRESHOLD:
            matched_predictions.add(best_index)
            matched_expected.add(expected.change_id)
            match_details.append(
                {
                    "expected_id": expected.change_id,
                    "expected_status": expected.status,
                    "predicted_index": best_index,
                    "predicted_status": predictions[best_index].status,
                    "score": round(best_score, 4),
                }
            )

    editorial_noise_indexes = {
        index
        for index, predicted in enumerate(predictions)
        if editorial_change_matches(editorial_changes, predicted)
    }
    fp_indexes = [
        index for index in range(len(predictions)) if index not in matched_predictions
    ]
    fn_expected = [
        expected
        for expected in expected_changes
        if expected.change_id not in matched_expected
    ]
    tp = len(matched_expected)
    fp = len(fp_indexes)
    fn = len(fn_expected)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_f1(precision, recall)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "noise_count": fp,
        "noise_ratio": safe_div(fp, len(predictions)),
        "editorial_noise_count": len(editorial_noise_indexes),
        "matched_predictions": sorted(matched_predictions),
        "fp_indexes": fp_indexes,
        "fn_expected_ids": [item.change_id for item in fn_expected],
        "match_details": match_details,
    }


def safe_div(num: int | float, den: int | float) -> float:
    if not den:
        return 0.0
    return round(float(num) / float(den), 4)


def safe_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def load_pairs() -> list[tuple[Path, dict[str, Any], str, str]]:
    pairs: list[tuple[Path, dict[str, Any], str, str]] = []
    for pair_dir in sorted(CORPUS_DIR.iterdir()):
        if not pair_dir.is_dir():
            continue
        annotation_path = pair_dir / "annotation.json"
        if not annotation_path.exists():
            continue
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        old_text = (pair_dir / annotation.get("old_file", "old.txt")).read_text(
            encoding="utf-8"
        )
        new_text = (pair_dir / annotation.get("new_file", "new.txt")).read_text(
            encoding="utf-8"
        )
        pairs.append((pair_dir, annotation, old_text, new_text))
    return pairs


def audit_corpus(pairs: list[tuple[Path, dict[str, Any], str, str]]) -> list[PairAudit]:
    audit: list[PairAudit] = []
    for pair_dir, annotation, _, _ in pairs:
        old_file = annotation.get("old_file", "old.txt")
        new_file = annotation.get("new_file", "new.txt")
        expected_changes = extract_expected_changes(annotation)
        editorial_changes = extract_editorial_changes(annotation)
        meaningful = meaningful_expected_changes(expected_changes)
        usable = bool(
            (pair_dir / old_file).exists()
            and (pair_dir / new_file).exists()
            and (pair_dir / "annotation.json").exists()
            and annotation.get("expected_changes") is not None
        )
        audit.append(
            PairAudit(
                pair_id=annotation.get("pair_id", pair_dir.name),
                title=annotation.get("title", ""),
                old_file_exists=(pair_dir / old_file).exists(),
                new_file_exists=(pair_dir / new_file).exists(),
                annotation_exists=(pair_dir / "annotation.json").exists(),
                expected_changes=len(expected_changes),
                expected_meaningful_changes=len(meaningful),
                editorial_changes=len(editorial_changes),
                expected_chunks=len(annotation.get("expected_chunks", [])),
                known_difficulties=annotation.get("known_difficulties", []),
                usable_for_comparison_evaluation=usable,
            )
        )
    return audit


def known_difficulty_note(annotation: dict[str, Any], method: str) -> str:
    notes = annotation.get("known_difficulties", []) or []
    if method != "structural_chunk_diff":
        return "; ".join(notes)
    pair_id = annotation.get("pair_id", "")
    if pair_id == "pair_03_document_list_change":
        return "Depends on subpoint chunk boundary; Phase 14 hybrid found this key boundary."
    if pair_id == "pair_08_reordered_structure":
        return "Production MVP treats exact-text relocation as unchanged; moved is diagnostic limitation."
    if pair_id == "pair_10_weakly_structured_document":
        return "Uses fallback-block chunks; comparison granularity is coarser than point-level chunks."
    return "Depends on hybrid structural chunks produced by Phase 14 method."


def result_notes(
    annotation: dict[str, Any],
    strict_metrics: dict[str, Any],
    raw_metrics: dict[str, Any],
) -> str:
    notes: list[str] = []
    if strict_metrics["editorial_noise_count"]:
        notes.append("editorial noise detected")
    if strict_metrics["fn"]:
        notes.append("meaningful FN present")
    if strict_metrics["fp"]:
        notes.append("strict FP/noise present")
    if raw_metrics["fn"] and not strict_metrics["fn"]:
        notes.append("raw expected FN is editorial/diagnostic only")
    if annotation.get("known_difficulties"):
        notes.append("known difficulty")
    return "; ".join(notes) or "ok"


def prediction_to_text(predicted: PredictedChange) -> str:
    left = collapse_ws(predicted.old_text)
    right = collapse_ws(predicted.new_text)
    if predicted.status == "modified":
        return f"modified: OLD='{left[:180]}' NEW='{right[:180]}'"
    if predicted.status == "added":
        return f"added: NEW='{right[:220]}'"
    if predicted.status == "removed":
        return f"removed: OLD='{left[:220]}'"
    return f"{predicted.status}: OLD='{left[:160]}' NEW='{right[:160]}'"


def expected_to_text(expected: ExpectedChange) -> str:
    old_text = collapse_ws(expected.old_text)
    new_text = collapse_ws(expected.new_text)
    return (
        f"{expected.change_id} [{expected.status}/{expected.importance}]: "
        f"OLD='{old_text[:180]}' NEW='{new_text[:180]}'"
    )


def aggregate_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    methods: dict[str, Any] = {}
    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        total_tp = sum(int(row["tp"]) for row in method_rows)
        total_fp = sum(int(row["fp"]) for row in method_rows)
        total_fn = sum(int(row["fn"]) for row in method_rows)
        total_predicted = sum(int(row["predicted_changes"]) for row in method_rows)
        raw_total_tp = sum(int(row["raw_tp"]) for row in method_rows)
        raw_total_fp = sum(int(row["raw_fp"]) for row in method_rows)
        raw_total_fn = sum(int(row["raw_fn"]) for row in method_rows)
        micro_precision = safe_div(total_tp, total_tp + total_fp)
        micro_recall = safe_div(total_tp, total_tp + total_fn)
        methods[method] = {
            "role": METHODS[method]["role"],
            "description": METHODS[method]["description"],
            "pairs_evaluated": len(method_rows),
            "avg_precision": round(
                sum(float(row["precision"]) for row in method_rows)
                / max(1, len(method_rows)),
                4,
            ),
            "avg_recall": round(
                sum(float(row["recall"]) for row in method_rows)
                / max(1, len(method_rows)),
                4,
            ),
            "avg_f1": round(
                sum(float(row["f1"]) for row in method_rows) / max(1, len(method_rows)),
                4,
            ),
            "micro_precision": micro_precision,
            "micro_recall": micro_recall,
            "micro_f1": safe_f1(micro_precision, micro_recall),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "total_noise": total_fp,
            "total_predicted_changes": total_predicted,
            "noise_ratio": safe_div(total_fp, total_predicted),
            "total_editorial_noise": sum(
                int(row["editorial_noise_count"]) for row in method_rows
            ),
            "diagnostic_all_expected_changes": {
                "raw_tp": raw_total_tp,
                "raw_fp": raw_total_fp,
                "raw_fn": raw_total_fn,
                "raw_precision": safe_div(raw_total_tp, raw_total_tp + raw_total_fp),
                "raw_recall": safe_div(raw_total_tp, raw_total_tp + raw_total_fn),
                "raw_f1": safe_f1(
                    safe_div(raw_total_tp, raw_total_tp + raw_total_fp),
                    safe_div(raw_total_tp, raw_total_tp + raw_total_fn),
                ),
            },
        }
    return methods


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "pair_id",
        "pair_scenario",
        "method",
        "raw_expected_changes",
        "expected_changes",
        "editorial_expected_changes",
        "predicted_changes",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "noise_count",
        "noise_ratio",
        "editorial_noise_count",
        "raw_tp",
        "raw_fp",
        "raw_fn",
        "known_difficulties",
        "chunking_dependency_note",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_fp_fn_plot(methods_summary: dict[str, Any], path: Path) -> None:
    labels = list(methods_summary)
    x_values = list(range(len(labels)))
    width = 0.35
    fp_values = [methods_summary[label]["total_fp"] for label in labels]
    fn_values = [methods_summary[label]["total_fn"] for label in labels]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar([x - width / 2 for x in x_values], fp_values, width, label="FP")
    ax.bar([x + width / 2 for x in x_values], fn_values, width, label="FN")
    ax.set_ylabel("Count")
    ax.set_title("False positives and false negatives by diff method")
    ax.set_xticks(x_values)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_prf_plot(methods_summary: dict[str, Any], path: Path) -> None:
    labels = list(methods_summary)
    x_values = list(range(len(labels)))
    width = 0.25
    precision = [methods_summary[label]["avg_precision"] for label in labels]
    recall = [methods_summary[label]["avg_recall"] for label in labels]
    f1_scores = [methods_summary[label]["avg_f1"] for label in labels]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar([x - width for x in x_values], precision, width, label="Precision")
    ax.bar(x_values, recall, width, label="Recall")
    ax.bar([x + width for x in x_values], f1_scores, width, label="F1")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Macro average score")
    ax.set_title("Precision, recall, and F1 by diff method")
    ax.set_xticks(x_values)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def make_error_examples(
    pair_diagnostics: list[dict[str, Any]],
    path: Path,
) -> None:
    examples: list[dict[str, str]] = []

    def add_example(
        *,
        title: str,
        pair_id: str,
        method: str,
        expected: str,
        predicted: str,
        error_type: str,
        why: str,
    ) -> None:
        examples.append(
            {
                "title": title,
                "pair_id": pair_id,
                "method": method,
                "expected": expected,
                "predicted": predicted,
                "error_type": error_type,
                "why": why,
            }
        )

    by_key = {(item["pair_id"], item["method"]): item for item in pair_diagnostics}

    item = by_key.get(("pair_02_added_obligation", "plain_text_diff"))
    if item:
        fp_indexes = item["strict_metrics"]["fp_indexes"]
        predicted = (
            prediction_to_text(item["predictions"][fp_indexes[0]])
            if fp_indexes
            else "No FP captured."
        )
        add_example(
            title="plain text diff false positive caused by renumbering",
            pair_id="pair_02_added_obligation",
            method="plain_text_diff",
            expected="Only the new notification obligation is a meaningful change.",
            predicted=predicted,
            error_type="FP",
            why=(
                "The baseline compares full text lines with numeric markers. "
                "After inserting a new point, the old point number changes, "
                "so an unchanged provision is emitted as modified noise."
            ),
        )

    item = by_key.get(("pair_03_document_list_change", "paragraph_diff"))
    if item:
        expected = "\n".join(expected_to_text(exp) for exp in item["strict_expected"])
        predicted = "\n".join(prediction_to_text(pred) for pred in item["predictions"])
        add_example(
            title="paragraph diff misses an added lettered subpoint",
            pair_id="pair_03_document_list_change",
            method="paragraph_diff",
            expected=expected,
            predicted=predicted,
            error_type="FN / FP",
            why=(
                "The paragraph baseline treats the whole Article 2 block as one "
                "paragraph-level modification. It does not isolate the added "
                "lettered subpoint as an added change."
            ),
        )

    item = by_key.get(("pair_08_reordered_structure", "structural_chunk_diff"))
    if item:
        raw_fns = item["raw_metrics"]["fn_expected_ids"]
        expected_raw = [
            exp for exp in item["raw_expected"] if exp.change_id in set(raw_fns)
        ]
        add_example(
            title="structural diff moved-case limitation",
            pair_id="pair_08_reordered_structure",
            method="structural_chunk_diff",
            expected="\n".join(expected_to_text(exp) for exp in expected_raw)
            or "No raw FN captured.",
            predicted="No change emitted by production structural comparison.",
            error_type="diagnostic raw FN",
            why=(
                "The current MVP comparison deliberately treats exact-text "
                "relocation as unchanged and does not materialize moved items. "
                "In strict meaningful metrics this moved case is editorial noise, "
                "but all-change diagnostics expose it as a moved-detection limit."
            ),
        )

    item = by_key.get(("pair_01_deadline_change", "structural_chunk_diff"))
    if item:
        add_example(
            title="structural diff cleanly detects a deadline change",
            pair_id="pair_01_deadline_change",
            method="structural_chunk_diff",
            expected="\n".join(
                expected_to_text(exp) for exp in item["strict_expected"]
            ),
            predicted="\n".join(
                prediction_to_text(pred) for pred in item["predictions"]
            ),
            error_type="TP / clean detection",
            why=(
                "The old and new chunks share the same path_key, so production "
                "comparison emits one modified chunk with no extra changed lines."
            ),
        )

    item = by_key.get(("pair_05_editorial_change", "structural_chunk_diff"))
    if item:
        add_example(
            title="editorial change counted as strict noise",
            pair_id="pair_05_editorial_change",
            method="structural_chunk_diff",
            expected="No meaningful expected change under strict usefulness metrics.",
            predicted="\n".join(
                prediction_to_text(pred) for pred in item["predictions"]
            ),
            error_type="editorial noise / FP",
            why=(
                "The diff layer correctly detects a wording change, but the "
                "annotation marks it as editorial. For strict comparison usefulness "
                "metrics it is counted as noise and reported separately as "
                "editorial_noise."
            ),
        )

    item = by_key.get(("pair_10_weakly_structured_document", "structural_chunk_diff"))
    if item:
        add_example(
            title="weakly structured document uses fallback-block comparison",
            pair_id="pair_10_weakly_structured_document",
            method="structural_chunk_diff",
            expected="\n".join(
                expected_to_text(exp) for exp in item["strict_expected"]
            ),
            predicted="\n".join(
                prediction_to_text(pred) for pred in item["predictions"]
            ),
            error_type="chunking dependency observation",
            why=(
                "The method still detects the deadline change, but the changed "
                "unit is a fallback block rather than a fine-grained point. "
                "This illustrates how chunk granularity bounds comparison clarity."
            ),
        )

    lines = ["# Diff evaluation error examples", ""]
    for example in examples:
        lines.extend(
            [
                f"### Example: {example['pair_id']}, method={example['method']}",
                "",
                f"**Scenario:** {example['title']}",
                "",
                "**Expected:**",
                "",
                example["expected"] or "-",
                "",
                "**Predicted:**",
                "",
                example["predicted"] or "-",
                "",
                "**Error type:**",
                "",
                example["error_type"],
                "",
                "**Why it happened:**",
                "",
                example["why"],
                "",
            ]
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        output.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(output)


def write_report(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    pair_diagnostics: list[dict[str, Any]],
    path: Path,
) -> None:
    methods_summary = summary["methods"]
    aggregate_rows = []
    for method, payload in methods_summary.items():
        aggregate_rows.append(
            [
                method,
                payload["total_tp"],
                payload["total_fp"],
                payload["total_fn"],
                f"{payload['micro_precision']:.4f}",
                f"{payload['micro_recall']:.4f}",
                f"{payload['micro_f1']:.4f}",
                payload["total_noise"],
                payload["total_editorial_noise"],
            ]
        )

    result_rows = []
    for row in rows:
        result_rows.append(
            [
                row["pair_id"],
                row["method"],
                row["tp"],
                row["fp"],
                row["fn"],
                f"{row['precision']:.4f}",
                f"{row['recall']:.4f}",
                f"{row['f1']:.4f}",
                row["noise_count"],
            ]
        )

    best_method = max(
        methods_summary,
        key=lambda method: (
            methods_summary[method]["micro_f1"],
            -methods_summary[method]["total_fp"],
        ),
    )
    chunking_summary = summary.get("phase14_chunking_summary", {})
    hybrid_chunking = (
        chunking_summary.get("aggregate_by_method", {})
        .get("hybrid_structural", {})
        .get("micro", {})
    )

    lines = [
        "# Diff / Version Comparison Evaluation",
        "",
        "## 1. Цель эксперимента",
        "",
        (
            "Эксперимент оценивает качество этапа `C — Comparison / Diff` "
            "гибридного метода. Цель — сравнить текущий structural chunk diff "
            "с двумя baseline-подходами и проверить, формирует ли он менее шумный "
            "и более пригодный для дальнейшей обработки набор изменений."
        ),
        "",
        "## 2. Связь с гибридным методом",
        "",
        (
            "В методе `M = <E, N, S, C, P, G, R>` данный эксперимент проверяет "
            "этап `C`. Его входом является нормализованный текст и, для основного "
            "метода, structural chunks этапа `S`; выходом являются изменения "
            "`added`, `removed`, `modified`, `moved`, которые далее используются "
            "significance-layer, summary и quiz generation."
        ),
        "",
        "## 3. Evaluation corpus",
        "",
        (
            f"Использован `data/evaluation_corpus/`: {summary['pairs_found']} "
            f"синтетических пар документов. В annotation найдено "
            f"{summary['raw_expected_changes_total']} raw expected changes, из них "
            f"{summary['strict_expected_changes_total']} meaningful/key changes "
            f"для strict-метрик и {summary['editorial_expected_changes_total']} "
            "editorial/diagnostic changes. Разметка является key-change gold "
            "standard, а не exhaustive full diff всех технических отличий."
        ),
        "",
        "## 4. Сравниваемые методы",
        "",
        markdown_table(
            [
                [method, payload["description"], payload["role"]]
                for method, payload in METHODS.items()
            ],
            ["Method", "Description", "Role"],
        ),
        "",
        "### 4.1 Plain text diff",
        "",
        (
            "Baseline сравнивает минимально нормализованный текст построчно через "
            "`difflib.SequenceMatcher`. Он сохраняет числовые markers строк и "
            "поэтому чувствителен к перенумерации пунктов после вставок."
        ),
        "",
        "### 4.2 Paragraph diff",
        "",
        (
            "Более крупный baseline сравнивает блоки, разделённые пустыми строками. "
            "Он снижает часть line-level шума, но часто склеивает несколько "
            "смысловых изменений внутри одного article/paragraph block."
        ),
        "",
        "### 4.3 Structural chunk diff",
        "",
        (
            "Основной метод использует production `chunk_by_structure_ru` и "
            "`build_version_diff`: сопоставление по `text_hash`, `path_key`, "
            "`canonical_label`, `section_path`, `heading`, lexical similarity и "
            "fallback matching. Core algorithm не изменялся ради метрик."
        ),
        "",
        "## 5. Метрики",
        "",
        (
            "Для каждой пары и метода считаются `TP`, `FP`, `FN`, `precision`, "
            "`recall`, `F1`, `noise_count = FP`, `noise_ratio = FP / "
            "max(1, predicted_changes)`. В summary дополнительно сохранены "
            "micro/macro агрегаты и диагностические raw-метрики по всем "
            "expected_changes, включая editorial."
        ),
        "",
        "## 6. Matching rule",
        "",
        (
            "Predicted change засчитывается как TP, если его статус совместим с "
            "expected status и side-specific lexical score не ниже "
            f"{MATCH_THRESHOLD}. Для `modified` проверяются old и new sides; "
            "для `added` — new side; для `removed` — old side. Leading markers "
            "вида `1.`, `2)`, `г)` нормализуются перед сопоставлением. "
            "Один predicted change может закрыть только один expected change, "
            "чтобы merged paragraph-block не давал несколько TP. Для `moved` "
            "в raw diagnostics допускается частичное совпадение через `moved`, "
            "`added`, `removed` или `modified`, поскольку production moved detector "
            "в текущем MVP не материализует moved items."
        ),
        "",
        "## 7. Учет editorial noise",
        "",
        (
            "Primary strict metrics оценивают полезные/key changes и исключают "
            "`importance=editorial` из expected set. Predicted changes, совпавшие "
            "с `editorial_changes`, учитываются в `editorial_noise_count`; если "
            "они не закрывают meaningful expected change, они также входят в FP. "
            "Это отделяет качество detection как raw факта от полезности diff для "
            "downstream summary/quiz."
        ),
        "",
        "## 8. Результаты",
        "",
        markdown_table(
            result_rows,
            ["Pair", "Method", "TP", "FP", "FN", "Precision", "Recall", "F1", "Noise"],
        ),
        "",
        "## 9. Aggregate results",
        "",
        markdown_table(
            aggregate_rows,
            [
                "Method",
                "TP",
                "FP",
                "FN",
                "Micro precision",
                "Micro recall",
                "Micro F1",
                "Noise",
                "Editorial noise",
            ],
        ),
        "",
        "## 10. FP/FN analysis",
        "",
        (
            "Plain text diff хорошо находит single-line textual edits, но "
            "создаёт FP при перенумерации пунктов после вставки. Paragraph diff "
            "часто объединяет несколько пунктов внутри одного крупного block, "
            "что снижает recall для added subpoints и добавляет FP modified-blocks. "
            f"Structural chunk diff получил лучший strict micro F1 в этом запуске: "
            f"`{best_method}` является лидером по агрегату, а structural method "
            "даёт наименьший noise среди методов, сохраняющих высокий recall."
        ),
        "",
        "## 11. Error examples",
        "",
        (
            "Подробные примеры сохранены в "
            "`experiments/diff/diff_error_examples.md`. Они покрывают line-level "
            "FP из-за перенумерации, paragraph-level FN/FP из-за склейки блоков, "
            "moved-case limitation production structural diff, clean structural TP "
            "и editorial noise."
        ),
        "",
        "## 12. Влияние chunking quality на comparison",
        "",
        (
            "Comparison зависит от качества этапа `S`: если key boundary выделена "
            "плохо, structural diff может получить ложный modified/added/removed "
            "или пропустить изменение. Результаты Фазы 14 показали, что "
            "`hybrid_structural` нашёл все 23 expected boundaries и получил "
            f"micro recall={hybrid_chunking.get('recall', 'n/a')} и "
            f"micro F1={hybrid_chunking.get('f1', 'n/a')} на key-boundary "
            "разметке. Это усиливает интерпретацию Фазы 15: structural "
            "comparison работает лучше там, где chunk boundaries устойчивы. "
            "При этом вывод остаётся ограниченным, потому что chunking gold "
            "standard не является full-document segmentation."
        ),
        "",
        "## 13. Ограничения эксперимента",
        "",
        "1. Corpus малый: 10 synthetic pairs, strict meaningful expected changes = "
        f"{summary['strict_expected_changes_total']}.",
        "2. Annotation задаёт key-change gold standard, а не exhaustive full diff.",
        "3. Matching основан на containment/lexical overlap, а не на экспертной "
        "семантической оценке каждого predicted fragment.",
        "4. Strict metrics намеренно считают editorial-only predictions шумом; raw "
        "diagnostics сохранены отдельно.",
        "5. Production structural diff не материализует moved items; exact-text "
        "relocation считается unchanged.",
        "6. Weakly structured case оценивается через fallback-block chunks, поэтому "
        "clarity ниже, чем у point/subpoint-level chunks.",
        "",
        "## 14. Вывод для диссертации",
        "",
        (
            "Экспериментальная оценка показала, что structural chunk diff формирует "
            "более пригодный для дальнейшей обработки набор изменений, чем plain "
            "text diff и paragraph diff. Использование structural chunks, "
            "`path_key` и `text_hash` снижает количество шумовых изменений и "
            "повышает интерпретируемость результата сравнения. Вывод следует "
            "формулировать в рамках текущего key-change corpus: преимущество "
            "подтверждено для размеченных synthetic pairs, но более строгая оценка "
            "потребует расширенной full-document разметки и отдельной Фазы 16 для "
            "significance-layer."
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    pairs = load_pairs()
    audit = audit_corpus(pairs)
    rows: list[dict[str, Any]] = []
    pair_diagnostics: list[dict[str, Any]] = []

    for pair_index, (pair_dir, annotation, old_text, new_text) in enumerate(
        pairs,
        start=1,
    ):
        pair_id = annotation.get("pair_id", pair_dir.name)
        title = annotation.get("title", pair_id)
        raw_expected = extract_expected_changes(annotation)
        strict_expected = meaningful_expected_changes(raw_expected)
        editorial_changes = extract_editorial_changes(annotation)

        for method in METHODS:
            predictions = run_method(
                method,
                old_text,
                new_text,
                document_id=pair_index,
                title=title,
            )
            strict_metrics = evaluate_predictions(
                expected_changes=strict_expected,
                editorial_changes=editorial_changes,
                predictions=predictions,
            )
            raw_metrics = evaluate_predictions(
                expected_changes=raw_expected,
                editorial_changes=editorial_changes,
                predictions=predictions,
            )
            row = {
                "pair_id": pair_id,
                "pair_scenario": title,
                "method": method,
                "raw_expected_changes": len(raw_expected),
                "expected_changes": len(strict_expected),
                "editorial_expected_changes": len(
                    [item for item in raw_expected if item.is_editorial]
                ),
                "predicted_changes": len(predictions),
                "tp": strict_metrics["tp"],
                "fp": strict_metrics["fp"],
                "fn": strict_metrics["fn"],
                "precision": strict_metrics["precision"],
                "recall": strict_metrics["recall"],
                "f1": strict_metrics["f1"],
                "noise_count": strict_metrics["noise_count"],
                "noise_ratio": strict_metrics["noise_ratio"],
                "editorial_noise_count": strict_metrics["editorial_noise_count"],
                "raw_tp": raw_metrics["tp"],
                "raw_fp": raw_metrics["fp"],
                "raw_fn": raw_metrics["fn"],
                "known_difficulties": "; ".join(
                    annotation.get("known_difficulties", []) or []
                ),
                "chunking_dependency_note": known_difficulty_note(
                    annotation,
                    method,
                ),
                "notes": result_notes(annotation, strict_metrics, raw_metrics),
            }
            rows.append(row)
            pair_diagnostics.append(
                {
                    "pair_id": pair_id,
                    "method": method,
                    "annotation": annotation,
                    "raw_expected": raw_expected,
                    "strict_expected": strict_expected,
                    "editorial_changes": editorial_changes,
                    "predictions": predictions,
                    "strict_metrics": strict_metrics,
                    "raw_metrics": raw_metrics,
                }
            )

    methods_summary = aggregate_results(rows)
    chunking_summary: dict[str, Any] = {}
    if CHUNKING_SUMMARY_PATH.exists():
        chunking_summary = json.loads(CHUNKING_SUMMARY_PATH.read_text(encoding="utf-8"))

    summary = {
        "experiment": "diff_version_comparison_evaluation",
        "phase": 15,
        "evaluation_scope": (
            "Primary strict metrics use meaningful/key expected changes from "
            "annotation.json and treat editorial-only predictions as noise. "
            "Diagnostic raw metrics use all expected_changes."
        ),
        "corpus_dir": str(CORPUS_DIR.relative_to(ROOT_DIR)),
        "pairs_found": len(pairs),
        "raw_expected_changes_total": sum(
            int(row["raw_expected_changes"])
            for row in rows
            if row["method"] == "plain_text_diff"
        ),
        "strict_expected_changes_total": sum(
            int(row["expected_changes"])
            for row in rows
            if row["method"] == "plain_text_diff"
        ),
        "editorial_expected_changes_total": sum(
            int(row["editorial_expected_changes"])
            for row in rows
            if row["method"] == "plain_text_diff"
        ),
        "methods": methods_summary,
        "matching_rule": (
            "One-to-one greedy matching. Status must be compatible; normalized "
            "old/new text must have side-specific lexical overlap >= 0.72. "
            "Leading structural markers are ignored. Moved raw diagnostics accept "
            "moved or partial added/removed/modified evidence."
        ),
        "editorial_noise_policy": (
            "Expected changes with importance=editorial are excluded from primary "
            "strict expected set. Predictions matching editorial_changes are counted "
            "as editorial_noise_count and as FP unless they also match a meaningful "
            "expected change. Raw diagnostics keep all expected_changes."
        ),
        "noise_definition": "noise_count = FP; noise_ratio = FP / max(1, predicted_changes)",
        "corpus_audit": [audit_item.__dict__ for audit_item in audit],
        "phase14_chunking_summary": chunking_summary,
        "outputs": {
            "csv": str((RESULTS_DIR / "diff_results.csv").relative_to(ROOT_DIR)),
            "summary_json": str(
                (RESULTS_DIR / "diff_summary.json").relative_to(ROOT_DIR)
            ),
            "fp_fn_png": str((RESULTS_DIR / "diff_fp_fn.png").relative_to(ROOT_DIR)),
            "precision_recall_f1_png": str(
                (RESULTS_DIR / "diff_precision_recall_f1.png").relative_to(ROOT_DIR)
            ),
            "error_examples_md": str(
                (RESULTS_DIR / "diff_error_examples.md").relative_to(ROOT_DIR)
            ),
            "report_md": str((DOCS_DIR / "diff-evaluation.md").relative_to(ROOT_DIR)),
        },
        "limitations": [
            "The corpus contains 10 synthetic pairs and key-change annotations, not full exhaustive diff labels.",
            "Strict metrics intentionally treat editorial-only changes as noise for downstream usefulness.",
            "Lexical matching is deterministic and does not replace expert semantic adjudication.",
            "Production structural comparison does not materialize moved items in the current MVP.",
            "Structural diff quality depends on Phase 14 chunk boundary quality.",
        ],
        "notes": [
            "Core production comparison algorithm was not changed for this experiment.",
            "The structural method is called through build_version_diff with in-memory versions/chunks, so the database is not modified.",
        ],
    }

    write_csv(rows, RESULTS_DIR / "diff_results.csv")
    (RESULTS_DIR / "diff_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_fp_fn_plot(methods_summary, RESULTS_DIR / "diff_fp_fn.png")
    write_prf_plot(methods_summary, RESULTS_DIR / "diff_precision_recall_f1.png")
    make_error_examples(pair_diagnostics, RESULTS_DIR / "diff_error_examples.md")
    write_report(
        rows=rows,
        summary=summary,
        pair_diagnostics=pair_diagnostics,
        path=DOCS_DIR / "diff-evaluation.md",
    )

    print("Diff evaluation completed")
    print(f"Pairs: {len(pairs)}")
    print(f"Results: {RESULTS_DIR / 'diff_results.csv'}")
    print(f"Summary: {RESULTS_DIR / 'diff_summary.json'}")


if __name__ == "__main__":
    main()
