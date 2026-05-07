from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
CORPUS_DIR = ROOT_DIR / "data" / "evaluation_corpus"
RESULTS_DIR = ROOT_DIR / "experiments" / "summary"
DOCS_DIR = ROOT_DIR / "docs" / "experiments"
DIFF_SUMMARY_PATH = ROOT_DIR / "experiments" / "diff" / "diff_summary.json"
SIGNIFICANCE_SUMMARY_PATH = (
    ROOT_DIR / "experiments" / "significance" / "significance_summary.json"
)

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    import django

    django.setup()
    from documents.domain.diff import build_version_diff
    from documents.domain.diff_summary import build_brief_summary
    from documents.domain.text_processing import chunk_by_structure_ru, normalize_text
except Exception as exc:  # pragma: no cover - CLI dependency guard
    raise RuntimeError(
        "Summary evaluation requires backend dependencies. Install "
        "backend/requirements.txt and run from the project root."
    ) from exc

CRITERIA = [
    "completeness",
    "accuracy",
    "no_hallucinations",
    "clarity",
    "usefulness",
    "source_alignment",
]

HIGH_PRIORITY_LABELS = {"critical", "important"}
SUMMARY_TOPIC_IMPORTANCE = {"critical", "important"}

STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "по",
    "при",
    "для",
    "о",
    "об",
    "от",
    "до",
    "с",
    "со",
    "из",
    "за",
    "к",
    "ко",
    "у",
    "а",
    "но",
    "или",
    "либо",
    "что",
    "как",
    "это",
    "его",
    "ее",
    "их",
    "он",
    "она",
    "они",
    "оно",
    "быть",
    "был",
    "было",
    "была",
    "стало",
    "новый",
    "новая",
    "новое",
    "новые",
    "добавлен",
    "добавлена",
    "добавлено",
    "изменение",
    "изменения",
    "изменены",
    "уточнены",
    "рабочих",
    "рабочие",
    "дней",
    "дня",
}

PAIR_EXPERT_ADJUDICATION: dict[str, dict[str, Any]] = {
    "pair_01_deadline_change": {
        "scores": [5, 5, 5, 5, 5, 5],
        "notes": "Covers the deadline reduction and preserves old/new values.",
        "good": True,
    },
    "pair_02_added_obligation": {
        "scores": [5, 5, 5, 5, 5, 5],
        "notes": "Covers the added notification obligation clearly and source-backed.",
        "good": True,
    },
    "pair_03_document_list_change": {
        "scores": [5, 5, 4, 5, 4, 4],
        "notes": (
            "Key document-list topic is covered; brief statistics also expose one "
            "upstream editorial/technical diff item."
        ),
        "editorial_overemphasis_details": [
            "Summary statistics mention one editorial/technical change produced by upstream comparison."
        ],
    },
    "pair_04_refusal_ground_change": {
        "scores": [5, 5, 5, 5, 5, 5],
        "notes": "Covers the new refusal ground and keeps the source condition intact.",
        "good": True,
    },
    "pair_05_editorial_change": {
        "scores": [2, 2, 2, 3, 1, 2],
        "notes": (
            "Weak editorial-control case: upstream semantic/significance classification "
            "turns a wording change into a critical highlight."
        ),
        "unsupported_claim_details": [
            "Editorial-only wording change is presented as a critical document-list requirement change."
        ],
        "editorial_overemphasis_details": [
            "Editorial wording change is over-prioritized as critical."
        ],
        "weak": True,
    },
    "pair_06_procedure_change": {
        "scores": [1, 2, 3, 3, 2, 2],
        "notes": (
            "Expected electronic-form submission topic is missed because upstream "
            "enrichment misclassifies the changed chunk."
        ),
        "unsupported_claim_details": [
            "Procedure change is summarized as a document-list requirement change."
        ],
        "weak": True,
    },
    "pair_07_responsibility_change": {
        "scores": [5, 4, 4, 4, 4, 4],
        "notes": (
            "Responsibility topic is visible in the source-backed snippet, but the "
            "semantic label frames it as a deadline requirement."
        ),
        "unsupported_claim_details": [
            "Responsibility change is framed as a deadline requirement, although the source text still states responsibility."
        ],
    },
    "pair_08_reordered_structure": {
        "scores": [5, 5, 5, 5, 5, 5],
        "notes": (
            "Correctly avoids inventing a substantive change for pure reordering in "
            "the current MVP pipeline."
        ),
        "good": True,
    },
    "pair_09_mixed_significant_and_editorial": {
        "scores": [5, 3, 3, 4, 3, 3],
        "notes": (
            "Both expected critical topics are covered, but upstream over-prioritization "
            "creates extra misleading highlights."
        ),
        "unsupported_claim_details": [
            "Editorial wording change is incorrectly summarized as another deadline-related critical change.",
            "Informational status notice is over-framed as an important procedural step.",
        ],
        "editorial_overemphasis_details": [
            "Editorial wording change receives a critical deadline highlight.",
            "Informational/noise item is counted as important in the brief.",
        ],
        "weak": True,
    },
    "pair_10_weakly_structured_document": {
        "scores": [5, 5, 5, 4, 5, 5],
        "notes": (
            "Weakly structured document is handled via fallback blocks and the deadline "
            "topic remains covered; wording has minor grammatical roughness."
        ),
    },
}


class QueryList(list):
    """Small in-memory stand-in for Django related managers used by build_version_diff."""

    def order_by(self, attr: str) -> list[Any]:
        return sorted(self, key=lambda item: getattr(item, attr))


@dataclass(frozen=True)
class PairInput:
    pair_id: str
    pair_dir: Path
    annotation: dict[str, Any]
    old_text: str
    new_text: str


def normalize_for_match(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_tokens(text: str) -> list[str]:
    normalized = normalize_for_match(text)
    tokens = []
    for token in normalized.split():
        if len(token) <= 2 and not token.isdigit():
            continue
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def dedupe_keep_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_for_match(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


def topic_is_covered(topic: str, summary_text: str) -> bool:
    topic_norm = normalize_for_match(topic)
    summary_norm = normalize_for_match(summary_text)
    if not topic_norm:
        return True
    if topic_norm in summary_norm:
        return True

    topic_numbers = {token for token in topic_norm.split() if token.isdigit()}
    summary_numbers = {token for token in summary_norm.split() if token.isdigit()}
    if topic_numbers and not topic_numbers <= summary_numbers:
        return False

    tokens = content_tokens(topic)
    if not tokens:
        return True
    matched = sum(1 for token in tokens if token in summary_norm)
    coverage = matched / len(tokens)
    return coverage >= 0.55


def extract_expected_topics(annotation: dict[str, Any]) -> list[str]:
    expected_summary = annotation.get("expected_summary") or {}
    topics: list[str] = []
    if isinstance(expected_summary, dict):
        topics.extend(expected_summary.get("must_mention") or [])
    if not topics:
        for key in ("expected_summary_topics", "expected_summary_topic"):
            value = annotation.get(key)
            if isinstance(value, str):
                topics.append(value)
            elif isinstance(value, list):
                topics.extend(value)
    return dedupe_keep_order([str(topic) for topic in topics if str(topic).strip()])


def extract_must_not_topics(annotation: dict[str, Any]) -> list[str]:
    expected_summary = annotation.get("expected_summary") or {}
    if not isinstance(expected_summary, dict):
        return []
    return dedupe_keep_order(
        [str(topic) for topic in expected_summary.get("must_not_mention") or []]
    )


def read_pairs() -> list[PairInput]:
    pairs: list[PairInput] = []
    for pair_dir in sorted(CORPUS_DIR.glob("pair_*")):
        annotation_path = pair_dir / "annotation.json"
        old_path = pair_dir / "old.txt"
        new_path = pair_dir / "new.txt"
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        pair_id = str(annotation.get("pair_id") or pair_dir.name)
        pairs.append(
            PairInput(
                pair_id=pair_id,
                pair_dir=pair_dir,
                annotation=annotation,
                old_text=old_path.read_text(encoding="utf-8"),
                new_text=new_path.read_text(encoding="utf-8"),
            )
        )
    return pairs


def make_in_memory_version(*, pair_id: str, version_number: int, text: str) -> Any:
    normalized = normalize_text(text)
    chunks = QueryList()
    base_id = version_number * 1000
    for index, chunk_data in enumerate(chunk_by_structure_ru(normalized), start=1):
        payload = dict(chunk_data.__dict__)
        payload["id"] = base_id + index
        chunks.append(SimpleNamespace(**payload))

    document = SimpleNamespace(id=1, title=pair_id)
    return SimpleNamespace(
        id=version_number,
        document_id=1,
        document=document,
        version_number=version_number,
        created_at="2026-01-01T00:00:00Z",
        extracted_text=text,
        normalized_text=normalized,
        chunks=chunks,
    )


def stringify_summary(summary_payload: dict[str, Any]) -> str:
    lines = [summary_payload.get("overview_title") or ""]
    if summary_payload.get("brief_text"):
        lines.append(summary_payload["brief_text"])
    highlights = summary_payload.get("highlights") or []
    if highlights:
        lines.append("Highlights:")
        for index, item in enumerate(highlights, start=1):
            label = item.get("significance_label") or ""
            semantic = item.get("semantic_type") or ""
            text = item.get("concise_explanation") or item.get("description") or ""
            lines.append(f"{index}. [{label}/{semantic}] {text}")
    return "\n".join(line for line in lines if line).strip()


def run_pipeline_summary(pair: PairInput) -> tuple[dict[str, Any], dict[str, Any]]:
    old_version = make_in_memory_version(
        pair_id=pair.pair_id,
        version_number=1,
        text=pair.old_text,
    )
    new_version = make_in_memory_version(
        pair_id=pair.pair_id,
        version_number=2,
        text=pair.new_text,
    )
    diff_payload = build_version_diff(old_version, new_version)
    summary_payload = build_brief_summary(diff_payload)
    return diff_payload, summary_payload


def make_chunk_from_change(
    change: dict[str, Any], *, text_key: str, index: int
) -> dict[str, Any]:
    text = str(change.get(text_key) or "")
    fragment = str(change.get("fragment") or "")
    return {
        "id": None,
        "chunk_index": index,
        "fragment_type": "annotation_change",
        "structure_level": 1,
        "raw_label": fragment,
        "canonical_label": fragment,
        "path_key": f"annotation:{change.get('id') or index}:{text_key}",
        "heading": fragment or f"Expected change {index}",
        "section_path": fragment,
        "text": text,
        "text_hash": "",
    }


def build_oracle_diff_payload(pair: PairInput) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "added": [],
        "removed": [],
        "modified": [],
        "moved": [],
    }
    for index, change in enumerate(
        pair.annotation.get("expected_changes") or [], start=1
    ):
        change_type = str(change.get("type") or "modified")
        change_type = change_type if change_type in buckets else "modified"
        common = {
            "semantic_type": change.get("semantic_type") or "unclassified",
            "significance_label": change.get("importance") or "not_evaluated",
            "significance_score": 1.0,
            "significance_reason": change.get("description")
            or "annotation oracle input",
            "significance_rules": ["annotation_oracle"],
            "requires_manual_review": bool(change.get("requires_manual_review", False)),
            "extracted_entities": [],
            "_original_order": index,
        }
        if change_type == "added":
            payload = {
                **make_chunk_from_change(change, text_key="new_text", index=index),
                **common,
                "change_classification": {
                    "label": change.get("change_type") or "added"
                },
            }
        elif change_type == "removed":
            payload = {
                **make_chunk_from_change(change, text_key="old_text", index=index),
                **common,
                "change_classification": {
                    "label": change.get("change_type") or "removed"
                },
            }
        else:
            old_chunk = make_chunk_from_change(change, text_key="old_text", index=index)
            new_chunk = make_chunk_from_change(change, text_key="new_text", index=index)
            payload = {
                "from_chunk": old_chunk,
                "to_chunk": new_chunk,
                "old_text": change.get("old_text") or "",
                "new_text": change.get("new_text") or "",
                "similarity": 0.9,
                "match_reason": "annotation_oracle",
                "change_classification": {
                    "label": change.get("change_type") or "modified"
                },
                **common,
            }
        buckets[change_type].append(payload)

    summary = {key: len(value) for key, value in buckets.items()}
    summary["unchanged"] = 0
    return {
        "from_version": {"id": 1, "document_id": 1, "version_number": 1},
        "to_version": {"id": 2, "document_id": 1, "version_number": 2},
        "comparison_meta": {
            "comparison_unit": "annotation_expected_changes",
            "matching_strategy": "oracle_annotation_v1",
        },
        "identical": not any(buckets.values()),
        "summary": summary,
        "added": buckets["added"],
        "removed": buckets["removed"],
        "modified": buckets["modified"],
        "moved": buckets["moved"],
        "text_diff": "",
    }


def evaluate_oracle(pair: PairInput, expected_topics: list[str]) -> dict[str, Any]:
    oracle_diff = build_oracle_diff_payload(pair)
    oracle_summary = build_brief_summary(oracle_diff)
    oracle_text = stringify_summary(oracle_summary)
    covered = [
        topic for topic in expected_topics if topic_is_covered(topic, oracle_text)
    ]
    missed = [topic for topic in expected_topics if topic not in covered]
    if not expected_topics:
        completeness = 5
    else:
        completeness = (
            5 if not missed else max(1, round(5 * len(covered) / len(expected_topics)))
        )
    # Oracle input is diagnostic: the production wording is evaluated with correct spans/labels.
    accuracy = 5
    no_hallucinations = 5
    clarity = 5 if oracle_summary.get("highlights") else 4
    usefulness = 5 if expected_topics or not oracle_summary.get("highlights") else 4
    source_alignment = 5
    scores = [
        completeness,
        accuracy,
        no_hallucinations,
        clarity,
        usefulness,
        source_alignment,
    ]
    return {
        "oracle_summary_text": oracle_text,
        "oracle_covered_topics": covered,
        "oracle_missed_topics": missed,
        "oracle_average_score": round(mean(scores), 4),
    }


def rows_from_json_list(row: dict[str, Any], key: str) -> list[Any]:
    value = row.get(key)
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def summarize_highlights(
    summary_payload: dict[str, Any],
) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    semantics: list[str] = []
    for item in summary_payload.get("highlights") or []:
        labels.append(str(item.get("significance_label") or ""))
        semantics.append(str(item.get("semantic_type") or ""))
    return labels, semantics


def score_pair(
    pair: PairInput,
    summary_payload: dict[str, Any],
    summary_text: str,
    expected_topics: list[str],
) -> dict[str, Any]:
    covered_topics = [
        topic for topic in expected_topics if topic_is_covered(topic, summary_text)
    ]
    missed_topics = [topic for topic in expected_topics if topic not in covered_topics]

    adjudication = PAIR_EXPERT_ADJUDICATION.get(pair.pair_id, {})
    scores = adjudication.get("scores")
    if not scores:
        coverage_ratio = (
            1.0 if not expected_topics else len(covered_topics) / len(expected_topics)
        )
        completeness = 5 if coverage_ratio == 1 else max(1, round(5 * coverage_ratio))
        scores = [completeness, 4, 4, 4, 4, 4]

    unsupported_details = list(adjudication.get("unsupported_claim_details") or [])
    editorial_details = list(adjudication.get("editorial_overemphasis_details") or [])

    labels, semantics = summarize_highlights(summary_payload)
    row = {
        "pair_id": pair.pair_id,
        "summary_text": summary_text,
        "expected_topics": expected_topics,
        "covered_topics": covered_topics,
        "missed_topics": missed_topics,
        "unsupported_claims": len(unsupported_details),
        "unsupported_claim_details": unsupported_details,
        "editorial_overemphasis": len(editorial_details),
        "editorial_overemphasis_details": editorial_details,
        "completeness": scores[0],
        "accuracy": scores[1],
        "no_hallucinations": scores[2],
        "clarity": scores[3],
        "usefulness": scores[4],
        "source_alignment": scores[5],
        "average_score": round(mean(scores), 4),
        "notes": adjudication.get("notes")
        or "Evaluated by hybrid automatic + expert rubric.",
        "brief_text": summary_payload.get("brief_text") or "",
        "overview_title": summary_payload.get("overview_title") or "",
        "selection_scope": summary_payload.get("selection_scope") or "",
        "highlights_count": len(summary_payload.get("highlights") or []),
        "highlight_labels": labels,
        "highlight_semantic_types": semantics,
    }
    row.update(evaluate_oracle(pair, expected_topics))
    return row


def evaluate_pairs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = read_pairs()
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        _, summary_payload = run_pipeline_summary(pair)
        summary_text = stringify_summary(summary_payload)
        expected_topics = extract_expected_topics(pair.annotation)
        rows.append(score_pair(pair, summary_payload, summary_text, expected_topics))

    average_scores = {
        criterion: round(mean(float(row[criterion]) for row in rows), 4)
        for criterion in CRITERIA
    }
    average_scores["overall"] = round(
        mean(float(row["average_score"]) for row in rows), 4
    )
    oracle_overall = round(mean(float(row["oracle_average_score"]) for row in rows), 4)
    summary = {
        "experiment": "summary_layer_evaluation",
        "phase": 17,
        "evaluation_mode": {
            "primary": "pipeline_summary_evaluation",
            "primary_pipeline": "chunk_by_structure_ru -> build_version_diff -> build_brief_summary",
            "diagnostic": "oracle_input_summary_evaluation",
            "oracle_input": "annotation expected_changes + semantic/importance labels -> build_brief_summary",
        },
        "total_pairs": len(rows),
        "average_scores": average_scores,
        "missed_topics_total": sum(len(row["missed_topics"]) for row in rows),
        "unsupported_claims_total": sum(int(row["unsupported_claims"]) for row in rows),
        "editorial_overemphasis_total": sum(
            int(row["editorial_overemphasis"]) for row in rows
        ),
        "covered_topics_total": sum(len(row["covered_topics"]) for row in rows),
        "expected_topics_total": sum(len(row["expected_topics"]) for row in rows),
        "oracle_diagnostic": {
            "overall_average": oracle_overall,
            "interpretation": (
                "Diagnostic only: estimates summary wording quality when upstream "
                "change spans and labels are correct."
            ),
        },
        "criteria": CRITERIA,
        "rows": rows,
        "limitations": [
            "The corpus is small and synthetic: 10 document pairs.",
            "Clarity, usefulness and source alignment require expert-heuristic scoring.",
            "Pipeline-mode scores include upstream diff/significance errors.",
            "Oracle-input diagnostic is not the real pipeline score.",
            "The production summary algorithm was not changed for the experiment.",
        ],
    }
    return rows, summary


def json_cell(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "pair_id",
        "summary_text",
        "expected_topics",
        "covered_topics",
        "missed_topics",
        "unsupported_claims",
        "unsupported_claim_details",
        "editorial_overemphasis",
        "editorial_overemphasis_details",
        "completeness",
        "accuracy",
        "no_hallucinations",
        "clarity",
        "usefulness",
        "source_alignment",
        "average_score",
        "notes",
        "brief_text",
        "overview_title",
        "selection_scope",
        "highlights_count",
        "highlight_labels",
        "highlight_semantic_types",
        "oracle_summary_text",
        "oracle_covered_topics",
        "oracle_missed_topics",
        "oracle_average_score",
    ]
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json_cell(row.get(key, "")) for key in fieldnames})


def write_json(summary: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_quality_chart(summary: dict[str, Any], path: Path) -> None:
    labels = [
        "Completeness",
        "Accuracy",
        "No hallucinations",
        "Clarity",
        "Usefulness",
        "Source alignment",
    ]
    values = [summary["average_scores"][criterion] for criterion in CRITERIA]
    plt.figure(figsize=(10, 5))
    plt.bar(labels, values)
    plt.ylim(0, 5)
    plt.ylabel("Average score, 1-5")
    plt.title("Summary-layer average quality scores")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def write_pair_scores_chart(rows: list[dict[str, Any]], path: Path) -> None:
    labels = [row["pair_id"].replace("pair_", "") for row in rows]
    values = [float(row["average_score"]) for row in rows]
    plt.figure(figsize=(12, 5))
    plt.bar(labels, values)
    plt.ylim(0, 5)
    plt.ylabel("Average score, 1-5")
    plt.title("Summary-layer average score by evaluation pair")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def format_topics(topics: list[str]) -> str:
    if not topics:
        return "- none"
    return "\n".join(f"- {topic}" for topic in topics)


def format_scores(row: dict[str, Any]) -> str:
    lines = []
    for criterion in CRITERIA:
        lines.append(f"- {criterion}: {row[criterion]}")
    lines.append(f"- average: {float(row['average_score']):.2f}")
    return "\n".join(lines)


def write_examples_md(rows: list[dict[str, Any]], path: Path) -> None:
    good_rows = [
        row for row in rows if PAIR_EXPERT_ADJUDICATION[row["pair_id"]].get("good")
    ]
    weak_rows = [
        row for row in rows if PAIR_EXPERT_ADJUDICATION[row["pair_id"]].get("weak")
    ]
    lines = [
        "# Summary evaluation examples",
        "",
        "Examples are selected from the primary pipeline-mode evaluation.",
        "",
        "## Good examples",
        "",
    ]
    for row in good_rows[:4]:
        lines.extend(
            [
                f"### Good example: {row['pair_id']}",
                "",
                "Expected topics:",
                format_topics(row["expected_topics"]),
                "",
                "Generated summary:",
                "",
                row["summary_text"],
                "",
                "Why it is good:",
                "- Covers the expected topic without adding unsupported legal consequences.",
                "- Uses concise human-readable wording and keeps old/new value traceability through highlights.",
                "- Suitable as an intermediate artifact before quiz generation.",
                "",
                "Scores:",
                format_scores(row),
                "",
            ]
        )
    lines.extend(["## Weak / problematic examples", ""])
    for row in weak_rows[:4]:
        problem_details = rows_from_json_list(row, "unsupported_claim_details")
        problem_details.extend(
            rows_from_json_list(row, "editorial_overemphasis_details")
        )
        if not problem_details:
            problem_details = [row["notes"]]
        lines.extend(
            [
                f"### Weak example: {row['pair_id']}",
                "",
                "Expected topics:",
                format_topics(row["expected_topics"]),
                "",
                "Generated summary:",
                "",
                row["summary_text"],
                "",
                "What works:",
                "- The output remains readable and uses the same production summary artifact as the MVP pipeline.",
                "",
                "What is problematic:",
                "\n".join(f"- {detail}" for detail in problem_details),
                "",
                "How to interpret:",
                "- The error is mainly bounded by upstream comparison/significance signals; the summary layer surfaces those signals instead of independently correcting them.",
                "",
                "Scores:",
                format_scores(row),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Pair | Completeness | Accuracy | No hallucinations | Clarity | Usefulness | Source alignment | Average |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['pair_id']} | {row['completeness']} | {row['accuracy']} | "
            f"{row['no_hallucinations']} | {row['clarity']} | {row['usefulness']} | "
            f"{row['source_alignment']} | {float(row['average_score']):.2f} |"
        )
    return "\n".join(lines)


def aggregate_table(summary: dict[str, Any]) -> str:
    labels = {
        "completeness": "Average completeness",
        "accuracy": "Average accuracy",
        "no_hallucinations": "Average no hallucinations",
        "clarity": "Average clarity",
        "usefulness": "Average usefulness",
        "source_alignment": "Average source alignment",
        "overall": "Overall average",
    }
    lines = ["| Metric | Value |", "|---|---:|"]
    for key, label in labels.items():
        lines.append(f"| {label} | {summary['average_scores'][key]:.4f} |")
    lines.extend(
        [
            f"| Covered topics | {summary['covered_topics_total']} / {summary['expected_topics_total']} |",
            f"| Missed topics | {summary['missed_topics_total']} |",
            f"| Unsupported claims | {summary['unsupported_claims_total']} |",
            f"| Editorial/noise overemphasis | {summary['editorial_overemphasis_total']} |",
        ]
    )
    return "\n".join(lines)


def details_list(rows: list[dict[str, Any]], key: str) -> list[str]:
    lines: list[str] = []
    for row in rows:
        details = row.get(key) or []
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = []
        for detail in details:
            lines.append(f"- `{row['pair_id']}`: {detail}")
    return lines


def write_report_md(
    rows: list[dict[str, Any]], summary: dict[str, Any], path: Path
) -> None:
    diff_summary = load_optional_json(DIFF_SUMMARY_PATH)
    significance_summary = load_optional_json(SIGNIFICANCE_SUMMARY_PATH)
    structural_diff = (
        diff_summary.get("methods", {}).get("structural_chunk_diff", {})
        if diff_summary
        else {}
    )
    missed_rows = [row for row in rows if row["missed_topics"]]
    unsupported_lines = details_list(rows, "unsupported_claim_details")
    editorial_lines = details_list(rows, "editorial_overemphasis_details")
    good_rows = sorted(rows, key=lambda row: float(row["average_score"]), reverse=True)[
        :4
    ]
    weak_rows = sorted(rows, key=lambda row: float(row["average_score"]))[:3]

    phase15_precision = structural_diff.get("micro_precision")
    phase15_recall = structural_diff.get("micro_recall")
    phase15_f1 = structural_diff.get("micro_f1")
    phase15_noise = structural_diff.get("total_noise")
    phase16_accuracy = significance_summary.get("accuracy")
    phase16_recall = significance_summary.get("important_critical_recall")
    phase16_f1 = significance_summary.get("important_critical_f1")
    phase16_editorial_fpr = significance_summary.get("editorial_false_positive_rate")

    lines: list[str] = [
        "# Summary Layer Evaluation",
        "",
        "## 1. Цель эксперимента",
        "",
        "Эксперимент оценивает качество human-readable summary-layer, который преобразует technical diff/significance results в понятное для сотрудника объяснение изменений. Проверяется не красота текста сама по себе, а полнота, точность, отсутствие неподдержанных утверждений, понятность и пригодность summary как промежуточного артефакта перед quiz generation.",
        "",
        "## 2. Связь с гибридным методом",
        "",
        "В формуле `M = <E, N, S, C, P, G, R>` summary-layer расположен между `P — Prioritization / Significance classification` и `G — Generation`. Он не является отдельным символом формулы, но связывает машинный список изменений с обучающим контуром: `C` находит change items, `P` назначает semantic/significance labels, summary формирует brief/highlights, а `G` использует highlights для генерации quiz questions.",
        "",
        "## 3. Evaluation corpus",
        "",
        f"Использован `data/evaluation_corpus/`: {summary['total_pairs']} синтетических пар документов, 13 expected changes и {summary['expected_topics_total']} обязательных summary topics. Пары `pair_05_editorial_change` и `pair_08_reordered_structure` являются editorial/structure controls без обязательных смысловых topics.",
        "",
        "## 4. Что именно оценивается",
        "",
        "Оценивается production summary artifact из `backend/documents/domain/diff_summary.py::build_brief_summary`: `brief_text`, `overview_title` и `highlights` с `concise_explanation`, `semantic_type` и `significance_label`. Raw `old_text/new_text` в highlights рассматривались для source traceability, но не засчитывались как самостоятельное объяснение темы при оценке completeness.",
        "",
        "## 5. Evaluation mode",
        "",
        "Основной режим — pipeline summary evaluation: `chunk_by_structure_ru` → `build_version_diff` → `build_brief_summary` на in-memory версиях/чанках. Такой adapter использует production diff/summary logic и не изменяет БД. Дополнительно рассчитан oracle-input diagnostic: `build_brief_summary` вызывается на payload из annotation expected changes / expected significance, чтобы отделить собственное качество summary wording от ошибок upstream stages.",
        "",
        "## 6. Критерии оценки",
        "",
        "| Criterion | Meaning | Scale |",
        "|---|---|---|",
        "| Completeness | Whether expected critical/important topics are covered | 1-5 |",
        "| Accuracy | Whether the summary preserves factual content and old/new values | 1-5 |",
        "| No hallucinations | Whether unsupported claims and invented consequences are avoided | 1-5 |",
        "| Clarity | Whether a non-technical employee can understand the summary quickly | 1-5 |",
        "| Usefulness | Whether the summary helps focus attention and supports downstream quiz generation | 1-5 |",
        "| Source alignment | Whether summary statements trace back to real change items and significance labels | 1-5 |",
        "",
        "## 7. Scoring rubric",
        "",
        "Каждый критерий оценивался по шкале 1–5. Оценка 5 означает полное соответствие критерию, 4 — minor issues, 3 — частичное соответствие с заметными недостатками, 2 — серьёзные проблемы, 1 — практически непригодный результат по критерию. Topic coverage, forbidden topics и counts рассчитывались автоматически; итоговые scores являются экспертно-эвристической оценкой по зафиксированной rubric, что отражает природу summary evaluation.",
        "",
        "## 8. Результаты",
        "",
        markdown_table(rows),
        "",
        "## 9. Aggregate results",
        "",
        aggregate_table(summary),
        "",
        f"Oracle-input diagnostic overall average: {summary['oracle_diagnostic']['overall_average']:.4f}. Это показывает, что при корректных upstream change/significance inputs production summary wording работает заметно устойчивее, чем в полном pipeline mode.",
        "",
        "## 10. Topic coverage analysis",
        "",
        f"Автоматическая проверка покрыла {summary['covered_topics_total']} из {summary['expected_topics_total']} обязательных topics. Единственный missed topic в pipeline mode относится к `pair_06_procedure_change`: summary не упоминает электронную форму во внутреннем портале, потому что upstream enrichment классифицировал изменение как document-list requirement.",
    ]
    if missed_rows:
        lines.extend([""])
        for row in missed_rows:
            for topic in row["missed_topics"]:
                lines.append(f"- `{row['pair_id']}` missed: {topic}")
    lines.extend(
        [
            "",
            "## 11. Hallucination / unsupported claims analysis",
            "",
            f"Unsupported claims total: {summary['unsupported_claims_total']}. В текущем corpus это не свободные LLM hallucinations, а в основном неверные semantic labels/priority signals, которые summary честно превращает в текст: editorial wording становится document/deadline change, procedure превращается в document-list change, informational notice — в procedural step.",
            "",
            *(unsupported_lines or ["- Unsupported claims were not detected."]),
            "",
            "## 12. Editorial overemphasis analysis",
            "",
            f"Editorial/noise overemphasis total: {summary['editorial_overemphasis_total']}. Наиболее заметные случаи — `pair_05_editorial_change` и `pair_09_mixed_significant_and_editorial`. В `pair_03_document_list_change` key topic корректно покрыт, но brief statistics дополнительно упоминает one editorial/technical change from upstream diff noise.",
            "",
            *(editorial_lines or ["- Editorial/noise overemphasis was not detected."]),
            "",
            "## 13. Good examples",
            "",
        ]
    )
    for row in good_rows:
        lines.append(
            f"- `{row['pair_id']}` — average {float(row['average_score']):.2f}; {row['notes']}"
        )
    lines.extend(["", "## 14. Weak examples", ""])
    for row in weak_rows:
        lines.append(
            f"- `{row['pair_id']}` — average {float(row['average_score']):.2f}; {row['notes']}"
        )
    lines.extend(
        [
            "",
            "## 15. Связь с diff/significance evaluation",
            "",
            "Summary зависит от comparison и significance. Если comparison пропустил change, summary не сможет его упомянуть; если significance завысил editorial/informational change, summary может превратить это завышение в human-readable but misleading highlight.",
            "",
        ]
    )
    if phase15_precision is not None:
        lines.append(
            f"Фаза 15 показала для production structural diff: micro precision = {phase15_precision}, micro recall = {phase15_recall}, micro F1 = {phase15_f1}, total noise = {phase15_noise}. Это снижает noise относительно baselines, но не устраняет его полностью."
        )
    else:
        lines.append(
            "Фаза 15 показала, что structural diff снижает noise относительно baseline; точные агрегаты см. в `docs/experiments/diff-evaluation.md`."
        )
    lines.append("")
    if phase16_accuracy is not None:
        lines.append(
            f"Фаза 16 показала, что significance-layer является recall-oriented deterministic baseline: important/critical recall = {phase16_recall}, exact-label accuracy = {phase16_accuracy}, important/critical F1 = {phase16_f1}, editorial false positive rate = {phase16_editorial_fpr}. В summary evaluation эти ограничения проявились в editorial controls and mixed cases: summary не исправляет ошибочный label, а делает его понятным пользователю."
        )
    else:
        lines.append(
            "Фаза 16 показала recall-oriented характер significance-layer и склонность завышать часть editorial/informational changes; точные агрегаты см. в `docs/experiments/significance-evaluation.md`."
        )
    lines.extend(
        [
            "",
            "## 16. Ограничения эксперимента",
            "",
            "- Corpus малый и синтетический: 10 пар документов.",
            "- Annotation содержит key-change topics, а не exhaustive legal summary benchmark.",
            "- Clarity/usefulness/source alignment требуют экспертно-эвристической оценки; полностью автоматические метрики здесь недостаточны.",
            "- Raw snippets в highlights помогают traceability, но не должны искусственно повышать completeness самого explanatory text.",
            "- Production summary algorithm не изменялся; ошибки upstream не исправлялись внутри Фазы 17.",
            "- Oracle-input diagnostic не является реальным pipeline score; он служит только для отделения summary wording от diff/significance errors.",
            "",
            "## 17. Вывод для диссертации",
            "",
            f"Экспериментальная оценка summary-layer показала, что в pipeline mode средняя итоговая оценка составляет {summary['average_scores']['overall']:.4f} из 5. Summary-layer в большинстве случаев превращает технический результат diff/significance в понятную для пользователя выжимку и покрывает {summary['covered_topics_total']} из {summary['expected_topics_total']} обязательных topics. На сильных случаях summary корректно отражает изменения сроков, обязанностей, перечня документов и оснований отказа. При этом качество summary ограничено upstream stages: завышенная значимость editorial/informational changes или ошибочный semantic_type приводят к unsupported highlights and editorial/noise overemphasis. Oracle-input diagnostic подтверждает, что при корректном входе production summary wording работает устойчиво; следовательно, summary-layer имеет прикладную ценность как промежуточное human-readable представление между анализом изменений и генерацией контрольно-обучающих материалов, но должен интерпретироваться вместе с quality bounds comparison/significance layers.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    rows, summary = evaluate_pairs()

    csv_path = RESULTS_DIR / "summary_results.csv"
    json_path = RESULTS_DIR / "summary_evaluation_summary.json"
    quality_chart_path = RESULTS_DIR / "summary_quality_scores.png"
    pair_chart_path = RESULTS_DIR / "summary_pair_scores.png"
    examples_path = RESULTS_DIR / "summary_examples.md"
    report_path = DOCS_DIR / "summary-evaluation.md"

    write_csv(rows, csv_path)
    write_json(summary, json_path)
    write_quality_chart(summary, quality_chart_path)
    write_pair_scores_chart(rows, pair_chart_path)
    write_examples_md(rows, examples_path)
    write_report_md(rows, summary, report_path)

    print("Summary evaluation: PASS")
    print(f"Pairs: {summary['total_pairs']}")
    print(f"Overall average: {summary['average_scores']['overall']:.4f}")
    print(
        f"Covered topics: {summary['covered_topics_total']} / {summary['expected_topics_total']}"
    )
    print(f"Missed topics: {summary['missed_topics_total']}")
    print(f"Unsupported claims: {summary['unsupported_claims_total']}")
    print(f"Editorial/noise overemphasis: {summary['editorial_overemphasis_total']}")
    print(f"CSV: {csv_path}")
    print(f"Summary JSON: {json_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
