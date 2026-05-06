#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT_DIR / "data" / "evaluation_corpus"

REQUIRED_TOP_LEVEL_FIELDS = {
    "pair_id",
    "title",
    "document_type",
    "purpose",
    "old_file",
    "new_file",
    "expected_changes",
    "expected_significance",
    "editorial_changes",
    "expected_chunks",
    "expected_summary_topics",
    "expected_quiz_topics",
}

ALLOWED_IMPORTANCE = {
    "critical",
    "important",
    "informational",
    "editorial",
    "not_evaluated",
}

ALLOWED_CHANGE_TYPES = {
    "added",
    "removed",
    "modified",
    "moved",
}

ALLOWED_CHUNK_TYPES = {
    "title",
    "preamble",
    "section",
    "chapter",
    "article",
    "point",
    "subpoint",
    "paragraph",
    "fallback_block",
}

PII_PATTERNS = {
    "passport_like": re.compile(r"\b\d{4}\s+\d{6}\b"),
    "email_like": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone_like": re.compile(r"(?:\+7|8)\s?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"),
}


class ValidationError(Exception):
    pass


def normalize_ws(value: str) -> str:
    return " ".join((value or "").split())


def contains_text(container: str, needle: str) -> bool:
    if not needle:
        return True
    return normalize_ws(needle) in normalize_ws(container)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError(f"{path}: annotation root must be an object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_text_file(path: Path) -> str:
    require(path.exists(), f"missing file: {path}")
    require(path.is_file(), f"not a regular file: {path}")
    text = path.read_text(encoding="utf-8")
    require(text.strip(), f"empty text file: {path}")
    return text


def validate_no_obvious_pii(path: Path, text: str) -> list[str]:
    warnings: list[str] = []
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            warnings.append(f"{path}: possible {name}")
    return warnings


def validate_annotation(pair_dir: Path) -> tuple[int, int, list[str]]:
    annotation_path = pair_dir / "annotation.json"
    require(annotation_path.exists(), f"{pair_dir}: missing annotation.json")
    annotation = load_json(annotation_path)

    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(annotation))
    require(not missing, f"{annotation_path}: missing fields: {', '.join(missing)}")

    pair_id = annotation["pair_id"]
    require(pair_id == pair_dir.name, f"{annotation_path}: pair_id must equal directory name")

    old_file = pair_dir / str(annotation["old_file"])
    new_file = pair_dir / str(annotation["new_file"])
    old_text = validate_text_file(old_file)
    new_text = validate_text_file(new_file)

    warnings: list[str] = []
    warnings.extend(validate_no_obvious_pii(old_file, old_text))
    warnings.extend(validate_no_obvious_pii(new_file, new_text))

    expected_changes = annotation["expected_changes"]
    expected_significance = annotation["expected_significance"]
    expected_chunks = annotation["expected_chunks"]
    expected_summary_topics = annotation["expected_summary_topics"]
    expected_quiz_topics = annotation["expected_quiz_topics"]

    require(isinstance(expected_changes, list), f"{annotation_path}: expected_changes must be a list")
    require(expected_changes, f"{annotation_path}: expected_changes must not be empty")
    require(isinstance(expected_significance, list), f"{annotation_path}: expected_significance must be a list")
    require(isinstance(expected_chunks, list), f"{annotation_path}: expected_chunks must be a list")
    require(expected_chunks, f"{annotation_path}: expected_chunks must not be empty")
    require(isinstance(expected_summary_topics, list), f"{annotation_path}: expected_summary_topics must be a list")
    require(isinstance(expected_quiz_topics, list), f"{annotation_path}: expected_quiz_topics must be a list")

    seen_change_ids: set[str] = set()
    for index, change in enumerate(expected_changes, start=1):
        require(isinstance(change, dict), f"{annotation_path}: expected_changes[{index}] must be an object")
        for field in ("id", "type", "fragment", "old_text", "new_text", "importance", "description"):
            require(field in change, f"{annotation_path}: expected_changes[{index}] missing {field}")

        change_id = str(change["id"])
        require(change_id not in seen_change_ids, f"{annotation_path}: duplicate change id {change_id}")
        seen_change_ids.add(change_id)

        change_type = str(change["type"])
        require(change_type in ALLOWED_CHANGE_TYPES, f"{annotation_path}: change {change_id} has unsupported type {change_type}")

        importance = str(change["importance"])
        require(importance in ALLOWED_IMPORTANCE, f"{annotation_path}: change {change_id} has unsupported importance {importance}")

        old_fragment = str(change.get("old_text") or "")
        new_fragment = str(change.get("new_text") or "")

        if change_type in {"modified", "removed", "moved"} and old_fragment:
            require(contains_text(old_text, old_fragment), f"{annotation_path}: old_text for {change_id} not found in old file")
        if change_type in {"modified", "added", "moved"} and new_fragment:
            require(contains_text(new_text, new_fragment), f"{annotation_path}: new_text for {change_id} not found in new file")

    significance_ids = {str(item.get("change_id")) for item in expected_significance if isinstance(item, dict)}
    require(seen_change_ids.issubset(significance_ids), f"{annotation_path}: expected_significance must cover all expected_changes")

    editorial_changes = annotation["editorial_changes"]
    require(isinstance(editorial_changes, list), f"{annotation_path}: editorial_changes must be a list")
    for index, change in enumerate(editorial_changes, start=1):
        require(isinstance(change, dict), f"{annotation_path}: editorial_changes[{index}] must be an object")
        require("id" in change, f"{annotation_path}: editorial_changes[{index}] missing id")
        require("description" in change, f"{annotation_path}: editorial_changes[{index}] missing description")

    seen_chunk_ids: set[str] = set()
    for index, chunk in enumerate(expected_chunks, start=1):
        require(isinstance(chunk, dict), f"{annotation_path}: expected_chunks[{index}] must be an object")
        for field in ("id", "fragment", "expected_type", "expected_boundary_text"):
            require(field in chunk, f"{annotation_path}: expected_chunks[{index}] missing {field}")

        chunk_id = str(chunk["id"])
        require(chunk_id not in seen_chunk_ids, f"{annotation_path}: duplicate chunk id {chunk_id}")
        seen_chunk_ids.add(chunk_id)

        expected_type = str(chunk["expected_type"])
        require(expected_type in ALLOWED_CHUNK_TYPES, f"{annotation_path}: chunk {chunk_id} has unsupported expected_type {expected_type}")

        version = str(chunk.get("version") or "new")
        source_text = old_text if version == "old" else new_text
        boundary = str(chunk.get("expected_boundary_text") or "")
        require(contains_text(source_text, boundary), f"{annotation_path}: boundary text for chunk {chunk_id} not found in {version} file")

    expected_summary = annotation.get("expected_summary")
    require(isinstance(expected_summary, dict), f"{annotation_path}: expected_summary must be an object")
    require(isinstance(expected_summary.get("must_mention", []), list), f"{annotation_path}: expected_summary.must_mention must be a list")
    require(isinstance(expected_summary.get("must_not_mention", []), list), f"{annotation_path}: expected_summary.must_not_mention must be a list")

    expected_quiz = annotation.get("expected_quiz")
    require(isinstance(expected_quiz, dict), f"{annotation_path}: expected_quiz must be an object")
    require(isinstance(expected_quiz.get("must_cover_topics", []), list), f"{annotation_path}: expected_quiz.must_cover_topics must be a list")
    require(isinstance(expected_quiz.get("must_not_cover_topics", []), list), f"{annotation_path}: expected_quiz.must_not_cover_topics must be a list")

    q_min = int(expected_quiz.get("expected_question_count_min", 0))
    q_max = int(expected_quiz.get("expected_question_count_max", q_min))
    require(q_min >= 0, f"{annotation_path}: expected_question_count_min must be >= 0")
    require(q_max >= q_min, f"{annotation_path}: expected_question_count_max must be >= min")

    return len(expected_changes), len(expected_chunks), warnings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not CORPUS_DIR.exists():
        print(f"FAIL: missing corpus directory: {CORPUS_DIR}")
        return 1

    pair_dirs = sorted(path for path in CORPUS_DIR.iterdir() if path.is_dir())
    if len(pair_dirs) < 6:
        errors.append(f"expected at least 6 pair directories, found {len(pair_dirs)}")

    total_changes = 0
    total_chunks = 0

    for pair_dir in pair_dirs:
        try:
            change_count, chunk_count, pair_warnings = validate_annotation(pair_dir)
            total_changes += change_count
            total_chunks += chunk_count
            warnings.extend(pair_warnings)
        except ValidationError as exc:
            errors.append(str(exc))

    if errors:
        print("Evaluation corpus validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Evaluation corpus validation: PASS")
    print(f"Pairs: {len(pair_dirs)}")
    print(f"Expected changes: {total_changes}")
    print(f"Expected chunks: {total_chunks}")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
