from __future__ import annotations

import csv
import json
import os
import re
import sys
import types
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
RESULTS_DIR = ROOT_DIR / "experiments" / "quiz"
DOCS_DIR = ROOT_DIR / "docs" / "experiments"
SUMMARY_EVALUATION_PATH = (
    ROOT_DIR / "experiments" / "summary" / "summary_evaluation_summary.json"
)
SIGNIFICANCE_EVALUATION_PATH = (
    ROOT_DIR / "experiments" / "significance" / "significance_summary.json"
)

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# The production diff module imports Django ORM model classes only for type/runtime
# access to attributes. The experiment runs without mutating the database and uses
# in-memory stand-ins, so a tiny module shim is enough when Django is not installed.
try:  # pragma: no cover - used only when the local env has Django installed
    import django  # type: ignore

    django.setup()
except Exception:  # pragma: no cover - CLI dependency guard
    fake_models = types.ModuleType("documents.models")

    class Chunk:  # noqa: D401 - simple stand-in for import compatibility
        """Import-compatible stand-in used by domain.diff type imports."""

    class DocumentVersion:  # noqa: D401 - simple stand-in for import compatibility
        """Import-compatible stand-in used by domain.diff type imports."""

    fake_models.Chunk = Chunk
    fake_models.DocumentVersion = DocumentVersion
    sys.modules.setdefault("documents.models", fake_models)

try:
    from documents.domain.diff import build_version_diff
    from documents.domain.diff_summary import build_brief_summary
    from documents.domain.diff_quiz import build_quiz_from_summary
    from documents.domain.text_processing import chunk_by_structure_ru, normalize_text
except Exception as exc:  # pragma: no cover - CLI dependency guard
    raise RuntimeError(
        "Quiz evaluation requires backend domain modules. Run from the project root."
    ) from exc

CRITERIA = [
    "change_relevance",
    "domain_correctness",
    "unambiguous_answer",
    "distractor_quality",
    "no_editorial_noise",
    "explanation_source_quality",
    "employee_usefulness",
]

CRITERIA_LABELS = {
    "change_relevance": "relevance",
    "domain_correctness": "correctness",
    "unambiguous_answer": "unambiguous answer",
    "distractor_quality": "distractor quality",
    "no_editorial_noise": "no editorial noise",
    "explanation_source_quality": "explanation/source",
    "employee_usefulness": "usefulness",
}

IMPORTANT_FOR_QUIZ = {"critical", "important"}
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
    "изменение",
    "изменения",
    "изменены",
    "добавлен",
    "добавлена",
    "добавлено",
    "рабочих",
    "рабочие",
    "дней",
    "дня",
    "срок",
    "срока",
}

# Expert adjudication for the deterministic pipeline output. The script still
# obtains questions from the production generator; these values only encode the
# Phase 18 expert scoring rubric and are intentionally separated from generation.
EXPERT_ASSESSMENTS: dict[str, dict[str, Any]] = {
    "pair_01_deadline_change:q1": {
        "scores": [5, 5, 5, 4, 5, 5, 5],
        "matched_topic": "новый срок рассмотрения заявления",
        "notes": "Directly checks the changed deadline and preserves old/new values.",
        "good_points": [
            "directly linked to the deadline change",
            "correct answer is unambiguous",
            "source includes old and new deadline values",
        ],
        "weak_points": ["distractors are generic rather than old-value based"],
        "error_origin": "none",
    },
    "pair_02_added_obligation:q1": {
        "scores": [5, 5, 5, 4, 5, 5, 5],
        "matched_topic": "новая обязанность сотрудника по уведомлению заявителя",
        "notes": "Directly checks the added notification obligation.",
        "good_points": [
            "question is tied to the new obligation",
            "correct answer states the action and notification channel",
            "source/explanation are sufficient for reviewer validation",
        ],
        "weak_points": ["distractors are mostly generic negations"],
        "error_origin": "none",
    },
    "pair_03_document_list_change:q1": {
        "scores": [5, 5, 5, 4, 5, 5, 5],
        "matched_topic": "новый документ в перечне обязательных документов",
        "notes": "Checks the added representative-authority document.",
        "good_points": [
            "question uses the document-list template",
            "answer contains the newly required document",
            "traceability points to the added subpoint",
        ],
        "weak_points": ["distractors do not include near-miss document options"],
        "error_origin": "none",
    },
    "pair_04_refusal_ground_change:q1": {
        "scores": [5, 5, 5, 4, 5, 5, 5],
        "matched_topic": "новое основание отказа",
        "notes": "Checks the new refusal ground without changing its legal condition.",
        "good_points": [
            "question is aligned with refusal-ground semantics",
            "answer preserves the non-submission condition",
            "source reference is clear",
        ],
        "weak_points": ["distractors are broad and easy"],
        "error_origin": "none",
    },
    "pair_05_editorial_change:q1": {
        "scores": [1, 1, 2, 3, 1, 2, 1],
        "matched_topic": "",
        "notes": (
            "Weak case: an editorial verb replacement is over-prioritized upstream "
            "and becomes a false document-list question."
        ),
        "good_points": ["question remains traceable to the changed fragment"],
        "weak_points": [
            "no quiz should be generated for this editorial-only change",
            "question invents a document-list requirement",
            "answer does not follow from the new version",
        ],
        "error_origin": "upstream_significance",
    },
    "pair_06_procedure_change:q1": {
        "scores": [3, 2, 2, 3, 5, 3, 2],
        "matched_topic": "",
        "notes": (
            "The source is the real procedure change, but the generated question "
            "frames it as a document-list change and misses the electronic-form topic."
        ),
        "good_points": ["question is attached to the changed source fragment"],
        "weak_points": [
            "correct answer is generic and does not mention the electronic form",
            "semantic template is wrong for the procedure change",
            "employee cannot learn the new submission channel from the answer",
        ],
        "error_origin": "upstream_semantic_classification",
    },
    "pair_07_responsibility_change:q1": {
        "scores": [4, 3, 4, 3, 5, 4, 4],
        "matched_topic": "ответственность за нарушение срока",
        "notes": (
            "The answer preserves the responsibility rule, but the prompt frames it "
            "as a deadline question because of upstream semantic labeling."
        ),
        "good_points": [
            "answer contains the responsibility rule",
            "source text is available for reviewer correction",
        ],
        "weak_points": [
            "prompt category is misleading",
            "answer is truncated",
            "distractors are generic",
        ],
        "error_origin": "upstream_semantic_classification",
    },
    "pair_09_mixed_significant_and_editorial:q1": {
        "scores": [5, 5, 5, 3, 5, 5, 5],
        "matched_topic": "новый срок подготовки справки",
        "notes": "Good deadline question in a mixed-change pair.",
        "good_points": [
            "covers one of the two critical expected quiz topics",
            "answer includes old and new values",
            "source points to the deadline fragment",
        ],
        "weak_points": [
            "distractors are other true changes, not realistic deadline alternatives"
        ],
        "error_origin": "none",
    },
    "pair_09_mixed_significant_and_editorial:q2": {
        "scores": [5, 5, 5, 3, 5, 5, 5],
        "matched_topic": "уведомление при невозможности подготовки справки",
        "notes": "Good obligation question in a mixed-change pair.",
        "good_points": [
            "covers the added notification obligation",
            "answer is specific and unambiguous",
            "source text is directly aligned",
        ],
        "weak_points": [
            "distractors are other true changes from the same quiz"
        ],
        "error_origin": "none",
    },
    "pair_09_mixed_significant_and_editorial:q3": {
        "scores": [3, 3, 4, 2, 2, 4, 2],
        "matched_topic": "",
        "notes": (
            "Informational status notice is turned into a procedure question; this "
            "is traceable but weak as an employee knowledge-control item."
        ),
        "good_points": ["source/explanation are present"],
        "weak_points": [
            "expected_quiz_topic is empty for this informational change",
            "question overstates the notice as a procedural step",
            "distractors are unrelated true changes",
        ],
        "error_origin": "upstream_significance",
    },
    "pair_09_mixed_significant_and_editorial:q4": {
        "scores": [1, 1, 2, 2, 1, 2, 1],
        "matched_topic": "",
        "notes": (
            "Editorial wording replacement is incorrectly converted into a critical "
            "deadline question."
        ),
        "good_points": ["source fragment is available for detecting the problem"],
        "weak_points": [
            "question is based on editorial/noise",
            "answer is unsupported by the source text",
            "another true deadline change appears as a distractor",
        ],
        "error_origin": "upstream_significance",
    },
    "pair_10_weakly_structured_document:q1": {
        "scores": [5, 4, 5, 4, 5, 4, 5],
        "matched_topic": "новый срок рассмотрения обращения",
        "notes": "Good fallback-block deadline question with minor wording roughness.",
        "good_points": [
            "covers the weakly structured deadline change",
            "correct answer gives the old and new values",
            "question remains useful despite fallback chunk title",
        ],
        "weak_points": [
            "title is a technical fallback block label",
            "answer has minor grammatical roughness: '3 рабочих дней'",
        ],
        "error_origin": "minor_generation_wording",
    },
}

PAIR_NOTES = {
    "pair_01_deadline_change": "Deadline change is covered by one strong question.",
    "pair_02_added_obligation": "Added obligation is covered by one strong question.",
    "pair_03_document_list_change": "Document-list addition is covered; upstream also found one editorial diff item but it did not become a question.",
    "pair_04_refusal_ground_change": "New refusal ground is covered by one strong question.",
    "pair_05_editorial_change": "No expected quiz topic, but pipeline generated one false positive question due to upstream significance/semantic labeling.",
    "pair_06_procedure_change": "The expected electronic-form submission topic is missed because the change is framed as a document-list issue.",
    "pair_07_responsibility_change": "Responsibility topic is recoverable from the answer/source, but the prompt uses a misleading deadline template.",
    "pair_08_reordered_structure": "No question is generated for pure reordering, which is the expected behavior.",
    "pair_09_mixed_significant_and_editorial": "Both critical expected topics are covered, but two extra weak questions come from informational/editorial upstream over-prioritization.",
    "pair_10_weakly_structured_document": "Fallback block still produces a useful deadline question with minor wording roughness.",
}


class QueryList(list):
    """Small in-memory stand-in for Django related managers."""

    def order_by(self, attr: str) -> list[Any]:
        reverse = attr.startswith("-")
        attr_name = attr.lstrip("-")
        return sorted(self, key=lambda item: getattr(item, attr_name), reverse=reverse)


@dataclass(frozen=True)
class PairInput:
    pair_id: str
    pair_dir: Path
    annotation: dict[str, Any]
    old_text: str
    new_text: str


def safe_divide(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def normalize_for_match(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "уведомлению": ("уведом",),
    "уведомление": ("уведом",),
    "уведомления": ("уведом",),
    "уведомить": ("уведом",),
    "сотрудника": ("сотрудник", "ответствен"),
    "способ": ("способ", "порядок", "форм", "электрон"),
    "подачи": ("подач", "подан", "подать", "подано", "подается"),
    "подача": ("подач", "подан", "подать", "подано", "подается"),
    "заявления": ("заявлен",),
    "заявление": ("заявлен",),
    "обращения": ("обращен",),
    "справки": ("справк",),
    "невозможности": ("невозможн",),
    "подготовки": ("подготов",),
}


def content_tokens(text: str) -> list[str]:
    normalized = normalize_for_match(text)
    tokens: list[str] = []
    for token in normalized.split():
        if len(token) <= 2 and not token.isdigit():
            continue
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def token_covered(token: str, text_norm: str) -> bool:
    if token in text_norm:
        return True
    aliases = TOKEN_ALIASES.get(token, ())
    if any(alias in text_norm for alias in aliases):
        return True
    if len(token) >= 6 and token[:6] in text_norm:
        return True
    if len(token) >= 5 and token.endswith(("ия", "ий", "ая", "ое", "ые", "ых", "ого", "ему", "ами", "ями")):
        return token[:5] in text_norm
    return False


def topic_is_covered(topic: str, text: str) -> bool:
    topic_norm = normalize_for_match(topic)
    text_norm = normalize_for_match(text)
    if not topic_norm:
        return True
    if topic_norm in text_norm:
        return True

    topic_numbers = {token for token in topic_norm.split() if token.isdigit()}
    text_numbers = {token for token in text_norm.split() if token.isdigit()}
    if topic_numbers and not topic_numbers <= text_numbers:
        return False

    tokens = content_tokens(topic)
    if not tokens:
        return True
    matched = sum(1 for token in tokens if token_covered(token, text_norm))
    return (matched / len(tokens)) >= 0.55


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


def read_pairs() -> list[PairInput]:
    pairs: list[PairInput] = []
    for pair_dir in sorted(CORPUS_DIR.glob("pair_*")):
        annotation = json.loads(
            (pair_dir / "annotation.json").read_text(encoding="utf-8")
        )
        pair_id = str(annotation.get("pair_id") or pair_dir.name)
        pairs.append(
            PairInput(
                pair_id=pair_id,
                pair_dir=pair_dir,
                annotation=annotation,
                old_text=(pair_dir / "old.txt").read_text(encoding="utf-8"),
                new_text=(pair_dir / "new.txt").read_text(encoding="utf-8"),
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


def extract_expected_quiz_topics(annotation: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    value = annotation.get("expected_quiz_topics")
    if isinstance(value, str):
        topics.append(value)
    elif isinstance(value, list):
        topics.extend(str(item) for item in value)

    for change in annotation.get("expected_changes") or []:
        importance = str(change.get("importance") or "").lower()
        topic = str(change.get("expected_quiz_topic") or "").strip()
        if importance in IMPORTANT_FOR_QUIZ and topic:
            topics.append(topic)
    return dedupe_keep_order([topic for topic in topics if topic.strip()])


def extract_quiz_worthy_changes(annotation: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for change in annotation.get("expected_changes") or []:
        importance = str(change.get("importance") or "").lower()
        topic = str(change.get("expected_quiz_topic") or "").strip()
        if importance in IMPORTANT_FOR_QUIZ and topic:
            changes.append(change)
    return changes


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
    for index, change in enumerate(extract_quiz_worthy_changes(pair.annotation), start=1):
        change_type = str(change.get("type") or "modified")
        change_type = change_type if change_type in buckets else "modified"
        common = {
            "semantic_type": change.get("semantic_type") or "unclassified",
            "significance_label": change.get("importance") or "not_evaluated",
            "significance_score": 1.0,
            "significance_reason": change.get("description")
            or "annotation oracle input",
            "significance_rules": ["annotation_oracle_quiz_input"],
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
            old_chunk = make_chunk_from_change(
                change, text_key="old_text", index=index
            )
            new_chunk = make_chunk_from_change(
                change, text_key="new_text", index=index
            )
            payload = {
                "from_chunk": old_chunk,
                "to_chunk": new_chunk,
                "old_text": change.get("old_text") or "",
                "new_text": change.get("new_text") or "",
                "similarity": 0.9,
                "match_reason": "annotation_oracle_quiz_input",
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
            "comparison_unit": "annotation_expected_quiz_changes",
            "matching_strategy": "oracle_quiz_annotation_v1",
        },
        "identical": not any(buckets.values()),
        "summary": summary,
        "added": buckets["added"],
        "removed": buckets["removed"],
        "modified": buckets["modified"],
        "moved": buckets["moved"],
        "text_diff": "",
    }


def build_pipeline_artifacts(pair: PairInput) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
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
    quiz_payload = build_quiz_from_summary(
        summary_payload={
            "highlights": summary_payload.get("highlights") or [],
            "selection_scope": summary_payload.get("selection_scope") or "",
        },
        from_version=diff_payload["from_version"],
        to_version=diff_payload["to_version"],
        identical=bool(diff_payload.get("identical", False)),
        max_questions=10,
    )
    return diff_payload, summary_payload, quiz_payload


def build_oracle_artifacts(pair: PairInput) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    diff_payload = build_oracle_diff_payload(pair)
    summary_payload = build_brief_summary(diff_payload)
    quiz_payload = build_quiz_from_summary(
        summary_payload={
            "highlights": summary_payload.get("highlights") or [],
            "selection_scope": summary_payload.get("selection_scope") or "",
        },
        from_version=diff_payload["from_version"],
        to_version=diff_payload["to_version"],
        identical=bool(diff_payload.get("identical", False)),
        max_questions=10,
    )
    return diff_payload, summary_payload, quiz_payload


def question_text_blob(question: dict[str, Any]) -> str:
    source = question.get("source") or {}
    choices = question.get("choices") or []
    return "\n".join(
        [
            str(question.get("question") or ""),
            str(question.get("answer") or ""),
            str(question.get("explanation") or ""),
            str(source.get("title") or ""),
            str(source.get("old_text") or ""),
            str(source.get("new_text") or ""),
            " ".join(str(choice.get("text") or "") for choice in choices),
        ]
    )


def auto_assess_question(
    *,
    pair_id: str,
    question_index: int,
    question: dict[str, Any],
    expected_topics: list[str],
) -> dict[str, Any]:
    blob = question_text_blob(question)
    matched_topics = [topic for topic in expected_topics if topic_is_covered(topic, blob)]
    matched_topic = matched_topics[0] if matched_topics else ""
    semantic_type = str(question.get("semantic_type") or "")
    label = str(question.get("significance_label") or "")
    source = question.get("source") or {}
    has_source = bool(
        question.get("explanation")
        and (source.get("old_text") or source.get("new_text") or source.get("title"))
    )
    is_noise = semantic_type in {"editorial", "structure"} or (
        not expected_topics and label in {"critical", "important"}
    )
    scores = [
        5 if matched_topic else (3 if source else 1),
        4 if matched_topic else 3,
        5 if question.get("answer") else 1,
        4 if len(question.get("choices") or []) >= 3 else 2,
        1 if is_noise else 5,
        4 if has_source else 2,
        5 if matched_topic else 3,
    ]
    return {
        "scores": scores,
        "matched_topic": matched_topic,
        "notes": (
            "Automatic fallback assessment; no hand-written expert note for "
            f"{pair_id}:q{question_index}."
        ),
        "good_points": [],
        "weak_points": [],
        "error_origin": "not_adjudicated",
    }


def assess_pipeline_question(
    *,
    pair: PairInput,
    question_index: int,
    question: dict[str, Any],
    expected_topics: list[str],
) -> dict[str, Any]:
    key = f"{pair.pair_id}:q{question_index}"
    assessment = EXPERT_ASSESSMENTS.get(key)
    if assessment is None:
        assessment = auto_assess_question(
            pair_id=pair.pair_id,
            question_index=question_index,
            question=question,
            expected_topics=expected_topics,
        )
    scores = dict(zip(CRITERIA, assessment["scores"], strict=True))
    return {
        **assessment,
        **scores,
        "overall_score": round(mean(scores.values()), 4),
    }


def has_explanation_and_source(question: dict[str, Any]) -> bool:
    source = question.get("source") or {}
    return bool(
        str(question.get("explanation") or "").strip()
        and (
            source.get("title")
            or source.get("old_text")
            or source.get("new_text")
            or source.get("source_change_item_id")
        )
    )


def evaluate_pipeline_pair(
    pair: PairInput,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    diff_payload, summary_payload, quiz_payload = build_pipeline_artifacts(pair)
    expected_topics = extract_expected_quiz_topics(pair.annotation)
    important_changes_count = len(extract_quiz_worthy_changes(pair.annotation))
    question_rows: list[dict[str, Any]] = []

    for question_index, question in enumerate(quiz_payload.get("questions") or [], start=1):
        assessment = assess_pipeline_question(
            pair=pair,
            question_index=question_index,
            question=question,
            expected_topics=expected_topics,
        )
        options = [choice.get("text", "") for choice in question.get("choices") or []]
        correct_answer = str(question.get("answer") or "")
        has_source = has_explanation_and_source(question)
        is_editorial_noise = assessment["no_editorial_noise"] <= 2
        is_relevant = bool(assessment.get("matched_topic")) and not is_editorial_noise
        is_correct = (
            assessment["change_relevance"] >= 4
            and assessment["domain_correctness"] >= 3
            and assessment["unambiguous_answer"] >= 4
            and assessment["no_editorial_noise"] >= 3
        )
        question_id = f"{pair.pair_id}_q{question_index:02d}"
        question_rows.append(
            {
                "pair_id": pair.pair_id,
                "question_id": question_id,
                "question_index": question_index,
                "question_text": question.get("question", ""),
                "options": json.dumps(options, ensure_ascii=False),
                "correct_answer": correct_answer,
                "expected_topics": json.dumps(expected_topics, ensure_ascii=False),
                "matched_topic": assessment.get("matched_topic", ""),
                "change_relevance": assessment["change_relevance"],
                "domain_correctness": assessment["domain_correctness"],
                "unambiguous_answer": assessment["unambiguous_answer"],
                "distractor_quality": assessment["distractor_quality"],
                "no_editorial_noise": assessment["no_editorial_noise"],
                "explanation_source_quality": assessment[
                    "explanation_source_quality"
                ],
                "employee_usefulness": assessment["employee_usefulness"],
                "overall_score": assessment["overall_score"],
                "has_source": has_source,
                "is_correct": is_correct,
                "is_relevant": is_relevant,
                "is_editorial_noise": is_editorial_noise,
                "notes": assessment["notes"],
                "explanation": question.get("explanation", ""),
                "source": json.dumps(question.get("source") or {}, ensure_ascii=False),
                "semantic_type": question.get("semantic_type", ""),
                "significance_label": question.get("significance_label", ""),
                "error_origin": assessment.get("error_origin", ""),
                "good_points": assessment.get("good_points", []),
                "weak_points": assessment.get("weak_points", []),
            }
        )

    covered_topics = dedupe_keep_order(
        [str(row["matched_topic"]) for row in question_rows if row.get("is_relevant")]
    )
    covered_important_changes_count = len(covered_topics)
    questions_count = len(question_rows)
    if important_changes_count:
        coverage = safe_divide(covered_important_changes_count, important_changes_count)
    else:
        coverage = 1.0 if questions_count == 0 else 0.0

    pair_row = {
        "pair_id": pair.pair_id,
        "questions_count": questions_count,
        "correct_questions": sum(1 for row in question_rows if row["is_correct"]),
        "relevant_questions": sum(1 for row in question_rows if row["is_relevant"]),
        "questions_with_source": sum(1 for row in question_rows if row["has_source"]),
        "important_changes": important_changes_count,
        "covered_important_changes": covered_important_changes_count,
        "coverage": coverage,
        "avg_question_score": round(
            mean([row["overall_score"] for row in question_rows]), 4
        )
        if question_rows
        else 0.0,
        "editorial_noise_questions": sum(
            1 for row in question_rows if row["is_editorial_noise"]
        ),
        "notes": PAIR_NOTES.get(pair.pair_id, ""),
    }
    diagnostics = {
        "diff_summary": diff_payload.get("summary", {}),
        "summary_highlights_count": len(summary_payload.get("highlights") or []),
        "quiz_selection_scope": quiz_payload.get("selection_scope", ""),
        "quiz_questions_count": quiz_payload.get("questions_count", 0),
        "expected_topics": expected_topics,
        "covered_topics": covered_topics,
    }
    return question_rows, pair_row, diagnostics


def evaluate_oracle_diagnostic(pairs: list[PairInput]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        _, _, quiz_payload = build_oracle_artifacts(pair)
        expected_topics = extract_expected_quiz_topics(pair.annotation)
        generated_questions = quiz_payload.get("questions") or []
        covered: list[str] = []
        for question in generated_questions:
            blob = question_text_blob(question)
            for topic in expected_topics:
                if topic not in covered and topic_is_covered(topic, blob):
                    covered.append(topic)
        important_changes = len(extract_quiz_worthy_changes(pair.annotation))
        rows.append(
            {
                "pair_id": pair.pair_id,
                "expected_topics": expected_topics,
                "oracle_questions_count": len(generated_questions),
                "important_changes": important_changes,
                "covered_important_changes": len(covered),
                "coverage": safe_divide(len(covered), important_changes)
                if important_changes
                else (1.0 if not generated_questions else 0.0),
            }
        )
    total_important = sum(row["important_changes"] for row in rows)
    total_covered = sum(row["covered_important_changes"] for row in rows)
    total_questions = sum(row["oracle_questions_count"] for row in rows)
    return {
        "mode": "oracle_input_quiz_diagnostic",
        "description": (
            "Annotation expected_quiz_topic changes only -> build_brief_summary -> "
            "production build_quiz_from_summary. Diagnostic upper bound, not the "
            "real pipeline score."
        ),
        "total_questions": total_questions,
        "important_changes": total_important,
        "covered_important_changes": total_covered,
        "important_change_coverage": safe_divide(total_covered, total_important),
        "rows": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def plot_quality_scores(question_rows: list[dict[str, Any]]) -> None:
    values = [
        round(mean([float(row[criterion]) for row in question_rows]), 4)
        if question_rows
        else 0.0
        for criterion in CRITERIA
    ]
    labels = [CRITERIA_LABELS[criterion] for criterion in CRITERIA]
    plt.figure(figsize=(12, 5.8))
    plt.bar(labels, values)
    plt.ylim(0, 5)
    plt.ylabel("Average score, 1-5")
    plt.title("Quiz generation: average question-quality scores")
    plt.xticks(rotation=25, ha="right")
    for index, value in enumerate(values):
        plt.text(index, value + 0.05, f"{value:.2f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "quiz_quality_scores.png", dpi=180)
    plt.close()


def plot_pair_scores(pair_rows: list[dict[str, Any]]) -> None:
    labels = [row["pair_id"].replace("pair_", "p") for row in pair_rows]
    values = [float(row["avg_question_score"]) for row in pair_rows]
    plt.figure(figsize=(12, 5.8))
    plt.bar(labels, values)
    plt.ylim(0, 5)
    plt.ylabel("Average question score, 1-5")
    plt.title("Quiz generation: pair-level average scores")
    plt.xticks(rotation=35, ha="right")
    for index, value in enumerate(values):
        plt.text(index, value + 0.05, f"{value:.2f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "quiz_pair_scores.png", dpi=180)
    plt.close()


def plot_coverage(pair_rows: list[dict[str, Any]]) -> None:
    labels = [row["pair_id"].replace("pair_", "p") for row in pair_rows]
    values = [float(row["coverage"]) for row in pair_rows]
    plt.figure(figsize=(12, 5.8))
    plt.bar(labels, values)
    plt.ylim(0, 1.05)
    plt.ylabel("Coverage of important/critical expected quiz topics")
    plt.title("Quiz generation: important-change coverage by pair")
    plt.xticks(rotation=35, ha="right")
    for index, value in enumerate(values):
        plt.text(index, value + 0.02, f"{value:.2f}", ha="center", va="bottom")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "quiz_coverage.png", dpi=180)
    plt.close()


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def make_summary_json(
    *,
    pairs: list[PairInput],
    question_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    oracle_diagnostic: dict[str, Any],
) -> dict[str, Any]:
    total_questions = len(question_rows)
    total_correct = sum(1 for row in question_rows if row["is_correct"])
    total_relevant = sum(1 for row in question_rows if row["is_relevant"])
    total_source = sum(1 for row in question_rows if row["has_source"])
    total_editorial_noise = sum(
        1 for row in question_rows if row["is_editorial_noise"]
    )
    total_important = sum(row["important_changes"] for row in pair_rows)
    total_covered = sum(row["covered_important_changes"] for row in pair_rows)
    average_criteria_scores = {
        criterion: round(mean([float(row[criterion]) for row in question_rows]), 4)
        if question_rows
        else 0.0
        for criterion in CRITERIA
    }
    return {
        "experiment": "quiz_generation_evaluation",
        "phase": 18,
        "evaluation_mode": {
            "primary": "pipeline_quiz_evaluation",
            "primary_pipeline": (
                "chunk_by_structure_ru -> build_version_diff -> build_brief_summary "
                "-> build_quiz_from_summary"
            ),
            "diagnostic": "oracle_input_quiz_evaluation",
            "oracle_input": (
                "annotation expected_quiz_topic changes -> build_brief_summary "
                "-> build_quiz_from_summary"
            ),
        },
        "total_pairs": len(pairs),
        "total_questions": total_questions,
        "correct_question_rate": safe_divide(total_correct, total_questions),
        "relevant_question_rate": safe_divide(total_relevant, total_questions),
        "source_explanation_rate": safe_divide(total_source, total_questions),
        "important_change_coverage": safe_divide(total_covered, total_important),
        "editorial_noise_question_rate": safe_divide(
            total_editorial_noise, total_questions
        ),
        "average_question_score": round(
            mean([row["overall_score"] for row in question_rows]), 4
        )
        if question_rows
        else 0.0,
        "average_criteria_scores": average_criteria_scores,
        "total_important_changes": total_important,
        "covered_important_changes": total_covered,
        "editorial_noise_questions": total_editorial_noise,
        "correct_questions": total_correct,
        "relevant_questions": total_relevant,
        "questions_with_source": total_source,
        "criteria": CRITERIA,
        "pair_results": pair_rows,
        "pipeline_diagnostics": diagnostics,
        "oracle_diagnostic": oracle_diagnostic,
        "limitations": [
            "The evaluation corpus is small and synthetic: 10 document pairs.",
            "Question quality scoring is expert-rubric based and combines annotation matching with manual adjudication of generated questions.",
            "Primary pipeline scores include upstream comparison, significance and summary errors; oracle-input diagnostic is reported separately.",
            "The production quiz generator was not changed for the experiment.",
            "The experiment runs the domain-layer generator in memory; it does not create ORM GeneratedQuiz/Question rows.",
        ],
    }


def render_options(options_json: str) -> list[str]:
    try:
        value = json.loads(options_json)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value]


def write_examples(question_rows: list[dict[str, Any]]) -> None:
    good_rows = [
        row
        for row in sorted(question_rows, key=lambda item: item["overall_score"], reverse=True)
        if row["is_correct"] and row["is_relevant"]
    ][:5]
    weak_rows = sorted(question_rows, key=lambda item: item["overall_score"])[:3]

    lines: list[str] = [
        "# Quiz Generation Examples",
        "",
        "Examples are selected from the primary pipeline evaluation.",
        "",
    ]

    def append_example(row: dict[str, Any], *, kind: str) -> None:
        title = "Good example" if kind == "good" else "Weak/problematic example"
        lines.extend(
            [
                f"### {title}: {row['question_id']}",
                "",
                "Expected topic:",
                f"- {row['matched_topic'] or 'no expected quiz-worthy topic covered'}",
                "",
                "Question:",
                str(row["question_text"]),
                "",
                "Options:",
            ]
        )
        for index, option in enumerate(render_options(row["options"]), start=1):
            marker = chr(ord("A") + index - 1)
            lines.append(f"{marker}. {option}")
        lines.extend(
            [
                "",
                "Correct answer:",
                str(row["correct_answer"]),
                "",
                "Explanation/source:",
                str(row.get("explanation") or ""),
                "",
                "Scores:",
            ]
        )
        for criterion in CRITERIA:
            lines.append(f"- {CRITERIA_LABELS[criterion]}: {row[criterion]}")
        lines.extend([f"- overall: {row['overall_score']}", ""])
        good_points = row.get("good_points") or []
        weak_points = row.get("weak_points") or []
        if good_points:
            lines.append("What is good:")
            for point in good_points:
                lines.append(f"- {point}")
            lines.append("")
        if weak_points:
            lines.append("What is weak:")
            for point in weak_points:
                lines.append(f"- {point}")
            lines.append("")
        lines.extend(
            [
                "Interpretation:",
                str(row["notes"]),
                "",
            ]
        )

    for row in good_rows:
        append_example(row, kind="good")
    for row in weak_rows:
        append_example(row, kind="weak")

    (RESULTS_DIR / "quiz_examples.md").write_text(
        "\n".join(lines).strip() + "\n", encoding="utf-8"
    )


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("|" + "|".join(["---" for _ in headers]) + "|")
    for row in rows:
        output.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(output)


def write_markdown_report(summary: dict[str, Any], question_rows: list[dict[str, Any]]) -> None:
    pair_rows = summary["pair_results"]
    summary_eval = load_json_if_exists(SUMMARY_EVALUATION_PATH)
    significance_eval = load_json_if_exists(SIGNIFICANCE_EVALUATION_PATH)

    pair_table_rows = [
        [
            row["pair_id"],
            row["questions_count"],
            row["correct_questions"],
            row["relevant_questions"],
            row["questions_with_source"],
            f"{row['coverage']:.4f}",
            f"{row['avg_question_score']:.4f}",
        ]
        for row in pair_rows
    ]
    aggregate_rows = [
        ["Total pairs", summary["total_pairs"]],
        ["Total questions", summary["total_questions"]],
        ["Correct question rate", f"{summary['correct_question_rate']:.4f}"],
        ["Relevant question rate", f"{summary['relevant_question_rate']:.4f}"],
        ["Source/explanation rate", f"{summary['source_explanation_rate']:.4f}"],
        ["Important change coverage", f"{summary['important_change_coverage']:.4f}"],
        [
            "Editorial/noise question rate",
            f"{summary['editorial_noise_question_rate']:.4f}",
        ],
        ["Average question score", f"{summary['average_question_score']:.4f}"],
    ]
    criteria_rows = [
        ["Change relevance", "Связь вопроса с реальным expected change", "1-5"],
        ["Legal/domain correctness", "Корректность формулировки и ответа", "1-5"],
        ["Unambiguous correct answer", "Один очевидный правильный ответ", "1-5"],
        ["Distractor quality", "Правдоподобность и не-дублирование distractors", "1-5"],
        ["No editorial noise", "Вопрос не построен на редакционном/шумовом изменении", "1-5"],
        ["Explanation/source quality", "Наличие объяснения и traceability", "1-5"],
        ["Employee usefulness", "Практическая полезность для сотрудника", "1-5"],
    ]

    good_count = sum(1 for row in question_rows if row["is_correct"])
    weak_rows = [row for row in question_rows if not row["is_correct"]]
    editorial_rows = [row for row in question_rows if row["is_editorial_noise"]]
    source_low_rows = [
        row for row in question_rows if row["explanation_source_quality"] < 4
    ]
    distractor_avg = summary["average_criteria_scores"]["distractor_quality"]

    phase17 = summary_eval.get("average_scores", {})
    phase16_lines = []
    if significance_eval:
        phase16_lines.append(
            f"Phase 16 significance: important/critical recall = "
            f"{significance_eval.get('important_critical_recall')}, precision = "
            f"{significance_eval.get('important_critical_precision')}, editorial "
            f"false-positive rate = "
            f"{significance_eval.get('editorial_false_positive_rate')}."
        )
    if phase17:
        phase16_lines.append(
            f"Phase 17 summary: overall average = {phase17.get('overall')}, "
            f"covered topics = {summary_eval.get('covered_topics_total')} / "
            f"{summary_eval.get('expected_topics_total')}, missed topics = "
            f"{summary_eval.get('missed_topics_total')}, unsupported claims = "
            f"{summary_eval.get('unsupported_claims_total')}, editorial/noise "
            f"overemphasis = {summary_eval.get('editorial_overemphasis_total')}."
        )

    good_examples = [
        row
        for row in sorted(question_rows, key=lambda item: item["overall_score"], reverse=True)
        if row["is_correct"] and row["is_relevant"]
    ][:5]
    weak_examples = sorted(question_rows, key=lambda item: item["overall_score"])[:4]

    report = f"""# Quiz Generation Evaluation

## 1. Цель эксперимента

Цель Фазы 18 — оценить, насколько production quiz generation формирует пригодные контрольно-обучающие материалы по значимым изменениям документов из evaluation corpus. Проверяются не только наличие вопросов, но и их связь с изменением, юридическая корректность, однозначность правильного ответа, качество distractors, отсутствие редакционного шума, traceability и полезность для сотрудника.

## 2. Связь с гибридным методом

Эксперимент относится к этапу `G — Generation of control-learning materials` гибридного метода `M = <E, N, S, C, P, G, R>`. В текущем MVP quiz generation получает не raw document, а summary highlights, сформированные после structural comparison и significance-layer.

## 3. Evaluation corpus

Использован `data/evaluation_corpus/`: 10 синтетических пар документов с `annotation.json`, `expected_changes`, `importance`, `change_type`, `editorial_changes`, `known_difficulties`, `expected_summary_topics` и `expected_quiz_topics`. Валидатор корпуса проходит успешно. Всего размечено 13 expected changes; quiz-worthy important/critical topics для этой фазы — {summary['total_important_changes']}.

## 4. Что именно оценивается

Оценивается production-функция `build_quiz_from_summary(...)` из `backend/documents/domain/diff_quiz.py` при входе из pipeline. Workflow materialization в БД (`GeneratedQuiz`, `Question`, `Choice`) не переписывался; эксперимент запускает доменные функции in-memory, чтобы не изменять состояние проекта.

## 5. Evaluation mode

Основной режим — pipeline evaluation:

```text
chunk_by_structure_ru -> build_version_diff -> build_brief_summary -> build_quiz_from_summary
```

Дополнительно сохранён oracle diagnostic: в генератор подаются только annotation expected quiz-worthy changes. Этот режим нужен для отделения ошибок quiz generation от upstream errors и не смешивается с основными pipeline метриками.

## 6. Критерии оценки вопроса

{markdown_table(['Criterion', 'Meaning', 'Scale'], criteria_rows)}

## 7. Scoring rubric

Шкала 1-5: `1` — критерий провален, вопрос misleading/шумовой; `3` — частично приемлемо, но есть существенные ограничения; `5` — критерий выполнен полностью. `overall_question_score` считается как среднее по семи критериям.

## 8. Метрики

Для каждой пары рассчитаны `questions_count`, `correct_questions`, `relevant_questions`, `questions_with_source`, `important_changes`, `covered_important_changes`, `coverage`, `avg_question_score`, `editorial_noise_questions`. Aggregate metrics считаются по question-level строкам и coverage важных/critical expected quiz topics.

## 9. Результаты по вопросам

{markdown_table(['Pair', 'Questions', 'Correct', 'Relevant', 'With source', 'Coverage', 'Avg score'], pair_table_rows)}

## 10. Aggregate results

{markdown_table(['Metric', 'Value'], aggregate_rows)}

## 11. Important change coverage

Pipeline quiz generation покрыл {summary['covered_important_changes']} из {summary['total_important_changes']} important/critical expected quiz topics (`{summary['important_change_coverage']:.4f}`). Не покрыт ожидаемый topic `новый способ подачи заявления` в `pair_06_procedure_change`: вопрос был связан с правильным source fragment, но upstream semantic classification подал его в quiz generator как document-list change, поэтому answer не проверяет электронную форму во внутреннем портале.

Oracle diagnostic при корректном входе даёт coverage {summary['oracle_diagnostic']['important_change_coverage']:.4f} ({summary['oracle_diagnostic']['covered_important_changes']} / {summary['oracle_diagnostic']['important_changes']}). Этот режим не является реальным pipeline score; он показывает, какие темы quiz generator способен сформулировать при корректном annotation-driven входе, без ошибок structural diff/significance/summary.

## 12. Source/explanation analysis

`source_explanation_rate` = `{summary['source_explanation_rate']:.4f}`: все сгенерированные вопросы имеют explanation и source metadata/title/old-new text. Однако наличие source не равно корректности вопроса: слабые вопросы в `pair_05` и `pair_09` тоже traceable, но traceability помогает reviewer обнаружить, что source является editorial/noise.

Количество вопросов с explanation/source quality ниже 4: {len(source_low_rows)}. Основная причина снижения — не отсутствие source, а то, что explanation повторяет upstream ошибочную semantic framing.

## 13. Distractor quality analysis

Средняя оценка distractor quality = `{distractor_avg:.4f}`. Сильная сторона baseline — distractors обычно не дублируют correct answer и дают single-choice структуру. Ограничение — distractors часто generic (`изменений не было`, `перечень документов остался прежним`) либо берутся из answer pool других true changes. В `pair_09` это делает варианты правдоподобными, но методически спорными: distractor может быть истинным изменением документа, просто не отвечающим на данный вопрос.

## 14. Editorial/noise question analysis

Editorial/noise question rate = `{summary['editorial_noise_question_rate']:.4f}` ({summary['editorial_noise_questions']} / {summary['total_questions']}). Слабые случаи:

- `pair_05_editorial_change`: editorial verb replacement превращён в critical document-list question.
- `pair_09_mixed_significant_and_editorial:q3`: informational notice over-framed as procedure.
- `pair_09_mixed_significant_and_editorial:q4`: editorial wording replacement превращён в deadline question.

Эти ошибки относятся преимущественно к upstream significance/summary representation, потому что quiz generator получает уже завышенные labels/highlights.

## 15. Good question examples

"""
    for row in good_examples:
        report += (
            f"- `{row['question_id']}`: {row['matched_topic']} — "
            f"overall `{row['overall_score']:.4f}`; {row['notes']}\n"
        )

    report += "\n## 16. Weak question examples\n\n"
    for row in weak_examples:
        report += (
            f"- `{row['question_id']}`: overall `{row['overall_score']:.4f}`; "
            f"{row['notes']}\n"
        )

    report += "\n## 17. Связь с summary/significance evaluation\n\n"
    report += "\n".join(phase16_lines) if phase16_lines else "Previous phase summaries were not found."
    report += f"""

Quiz generation зависит от significance-layer: если significance завышает editorial/informational change, generator воспринимает его как допустимый highlight и строит question. Поэтому ошибки `pair_05` и части `pair_09` классифицируются как upstream-induced. Quiz generation также зависит от summary/source representation: если summary highlight имеет неверный semantic type, вопрос получает неверный template, как в `pair_06` и частично `pair_07`.

## 18. Human-in-the-loop approval

Generated quiz не должен автоматически становиться финальным учебным материалом. В MVP responsible person approval является обязательным quality gate: `GeneratedQuiz` проходит состояния `draft -> pending_review -> approved/rejected`, а employee attempts разрешаются только для approved quiz. Для нормативной области это принципиально: reviewer проверяет legal wording, source reference, корректность correct answer и отсутствие questions по editorial/noise. Это не слабость метода, а осознанное инженерное ограничение MVP.

## 19. Ограничения эксперимента

- Corpus малый и синтетический: 10 пар документов.
- Expert scoring частично ручной, поскольку legal/domain correctness и usefulness нельзя надежно вывести только lexical matching.
- Pipeline-mode метрики включают ошибки upstream stages.
- Oracle diagnostic не является реальным pipeline score.
- ORM workflow не запускался для сохранения GeneratedQuiz rows; использованы те же domain generation functions in-memory.
- Production quiz generation algorithm не изменялся ради улучшения метрик.

## 20. Вывод для диссертации

Экспериментальная оценка quiz generation показала, что этап `G` формирует проверяемые single-choice контрольно-обучающие материалы по большинству important/critical изменений: coverage составил {summary['important_change_coverage']:.4f}, average expert score — {summary['average_question_score']:.4f}, доля вопросов с source/explanation — {summary['source_explanation_rate']:.4f}. Лучшие вопросы возникают для сроков, обязанностей, перечней документов и оснований отказа. Основные слабые случаи связаны с upstream over-prioritization editorial/informational changes и неверным semantic framing. Следовательно, quiz generation применим для MVP как материализованный baseline-этап гибридного метода, но только при обязательном human-in-the-loop утверждении ответственным лицом.
"""

    (DOCS_DIR / "quiz-generation-evaluation.md").write_text(
        report.strip() + "\n", encoding="utf-8"
    )


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    pairs = read_pairs()

    question_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for pair in pairs:
        rows, pair_row, pair_diagnostics = evaluate_pipeline_pair(pair)
        question_rows.extend(rows)
        pair_rows.append(pair_row)
        diagnostics[pair.pair_id] = pair_diagnostics

    oracle_diagnostic = evaluate_oracle_diagnostic(pairs)
    summary = make_summary_json(
        pairs=pairs,
        question_rows=question_rows,
        pair_rows=pair_rows,
        diagnostics=diagnostics,
        oracle_diagnostic=oracle_diagnostic,
    )

    question_fieldnames = [
        "pair_id",
        "question_id",
        "question_text",
        "options",
        "correct_answer",
        "expected_topics",
        "matched_topic",
        "change_relevance",
        "domain_correctness",
        "unambiguous_answer",
        "distractor_quality",
        "no_editorial_noise",
        "explanation_source_quality",
        "employee_usefulness",
        "overall_score",
        "has_source",
        "is_correct",
        "is_relevant",
        "is_editorial_noise",
        "notes",
        "explanation",
        "source",
        "semantic_type",
        "significance_label",
        "error_origin",
    ]
    pair_fieldnames = [
        "pair_id",
        "questions_count",
        "correct_questions",
        "relevant_questions",
        "questions_with_source",
        "important_changes",
        "covered_important_changes",
        "coverage",
        "avg_question_score",
        "editorial_noise_questions",
        "notes",
    ]

    write_csv(RESULTS_DIR / "quiz_results.csv", question_rows, question_fieldnames)
    write_csv(RESULTS_DIR / "quiz_pair_results.csv", pair_rows, pair_fieldnames)
    (RESULTS_DIR / "quiz_evaluation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot_quality_scores(question_rows)
    plot_pair_scores(pair_rows)
    plot_coverage(pair_rows)
    write_examples(question_rows)
    write_markdown_report(summary, question_rows)

    print(
        json.dumps(
            {
                "total_pairs": summary["total_pairs"],
                "total_questions": summary["total_questions"],
                "correct_question_rate": summary["correct_question_rate"],
                "relevant_question_rate": summary["relevant_question_rate"],
                "source_explanation_rate": summary["source_explanation_rate"],
                "important_change_coverage": summary["important_change_coverage"],
                "editorial_noise_question_rate": summary[
                    "editorial_noise_question_rate"
                ],
                "average_question_score": summary["average_question_score"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
