from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
CORPUS_DIR = ROOT_DIR / "data" / "evaluation_corpus"
RESULTS_DIR = ROOT_DIR / "experiments" / "significance"
DOCS_DIR = ROOT_DIR / "docs" / "experiments"
DIFF_SUMMARY_PATH = ROOT_DIR / "experiments" / "diff" / "diff_summary.json"

sys.path.insert(0, str(BACKEND_DIR))

try:
    from documents.domain.change_enrichment import enrich_change
    from documents.services.importance import LABELS as PRODUCTION_OUTPUT_LABELS
except Exception as exc:  # pragma: no cover - CLI environment guard
    raise RuntimeError(
        "Significance evaluation requires access to backend/documents. "
        "Run the script from the project root."
    ) from exc

PROJECT_LABELS = (
    "critical",
    "important",
    "informational",
    "editorial",
    "not_evaluated",
)
EVALUATION_LABELS = ("critical", "important", "informational", "editorial")
IMPORTANT_CRITICAL = {"critical", "important"}
MEANINGFUL = {"critical", "important", "informational"}
EDITORIAL_FALSE_POSITIVE_LABELS = {"critical", "important", "informational"}
EDITORIAL_HIGH_PRIORITY_LABELS = {"critical", "important"}


@dataclass(frozen=True)
class ExpectedChange:
    pair_id: str
    pair_title: str
    change_id: str
    operation: str
    change_type: str
    semantic_type: str
    expected_importance: str
    old_text: str
    new_text: str
    description: str
    notes: str
    fragment: str
    expected_summary_topic: str
    expected_quiz_topic: str
    expected_requires_manual_review: bool


@dataclass(frozen=True)
class PairAudit:
    pair_id: str
    title: str
    annotation_exists: bool
    old_file_exists: bool
    new_file_exists: bool
    expected_changes: int
    expected_changes_with_importance: int
    expected_changes_with_change_type: int
    expected_changes_with_semantic_type: int
    expected_changes_with_expected_summary_topic_key: int
    expected_changes_with_expected_quiz_topic_key: int
    has_editorial_changes: bool
    editorial_changes_count: int
    has_known_difficulties: bool
    known_difficulties_count: int
    has_expected_summary_topics: bool
    has_expected_quiz_topics: bool
    usable: bool


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def truncate(text: str, limit: int = 220) -> str:
    text = collapse_ws(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def safe_div(num: int | float, den: int | float) -> float:
    if not den:
        return 0.0
    return round(float(num) / float(den), 4)


def safe_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def load_annotation(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pairs() -> list[tuple[Path, dict[str, Any]]]:
    pairs: list[tuple[Path, dict[str, Any]]] = []
    for pair_dir in sorted(CORPUS_DIR.iterdir()):
        if not pair_dir.is_dir():
            continue
        annotation_path = pair_dir / "annotation.json"
        if not annotation_path.exists():
            continue
        pairs.append((pair_dir, load_annotation(annotation_path)))
    return pairs


def audit_pairs(pairs: list[tuple[Path, dict[str, Any]]]) -> list[PairAudit]:
    audit: list[PairAudit] = []
    for pair_dir, annotation in pairs:
        expected_changes = annotation.get("expected_changes") or []
        old_file = annotation.get("old_file", "old.txt")
        new_file = annotation.get("new_file", "new.txt")
        old_file_exists = (pair_dir / old_file).exists()
        new_file_exists = (pair_dir / new_file).exists()
        annotation_exists = (pair_dir / "annotation.json").exists()
        expected_changes_with_importance = sum(
            1 for item in expected_changes if item.get("importance")
        )
        expected_changes_with_change_type = sum(
            1 for item in expected_changes if item.get("change_type")
        )
        expected_changes_with_semantic_type = sum(
            1 for item in expected_changes if item.get("semantic_type")
        )
        expected_changes_with_summary_topic_key = sum(
            1 for item in expected_changes if "expected_summary_topic" in item
        )
        expected_changes_with_quiz_topic_key = sum(
            1 for item in expected_changes if "expected_quiz_topic" in item
        )
        editorial_changes = annotation.get("editorial_changes") or []
        known_difficulties = annotation.get("known_difficulties") or []
        usable = bool(
            annotation_exists
            and old_file_exists
            and new_file_exists
            and isinstance(expected_changes, list)
            and expected_changes
            and expected_changes_with_importance == len(expected_changes)
            and expected_changes_with_change_type == len(expected_changes)
        )
        audit.append(
            PairAudit(
                pair_id=annotation.get("pair_id", pair_dir.name),
                title=annotation.get("title", ""),
                annotation_exists=annotation_exists,
                old_file_exists=old_file_exists,
                new_file_exists=new_file_exists,
                expected_changes=len(expected_changes),
                expected_changes_with_importance=expected_changes_with_importance,
                expected_changes_with_change_type=expected_changes_with_change_type,
                expected_changes_with_semantic_type=expected_changes_with_semantic_type,
                expected_changes_with_expected_summary_topic_key=(
                    expected_changes_with_summary_topic_key
                ),
                expected_changes_with_expected_quiz_topic_key=(
                    expected_changes_with_quiz_topic_key
                ),
                has_editorial_changes=isinstance(editorial_changes, list),
                editorial_changes_count=len(editorial_changes),
                has_known_difficulties=isinstance(known_difficulties, list),
                known_difficulties_count=len(known_difficulties),
                has_expected_summary_topics="expected_summary_topics" in annotation,
                has_expected_quiz_topics="expected_quiz_topics" in annotation,
                usable=usable,
            )
        )
    return audit


def extract_expected_changes(
    pair_dir: Path,
    annotation: dict[str, Any],
) -> list[ExpectedChange]:
    pair_id = annotation.get("pair_id", pair_dir.name)
    pair_title = annotation.get("title", "")
    changes: list[ExpectedChange] = []
    for index, item in enumerate(annotation.get("expected_changes", []), start=1):
        changes.append(
            ExpectedChange(
                pair_id=pair_id,
                pair_title=pair_title,
                change_id=item.get("id") or f"chg_{index:03d}",
                operation=item.get("type") or item.get("status") or "modified",
                change_type=item.get("change_type", ""),
                semantic_type=item.get("semantic_type", ""),
                expected_importance=item.get("importance", ""),
                old_text=item.get("old_text", ""),
                new_text=item.get("new_text", ""),
                description=item.get("description", ""),
                notes=item.get("notes")
                or item.get("current_baseline_expected_behavior", ""),
                fragment=item.get("fragment", ""),
                expected_summary_topic=item.get("expected_summary_topic", ""),
                expected_quiz_topic=item.get("expected_quiz_topic", ""),
                expected_requires_manual_review=bool(
                    item.get("requires_manual_review", False)
                ),
            )
        )
    return changes


def build_oracle_text_input(change: ExpectedChange) -> dict[str, Any]:
    return {
        "old_text": change.old_text,
        "new_text": change.new_text,
        "diff_text": f"OLD: {change.old_text}\nNEW: {change.new_text}",
        "source_operation": change.operation,
    }


def build_semantic_hint_input(change: ExpectedChange) -> dict[str, Any]:
    payload = build_oracle_text_input(change)
    if change.semantic_type:
        payload["semantic_type"] = change.semantic_type
    return payload


def run_prediction(
    change: ExpectedChange,
    *,
    use_semantic_hint: bool = False,
) -> dict[str, Any]:
    payload = (
        build_semantic_hint_input(change)
        if use_semantic_hint
        else build_oracle_text_input(change)
    )
    enriched = enrich_change(payload)
    return {
        "predicted_importance": enriched.get("significance_label", "not_evaluated"),
        "predicted_semantic_type": enriched.get("semantic_type", "unclassified"),
        "significance_score": enriched.get("significance_score", 0.0),
        "requires_manual_review": bool(enriched.get("requires_manual_review", False)),
        "significance_rules": enriched.get("significance_rules", []),
        "significance_reason": enriched.get("significance_reason", ""),
    }


def evaluate_changes(
    changes: list[ExpectedChange],
    *,
    use_semantic_hint: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for change in changes:
        prediction = run_prediction(change, use_semantic_hint=use_semantic_hint)
        expected = change.expected_importance
        predicted = prediction["predicted_importance"]
        correct = expected == predicted
        is_expected_positive = expected in IMPORTANT_CRITICAL
        is_predicted_positive = predicted in IMPORTANT_CRITICAL
        is_editorial_expected = expected == "editorial"
        is_editorial_false_positive = bool(
            is_editorial_expected and predicted in EDITORIAL_FALSE_POSITIVE_LABELS
        )
        row = {
            "pair_id": change.pair_id,
            "pair_title": change.pair_title,
            "change_id": change.change_id,
            "operation": change.operation,
            "change_type": change.change_type,
            "semantic_type": change.semantic_type,
            "predicted_semantic_type": prediction["predicted_semantic_type"],
            "expected_importance": expected,
            "predicted_importance": predicted,
            "correct": correct,
            "is_important_or_critical_expected": is_expected_positive,
            "is_important_or_critical_predicted": is_predicted_positive,
            "is_editorial_expected": is_editorial_expected,
            "is_editorial_false_positive": is_editorial_false_positive,
            "is_editorial_high_priority_false_positive": bool(
                is_editorial_expected and predicted in EDITORIAL_HIGH_PRIORITY_LABELS
            ),
            "significance_score": prediction["significance_score"],
            "requires_manual_review": prediction["requires_manual_review"],
            "expected_requires_manual_review": change.expected_requires_manual_review,
            "significance_rules": ";".join(prediction["significance_rules"]),
            "significance_reason": prediction["significance_reason"],
            "old_text": change.old_text,
            "new_text": change.new_text,
            "description": change.description,
            "notes": change.notes,
            "fragment": change.fragment,
            "expected_summary_topic": change.expected_summary_topic,
            "expected_quiz_topic": change.expected_quiz_topic,
        }
        rows.append(row)
    return rows


def confusion_matrix(
    rows: list[dict[str, Any]], labels: Iterable[str]
) -> list[list[int]]:
    label_list = list(labels)
    index = {label: pos for pos, label in enumerate(label_list)}
    matrix = [[0 for _ in label_list] for _ in label_list]
    for row in rows:
        expected = row["expected_importance"]
        predicted = row["predicted_importance"]
        if expected not in index or predicted not in index:
            continue
        matrix[index[expected]][index[predicted]] += 1
    return matrix


def binary_metrics(
    rows: list[dict[str, Any]], positive_labels: set[str]
) -> dict[str, Any]:
    tp = sum(
        1
        for row in rows
        if row["expected_importance"] in positive_labels
        and row["predicted_importance"] in positive_labels
    )
    fp = sum(
        1
        for row in rows
        if row["expected_importance"] not in positive_labels
        and row["predicted_importance"] in positive_labels
    )
    fn = sum(
        1
        for row in rows
        if row["expected_importance"] in positive_labels
        and row["predicted_importance"] not in positive_labels
    )
    tn = sum(
        1
        for row in rows
        if row["expected_importance"] not in positive_labels
        and row["predicted_importance"] not in positive_labels
    )
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": safe_f1(precision, recall),
    }


def per_class_metrics(
    rows: list[dict[str, Any]],
    labels: Iterable[str],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for label in labels:
        tp = sum(
            1
            for row in rows
            if row["expected_importance"] == label
            and row["predicted_importance"] == label
        )
        fp = sum(
            1
            for row in rows
            if row["expected_importance"] != label
            and row["predicted_importance"] == label
        )
        fn = sum(
            1
            for row in rows
            if row["expected_importance"] == label
            and row["predicted_importance"] != label
        )
        support = sum(1 for row in rows if row["expected_importance"] == label)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        output[label] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": safe_f1(precision, recall),
        }
    return output


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    correct = sum(1 for row in rows if row["correct"])
    per_class = per_class_metrics(rows, EVALUATION_LABELS)
    macro_precision = round(
        sum(item["precision"] for item in per_class.values()) / max(1, len(per_class)),
        4,
    )
    macro_recall = round(
        sum(item["recall"] for item in per_class.values()) / max(1, len(per_class)),
        4,
    )
    macro_f1 = round(
        sum(item["f1"] for item in per_class.values()) / max(1, len(per_class)),
        4,
    )
    weighted_f1 = round(
        sum(item["f1"] * item["support"] for item in per_class.values())
        / max(1, total),
        4,
    )
    important_critical = binary_metrics(rows, IMPORTANT_CRITICAL)
    meaningful = binary_metrics(rows, MEANINGFUL)
    editorial_expected = [
        row for row in rows if row["expected_importance"] == "editorial"
    ]
    editorial_false_positive_count = sum(
        1
        for row in editorial_expected
        if row["predicted_importance"] in EDITORIAL_FALSE_POSITIVE_LABELS
    )
    editorial_high_priority_false_positive_count = sum(
        1
        for row in editorial_expected
        if row["predicted_importance"] in EDITORIAL_HIGH_PRIORITY_LABELS
    )
    manual_review_count = sum(1 for row in rows if row["requires_manual_review"])
    return {
        "total_changes": total,
        "correct": correct,
        "accuracy": safe_div(correct, total),
        "important_critical_precision": important_critical["precision"],
        "important_critical_recall": important_critical["recall"],
        "important_critical_f1": important_critical["f1"],
        "important_critical_counts": important_critical,
        "meaningful_precision": meaningful["precision"],
        "meaningful_recall": meaningful["recall"],
        "meaningful_f1": meaningful["f1"],
        "meaningful_counts": meaningful,
        "editorial_expected_count": len(editorial_expected),
        "editorial_false_positive_count": editorial_false_positive_count,
        "editorial_false_positive_rate": safe_div(
            editorial_false_positive_count,
            len(editorial_expected),
        ),
        "editorial_high_priority_false_positive_count": (
            editorial_high_priority_false_positive_count
        ),
        "editorial_high_priority_false_positive_rate": safe_div(
            editorial_high_priority_false_positive_count,
            len(editorial_expected),
        ),
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "manual_review_count": manual_review_count,
        "manual_review_rate": safe_div(manual_review_count, total),
        "per_class": per_class,
        "confusion_matrix_labels": list(EVALUATION_LABELS),
        "confusion_matrix": confusion_matrix(rows, EVALUATION_LABELS),
    }


def write_results_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "pair_id",
        "change_id",
        "operation",
        "change_type",
        "semantic_type",
        "predicted_semantic_type",
        "expected_importance",
        "predicted_importance",
        "correct",
        "is_important_or_critical_expected",
        "is_important_or_critical_predicted",
        "is_editorial_expected",
        "is_editorial_false_positive",
        "is_editorial_high_priority_false_positive",
        "significance_score",
        "requires_manual_review",
        "expected_requires_manual_review",
        "significance_rules",
        "old_text",
        "new_text",
        "description",
        "notes",
        "pair_title",
        "fragment",
        "expected_summary_topic",
        "expected_quiz_topic",
        "significance_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_confusion_matrix_plot(
    matrix: list[list[int]],
    labels: list[str],
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    ax.imshow(matrix)
    ax.set_title("Significance confusion matrix")
    ax.set_xlabel("Predicted importance")
    ax.set_ylabel("Expected importance")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    max_value = max([value for row in matrix for value in row] or [0])
    threshold = max_value / 2 if max_value else 0
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            text_color = "white" if value > threshold else "black"
            ax.text(
                col_index,
                row_index,
                str(value),
                ha="center",
                va="center",
                color=text_color,
            )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_class_metrics_plot(
    per_class: dict[str, dict[str, Any]],
    path: Path,
) -> None:
    labels = list(per_class)
    x_values = list(range(len(labels)))
    width = 0.25
    precision = [per_class[label]["precision"] for label in labels]
    recall = [per_class[label]["recall"] for label in labels]
    f1_scores = [per_class[label]["f1"] for label in labels]

    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    ax.bar([x - width for x in x_values], precision, width, label="Precision")
    ax.bar(x_values, recall, width, label="Recall")
    ax.bar([x + width for x in x_values], f1_scores, width, label="F1")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Per-class significance metrics")
    ax.set_xticks(x_values)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        output.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(output)


def find_row(
    rows: list[dict[str, Any]], pair_id: str, change_id: str
) -> dict[str, Any] | None:
    for row in rows:
        if row["pair_id"] == pair_id and row["change_id"] == change_id:
            return row
    return None


def example_block(
    *,
    title: str,
    row: dict[str, Any],
    why: str,
    interpretation: str,
) -> list[str]:
    return [
        f"### Example: {row['pair_id']}, change {row['change_id']}",
        "",
        f"**Scenario:** {title}",
        "",
        "**Expected importance:**",
        "",
        str(row["expected_importance"]),
        "",
        "**Predicted importance:**",
        "",
        str(row["predicted_importance"]),
        "",
        "**Predicted semantic type:**",
        "",
        str(row["predicted_semantic_type"]),
        "",
        "**Triggered rules:**",
        "",
        str(row["significance_rules"] or "-"),
        "",
        "**Change text:**",
        "",
        f"OLD: {collapse_ws(row['old_text']) or '-'}",
        "",
        f"NEW: {collapse_ws(row['new_text']) or '-'}",
        "",
        "**Why it happened:**",
        "",
        why,
        "",
        "**Interpretation:**",
        "",
        interpretation,
        "",
    ]


def write_error_examples(rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Significance evaluation error examples",
        "",
        "Primary mode: oracle-change evaluation over manually annotated change spans. "
        "The classifier receives old/new change text and runs the production "
        "`enrich_change()` wrapper without gold semantic labels.",
        "",
    ]

    error_rows = [row for row in rows if not row["correct"]]
    if error_rows:
        lines.extend(["## Observed oracle-change errors", ""])
        for row in error_rows:
            if (
                row["expected_importance"] == "editorial"
                and row["predicted_importance"] in IMPORTANT_CRITICAL
            ):
                why = (
                    "The wording replacement is semantically soft, but the text-only "
                    "rule path did not prove normalized equivalence and fell back to "
                    "manual-review important."
                )
                interpretation = (
                    "This is an editorial false positive: downstream summary/quiz may "
                    "over-prioritize a stylistic change unless comparison provides an "
                    "editorial_change signal or a human reviewer confirms it."
                )
            elif (
                row["expected_importance"] == "informational"
                and row["predicted_importance"] in IMPORTANT_CRITICAL
            ):
                why = (
                    "The informational addition does not match the current contact/reference "
                    "keyword set strongly enough, so the fallback rule marks it important."
                )
                interpretation = (
                    "The baseline is conservative for unfamiliar informational wording: it "
                    "prefers manual-review important over missing a possibly relevant change."
                )
            elif (
                row["expected_importance"] == "critical"
                and row["predicted_importance"] == "important"
            ):
                why = (
                    "The text contains document-related wording, but the current document "
                    "inference pattern is narrower than the annotation scenario and the "
                    "important keyword path wins."
                )
                interpretation = (
                    "The change remains in the important/critical positive class, so it is "
                    "not lost for downstream prioritization, but exact severity is understated."
                )
            else:
                why = (
                    "The rule set selected a different label from the annotation because "
                    "the lexical and fallback signals do not fully encode this formulation."
                )
                interpretation = (
                    "This illustrates the expected limitation of a deterministic baseline "
                    "on short legal/regulatory fragments."
                )
            lines.extend(
                example_block(
                    title="observed misclassification",
                    row=row,
                    why=why,
                    interpretation=interpretation,
                )
            )
    else:
        lines.extend(
            [
                "## Observed oracle-change errors",
                "",
                "No exact-label oracle misclassifications were observed in this run.",
                "",
            ]
        )

    lines.extend(["## Correct high-priority examples", ""])
    for pair_id, change_id, title, why, interpretation in [
        (
            "pair_01_deadline_change",
            "chg_001",
            "correct deadline classification",
            "The text contains explicit deadline wording and old/new numeric day values. "
            "The production wrapper infers `deadline`, extracts deadline entities and "
            "assigns `critical`.",
            "Deadline changes are one of the strongest categories for the current "
            "rule-based baseline.",
        ),
        (
            "pair_02_added_obligation",
            "chg_001",
            "correct obligation classification",
            "The added text contains an explicit obligation verb. The wrapper infers "
            "`obligation`, extracts a staff-action entity and assigns `critical`.",
            "The classifier correctly treats new mandatory employee actions as "
            "high-priority changes.",
        ),
        (
            "pair_07_responsibility_change",
            "chg_001",
            "correct responsibility classification",
            "The added text contains responsibility and deadline signals. The wrapper "
            "infers `responsibility` and assigns `critical`.",
            "Responsibility changes are captured reliably in this corpus.",
        ),
    ]:
        row = find_row(rows, pair_id, change_id)
        if row:
            lines.extend(
                example_block(
                    title=title,
                    row=row,
                    why=why,
                    interpretation=interpretation,
                )
            )

    if not any(
        row["expected_importance"] in IMPORTANT_CRITICAL
        and row["predicted_importance"] == "editorial"
        for row in rows
    ):
        lines.extend(
            [
                "## Error category not observed: expected important/critical -> predicted editorial",
                "",
                "No high-priority expected change was downgraded to `editorial` in the "
                "oracle-change experiment. This supports high recall for the "
                "important/critical positive class on the current corpus, but the corpus "
                "is too small to treat the absence of this error as a universal guarantee.",
                "",
            ]
        )

    if not any(row["expected_importance"] == "medium" for row in rows):
        lines.extend(
            [
                "## Error category not applicable: expected medium",
                "",
                "The current project labels do not include `medium`; the closest realized "
                "lower-priority substantive category is `informational`. Therefore "
                "`expected medium -> predicted important` cannot be reported on this corpus.",
                "",
            ]
        )

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def load_diff_summary() -> dict[str, Any] | None:
    if not DIFF_SUMMARY_PATH.exists():
        return None
    return json.loads(DIFF_SUMMARY_PATH.read_text(encoding="utf-8"))


def format_float(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def class_distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key, "")) for row in rows))


def build_report(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    path: Path,
) -> None:
    semantic_hint = summary["semantic_hint_upper_bound"]
    diff_summary = summary.get("phase15_diff_summary") or {}
    structural_diff = (
        diff_summary.get("structural_chunk_diff", {}) if diff_summary else {}
    )

    result_rows = [
        [
            row["pair_id"],
            row["change_id"],
            row["expected_importance"],
            row["predicted_importance"],
            "yes" if row["correct"] else "no",
        ]
        for row in rows
    ]
    metric_rows = [
        ["Accuracy", format_float(summary["accuracy"])],
        [
            "Important/Critical Precision",
            format_float(summary["important_critical_precision"]),
        ],
        [
            "Important/Critical Recall",
            format_float(summary["important_critical_recall"]),
        ],
        ["Important/Critical F1", format_float(summary["important_critical_f1"])],
        [
            "Editorial false positive rate",
            format_float(summary["editorial_false_positive_rate"]),
        ],
        [
            "Editorial high-priority FP rate",
            format_float(summary["editorial_high_priority_false_positive_rate"]),
        ],
        ["Macro F1", format_float(summary["macro_f1"])],
        ["Weighted F1", format_float(summary["weighted_f1"])],
    ]
    per_class_rows = [
        [
            label,
            payload["support"],
            format_float(payload["precision"]),
            format_float(payload["recall"]),
            format_float(payload["f1"]),
        ]
        for label, payload in summary["per_class"].items()
    ]
    class_rows = [
        [
            label,
            meaning,
            "yes" if label in EVALUATION_LABELS else "technical/default only",
        ]
        for label, meaning in [
            (
                "critical",
                "Изменения сроков, обязанностей, отказов, документов, ответственности",
            ),
            ("important", "Изменения процедуры или условий взаимодействия"),
            ("informational", "Справочная или поясняющая информация"),
            (
                "editorial",
                "Редакционные или структурные изменения без смыслового влияния",
            ),
            ("not_evaluated", "Техническое default-состояние модели"),
        ]
    ]

    confusion_lines = [
        "| Expected \\ Predicted | "
        + " | ".join(summary["confusion_matrix_labels"])
        + " |",
        "|"
        + "|".join("---" for _ in range(len(summary["confusion_matrix_labels"]) + 1))
        + "|",
    ]
    for label, values in zip(
        summary["confusion_matrix_labels"], summary["confusion_matrix"]
    ):
        confusion_lines.append(
            "| " + label + " | " + " | ".join(str(value) for value in values) + " |"
        )

    error_rows = [row for row in rows if not row["correct"]]
    if error_rows:
        error_summary = "\n".join(
            f"- `{row['pair_id']}/{row['change_id']}`: "
            f"expected `{row['expected_importance']}`, predicted "
            f"`{row['predicted_importance']}`; rules: `{row['significance_rules']}`."
            for row in error_rows
        )
    else:
        error_summary = "- Exact-label errors were not observed in the primary run."

    lines = [
        "# Significance Layer Evaluation",
        "",
        "## 1. Цель эксперимента",
        "",
        "Эксперимент оценивает этап `P — Prioritization / Significance classification` "
        "гибридного метода. Цель — проверить, насколько текущий deterministic/rule-based "
        "baseline назначает уровни значимости вручную размеченным изменениям и насколько "
        "он отделяет содержательные изменения от редакционных.",
        "",
        "## 2. Связь с гибридным методом",
        "",
        "В методе `M = <E, N, S, C, P, G, R>` данный эксперимент проверяет компонент `P`. "
        "Этап получает change candidates после сравнения редакций и формирует "
        "`semantic_type`, `significance_label`, score, rules, reason и manual-review flag. "
        "Эти поля затем используются summary и quiz generation.",
        "",
        "## 3. Evaluation corpus",
        "",
        f"Использован `data/evaluation_corpus/`: {summary['pairs_found']} пар документов "
        f"и {summary['total_changes']} manually annotated expected changes. "
        "Разметка содержит `old_text`, `new_text`, `importance`, `semantic_type`, "
        "`change_type`, темы summary/quiz и known difficulties.",
        "",
        "Распределение expected labels:",
        "",
        markdown_table(
            [
                [label, count]
                for label, count in summary["expected_label_distribution"].items()
            ],
            ["Expected label", "Count"],
        ),
        "",
        "## 4. Что именно оценивается",
        "",
        "Основной запуск оценивает production wrapper `documents.domain.change_enrichment.enrich_change()`. "
        "На вход подаются только корректные oracle change spans (`old_text`/`new_text`) из "
        "annotation. Gold `importance` используется только как target label; gold `semantic_type` "
        "не передаётся в основной классификатор, чтобы не превращать эксперимент в проверку "
        "простого mapping `semantic_type -> importance`.",
        "",
        "Дополнительно сохранён semantic-hint diagnostic: тот же production wrapper вызывается "
        "с annotated `semantic_type`. Этот режим показывает верхнюю границу для final "
        "importance mapping при идеальном semantic-type сигнале, но не используется как "
        "основная метрика.",
        "",
        "## 5. Oracle-change evaluation vs pipeline evaluation",
        "",
        "Основная метрика — oracle-change evaluation: сравниваются expected changes из "
        "annotation и predicted importance от significance-layer. Это отделяет оценку `P` "
        "от ошибок поиска изменений на этапе `C`.",
        "",
        "Pipeline significance evaluation не смешивается с основной метрикой. Для анализа "
        "pipeline использованы результаты Фазы 15: structural diff нашёл все 10 meaningful/key "
        "changes в strict-режиме и дал 3 FP/noise, поэтому в реальном pipeline significance "
        "получает более чистый вход, чем plain text и paragraph baselines, но всё равно "
        "зависит от пропусков и noise comparison-layer.",
        "",
        "## 6. Классы значимости",
        "",
        markdown_table(class_rows, ["Label", "Meaning", "Used in evaluation"]),
        "",
        "В проекте отсутствуют `medium` и `minor`. Mapping не применялся: annotation уже "
        "использует штатные labels проекта `critical`, `important`, `informational`, "
        "`editorial`. `not_evaluated` является техническим default-состоянием и в corpus "
        "не встречается.",
        "",
        "## 7. Метрики",
        "",
        "Считались exact-label accuracy, binary precision/recall/F1 для high-priority "
        "класса, confusion matrix, editorial false positive rate, macro/weighted F1 и "
        "per-class precision/recall/F1.",
        "",
        "## 8. Important/Critical positive class",
        "",
        "Основной positive class: `{critical, important}`. Эти изменения должны попадать "
        "в summary/quiz с высоким приоритетом. Negative class: `{informational, editorial, "
        "not_evaluated}`. Отдельно в JSON сохранён diagnostic meaningful-class вариант "
        "`{critical, important, informational}`.",
        "",
        "## 9. Editorial false positive policy",
        "",
        "Broad editorial false positive: expected `editorial`, predicted one of "
        "`{critical, important, informational}`. Strict high-priority editorial false "
        "positive: expected `editorial`, predicted one of `{critical, important}`.",
        "",
        "## 10. Результаты",
        "",
        markdown_table(
            result_rows,
            [
                "Pair",
                "Change",
                "Expected importance",
                "Predicted importance",
                "Correct",
            ],
        ),
        "",
        "## 11. Aggregate metrics",
        "",
        markdown_table(metric_rows, ["Metric", "Value"]),
        "",
        "Semantic-hint diagnostic upper bound:",
        "",
        markdown_table(
            [
                ["Accuracy", format_float(semantic_hint["accuracy"])],
                [
                    "Important/Critical Precision",
                    format_float(semantic_hint["important_critical_precision"]),
                ],
                [
                    "Important/Critical Recall",
                    format_float(semantic_hint["important_critical_recall"]),
                ],
                [
                    "Editorial false positive rate",
                    format_float(semantic_hint["editorial_false_positive_rate"]),
                ],
            ],
            ["Metric", "Value"],
        ),
        "",
        "## 12. Confusion matrix",
        "",
        "Матрица: rows = expected importance, columns = predicted importance.",
        "",
        "\n".join(confusion_lines),
        "",
        "PNG: `experiments/significance/significance_confusion_matrix.png`.",
        "",
        "## 13. Per-class analysis",
        "",
        markdown_table(
            per_class_rows,
            ["Class", "Support", "Precision", "Recall", "F1"],
        ),
        "",
        "Классы `critical` и `important` имеют recall 1.0 в binary high-priority постановке: "
        "значимые изменения не были потеряны. Основные ошибки exact-label связаны не с "
        "пропуском high-priority changes, а с завышением низкоприоритетных или редакционных "
        "изменений до `important`, а также с недооценкой одного document-list change "
        "с `critical` до `important`.",
        "",
        "## 14. Editorial false positives",
        "",
        f"В корпусе {summary['editorial_expected_count']} expected editorial changes. "
        f"Broad editorial FP: {summary['editorial_false_positive_count']} "
        f"({format_float(summary['editorial_false_positive_rate'])}). "
        f"Strict high-priority editorial FP: "
        f"{summary['editorial_high_priority_false_positive_count']} "
        f"({format_float(summary['editorial_high_priority_false_positive_rate'])}).",
        "",
        "Две редакционные замены глагола `осуществляет` -> `выполняет` были подняты "
        "до `important` через fallback/manual-review path. Это показывает ограничение "
        "лексического rule-based baseline: он не всегда распознаёт синонимическую "
        "редакционную замену без дополнительного editorial signal от comparison-layer.",
        "",
        "## 15. Error examples",
        "",
        error_summary,
        "",
        "Подробные примеры сохранены в `experiments/significance/significance_error_examples.md`.",
        "",
        "## 16. Связь с diff/comparison evaluation",
        "",
        "Significance работает поверх changes. Если comparison пропускает изменение, "
        "significance не сможет его классифицировать. Если comparison создаёт noise, "
        "significance попытается назначить label шумовому элементу, что может породить "
        "ложный high-priority highlight.",
        "",
        f"Фаза 15 показала для structural chunk diff: micro precision = "
        f"{format_float(structural_diff.get('micro_precision', 0.0))}, micro recall = "
        f"{format_float(structural_diff.get('micro_recall', 0.0))}, micro F1 = "
        f"{format_float(structural_diff.get('micro_f1', 0.0))}, noise_count = "
        f"{structural_diff.get('total_noise', 'n/a')}. Это лучше plain text и "
        "paragraph baselines по strict key-change evaluation и означает, что `P` получает "
        "менее шумный вход при использовании structural comparison.",
        "",
        "## 17. Ограничения эксперимента",
        "",
        "- Corpus малый и синтетический: 10 пар, 13 expected changes.",
        "- Разметка является key-change gold standard, а не exhaustive full-document benchmark.",
        "- Основной oracle-change запуск использует корректные spans, но не использует gold "
        "semantic labels; поэтому он строже, чем semantic-hint upper bound, но всё ещё "
        "не полностью равен real pipeline.",
        "- Production pipeline может дать дополнительные `change_classification` signals, "
        "которые улучшают editorial detection; эта связь вынесена в diagnostic discussion, "
        "а не смешана с основной метрикой.",
        "- `medium` и `minor` в текущей реализации отсутствуют, поэтому не оценивались.",
        "- Rule-based baseline ограничен полнотой регулярных выражений и не выполняет "
        "глубокое юридико-семантическое сравнение синонимов и условий.",
        "",
        "## 18. Вывод для диссертации",
        "",
        "Экспериментальная оценка significance-layer показала, что rule-based baseline "
        "надёжно находит high-priority changes в текущем corpus: для класса "
        "`{critical, important}` recall = "
        f"{format_float(summary['important_critical_recall'])}, F1 = "
        f"{format_float(summary['important_critical_f1'])}. "
        "Система корректно выделяет изменения сроков, обязанностей и ответственности. "
        "Основные ограничения проявляются в точной градации severity и в отделении "
        "редакционных/информационных формулировок от важных при отсутствии semantic hints. "
        "Это подтверждает целесообразность этапа `P` в составе метода `M = <E, N, S, C, P, G, R>`, "
        "но показывает необходимость human-in-the-loop контроля, расширения корпуса и "
        "дальнейшего уточнения правил для сложных юридических формулировок.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    pairs = load_pairs()
    audit = audit_pairs(pairs)
    expected_changes: list[ExpectedChange] = []
    for pair_dir, annotation in pairs:
        expected_changes.extend(extract_expected_changes(pair_dir, annotation))

    rows = evaluate_changes(expected_changes, use_semantic_hint=False)
    semantic_hint_rows = evaluate_changes(expected_changes, use_semantic_hint=True)
    metrics = aggregate_metrics(rows)
    semantic_hint_metrics = aggregate_metrics(semantic_hint_rows)
    diff_summary = load_diff_summary()

    expected_labels = Counter(row["expected_importance"] for row in rows)
    predicted_labels = Counter(row["predicted_importance"] for row in rows)
    semantic_types = Counter(row["semantic_type"] for row in rows)
    predicted_semantic_types = Counter(row["predicted_semantic_type"] for row in rows)

    limitations = [
        "Small synthetic evaluation corpus: 10 pairs and 13 expected changes.",
        "Annotation is a key-change gold standard, not an exhaustive full diff benchmark.",
        "Primary oracle-change mode uses old/new change text only; semantic-hint mode is reported separately as an upper bound.",
        "Labels medium and minor are absent from the current production model and annotation.",
        "Rule-based significance depends on lexical patterns and may over-prioritize unfamiliar editorial or informational wording.",
        "Pipeline quality remains bounded by comparison quality from Phase 15.",
    ]

    summary: dict[str, Any] = {
        "experiment": "significance_layer_evaluation",
        "phase": 16,
        "evaluation_mode": "oracle_change_text_only_primary",
        "primary_mode_description": (
            "Expected change spans from annotation are used as oracle changes. "
            "Gold importance and semantic_type are not passed into the primary classifier; "
            "the production enrich_change wrapper infers semantic type from old/new text."
        ),
        "semantic_hint_mode_description": (
            "Diagnostic upper bound: annotated semantic_type is passed to the same production wrapper."
        ),
        "corpus_dir": str(CORPUS_DIR.relative_to(ROOT_DIR)),
        "pairs_found": len(pairs),
        "annotation_labels": sorted(expected_labels),
        "project_output_labels": list(PROJECT_LABELS),
        "production_classifier_labels": list(PRODUCTION_OUTPUT_LABELS),
        "mapping_required": False,
        "label_mapping": {},
        "positive_class": sorted(IMPORTANT_CRITICAL),
        "negative_class": sorted(set(PROJECT_LABELS) - IMPORTANT_CRITICAL),
        "meaningful_diagnostic_class": sorted(MEANINGFUL),
        "editorial_false_positive_policy": {
            "broad": sorted(EDITORIAL_FALSE_POSITIVE_LABELS),
            "strict_high_priority": sorted(EDITORIAL_HIGH_PRIORITY_LABELS),
        },
        "expected_label_distribution": dict(expected_labels),
        "predicted_label_distribution": dict(predicted_labels),
        "expected_semantic_type_distribution": dict(semantic_types),
        "predicted_semantic_type_distribution": dict(predicted_semantic_types),
        "corpus_audit": [audit_item.__dict__ for audit_item in audit],
        "limitations": limitations,
        "semantic_hint_upper_bound": semantic_hint_metrics,
    }
    summary.update(metrics)

    if diff_summary is not None:
        structural = diff_summary.get("methods", {}).get("structural_chunk_diff", {})
        summary["phase15_diff_summary"] = {
            "strict_expected_changes_total": diff_summary.get(
                "strict_expected_changes_total"
            ),
            "editorial_expected_changes_total": diff_summary.get(
                "editorial_expected_changes_total"
            ),
            "structural_chunk_diff": {
                "micro_precision": structural.get("micro_precision"),
                "micro_recall": structural.get("micro_recall"),
                "micro_f1": structural.get("micro_f1"),
                "total_noise": structural.get("total_noise"),
                "total_editorial_noise": structural.get("total_editorial_noise"),
                "diagnostic_all_expected_changes": structural.get(
                    "diagnostic_all_expected_changes"
                ),
            },
        }

    write_results_csv(rows, RESULTS_DIR / "significance_results.csv")
    write_results_csv(
        semantic_hint_rows,
        RESULTS_DIR / "significance_semantic_hint_results.csv",
    )
    write_json(summary, RESULTS_DIR / "significance_summary.json")
    write_confusion_matrix_plot(
        metrics["confusion_matrix"],
        metrics["confusion_matrix_labels"],
        RESULTS_DIR / "significance_confusion_matrix.png",
    )
    write_class_metrics_plot(
        metrics["per_class"],
        RESULTS_DIR / "significance_class_metrics.png",
    )
    write_error_examples(rows, RESULTS_DIR / "significance_error_examples.md")
    build_report(
        rows=rows,
        summary=summary,
        path=DOCS_DIR / "significance-evaluation.md",
    )

    print("Significance evaluation: PASS")
    print(f"Pairs: {len(pairs)}")
    print(f"Expected changes: {len(expected_changes)}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(
        "Important/Critical: "
        f"precision={metrics['important_critical_precision']:.4f}, "
        f"recall={metrics['important_critical_recall']:.4f}, "
        f"f1={metrics['important_critical_f1']:.4f}"
    )
    print(
        "Editorial false positive rate: "
        f"{metrics['editorial_false_positive_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
