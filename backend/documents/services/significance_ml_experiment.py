from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from documents.services.importance import LABELS as SIGNIFICANCE_LABELS

try:
    from scipy.sparse import hstack
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        precision_recall_fscore_support,
    )

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback
    DictVectorizer = None
    LogisticRegression = None
    TfidfVectorizer = None
    accuracy_score = None
    confusion_matrix = None
    hstack = None
    precision_recall_fscore_support = None
    SKLEARN_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "experiments" / "significance_ml"
DEFAULT_DATASET_CSV = PROJECT_ROOT / "experiments" / "significance" / "significance_results.csv"
DEFAULT_SUPERVISED_CORPUS_DIR = PROJECT_ROOT / "experiments" / "ml_corpus"

LABELS = tuple(SIGNIFICANCE_LABELS)
HIGH_PRIORITY_LABELS = {"critical", "important"}

NUMBER_RE = re.compile(r"\d")
DATE_LIKE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")
LEGAL_REFERENCE_RE = re.compile(
    r"\b(статья|ст\.|пункт|п\.|раздел|глава|приказ|постановление|регламент)\b",
    re.IGNORECASE,
)
DEADLINE_RE = re.compile(r"\b(срок|дней|дня|рабочих|рабочие)\b", re.IGNORECASE)
OBLIGATION_RE = re.compile(r"\b(обязан|обязаны|обязана|должен|должна|должны)\b", re.IGNORECASE)
REFUSAL_RE = re.compile(r"\b(отказ|отказать|основание)\b", re.IGNORECASE)
DOCUMENT_RE = re.compile(r"\b(документ|документов|справк|копи|доверенност)\b", re.IGNORECASE)
RESPONSIBILITY_RE = re.compile(
    r"\b(ответственност|дисциплинар|санкц|нарушени)\b",
    re.IGNORECASE,
)
PROCEDURE_RE = re.compile(
    r"\b(процедур|порядок|подач|портал|электронн|уведомлен)\b",
    re.IGNORECASE,
)
EDITORIAL_RE = re.compile(
    r"\b(редакцион|формулировк|уточнен|переимен|структур)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SignificanceExample:
    example_id: str
    pair_id: str
    change_id: str
    true_label: str
    rule_based_label: str
    operation: str
    change_type: str
    semantic_type: str
    predicted_semantic_type: str
    old_text: str
    new_text: str
    description: str
    notes: str
    requires_manual_review: bool
    source: str


@dataclass
class ModelBundle:
    text_vectorizer: Any
    meta_vectorizer: Any
    model: Any
    feature_names: list[str]


def rel_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


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


def _normalize_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in LABELS else ""


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _safe_divide(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)


def _truncate(value: str, limit: int = 200) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def map_high_priority(label: str) -> int:
    return int(str(label or "").strip().lower() in HIGH_PRIORITY_LABELS)


def collect_significance_dataset(
    results_csv_path: Path = DEFAULT_DATASET_CSV,
) -> tuple[list[SignificanceExample], dict[str, Any]]:
    warnings: list[str] = []
    if not results_csv_path.exists():
        warnings.append("Primary labeled significance dataset is not available.")
        return [], {
            "dataset_source": rel_repo_path(results_csv_path),
            "warnings": warnings,
            "label_distribution": {},
        }

    examples: list[SignificanceExample] = []
    with results_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            true_label = _normalize_label(row.get("expected_importance", ""))
            rule_based_label = _normalize_label(row.get("predicted_importance", ""))
            if not true_label or not rule_based_label:
                continue
            pair_id = str(row.get("pair_id") or f"pair_{index:04d}")
            change_id = str(row.get("change_id") or f"chg_{index:04d}")
            examples.append(
                SignificanceExample(
                    example_id=f"{pair_id}:{change_id}",
                    pair_id=pair_id,
                    change_id=change_id,
                    true_label=true_label,
                    rule_based_label=rule_based_label,
                    operation=str(row.get("operation") or ""),
                    change_type=str(row.get("change_type") or ""),
                    semantic_type=str(row.get("semantic_type") or ""),
                    predicted_semantic_type=str(row.get("predicted_semantic_type") or ""),
                    old_text=str(row.get("old_text") or ""),
                    new_text=str(row.get("new_text") or ""),
                    description=str(row.get("description") or ""),
                    notes=str(row.get("notes") or ""),
                    requires_manual_review=_parse_bool(row.get("requires_manual_review")),
                    source=rel_repo_path(results_csv_path),
                )
            )

    label_distribution = dict(sorted(Counter(item.true_label for item in examples).items()))
    metadata = {
        "dataset_source": rel_repo_path(results_csv_path),
        "warnings": warnings,
        "label_distribution": label_distribution,
    }
    if len(examples) < 8:
        warnings.append(
            "The labeled significance corpus is very small; ML estimates should be treated as indicative only."
        )
    if any(count < 2 for count in label_distribution.values()):
        warnings.append(
            "Some significance labels have fewer than two examples; leave-one-out evaluation is used and class coverage is fragile."
        )
    return examples, metadata


def collect_significance_dataset_from_supervised_corpus(
    *,
    train_csv_path: Path,
    test_csv_path: Path,
) -> tuple[list[SignificanceExample], list[SignificanceExample], dict[str, Any]]:
    warnings: list[str] = []
    if not train_csv_path.exists() or not test_csv_path.exists():
        warnings.append("Supervised ML corpus train/test files are not available.")
        return [], [], {
            "dataset_source": f"{rel_repo_path(train_csv_path)} + {rel_repo_path(test_csv_path)}",
            "warnings": warnings,
            "label_distribution": {},
            "mode": "missing",
        }

    def _load(path: Path, split_name: str) -> list[SignificanceExample]:
        rows: list[SignificanceExample] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=1):
                true_label = _normalize_label(row.get("y_significance") or row.get("significance_label") or "")
                rule_based_label = _normalize_label(row.get("rule_based_label") or row.get("significance_label") or "")
                if not true_label or not rule_based_label:
                    continue
                pair_id = str(row.get("pair_id") or f"{split_name}_pair_{index:04d}")
                change_id = str(row.get("change_id") or f"{split_name}_chg_{index:04d}")
                rows.append(
                    SignificanceExample(
                        example_id=str(row.get("example_id") or f"{pair_id}:{change_id}"),
                        pair_id=pair_id,
                        change_id=change_id,
                        true_label=true_label,
                        rule_based_label=rule_based_label,
                        operation=str(row.get("operation_type") or row.get("operation") or ""),
                        change_type=str(row.get("semantic_type") or ""),
                        semantic_type=str(row.get("semantic_type") or ""),
                        predicted_semantic_type=str(row.get("semantic_type") or ""),
                        old_text=str(row.get("old_text") or ""),
                        new_text=str(row.get("new_text") or ""),
                        description=str(row.get("notes") or ""),
                        notes=str(row.get("notes") or ""),
                        requires_manual_review=_parse_bool(
                            row.get("rule_based_requires_manual_review")
                        ),
                        source=rel_repo_path(path),
                    )
                )
        return rows

    train_examples = _load(train_csv_path, "train")
    test_examples = _load(test_csv_path, "test")
    label_distribution = dict(
        sorted(Counter(item.true_label for item in (train_examples + test_examples)).items())
    )
    metadata = {
        "dataset_source": f"{rel_repo_path(train_csv_path)} + {rel_repo_path(test_csv_path)}",
        "warnings": warnings,
        "label_distribution": label_distribution,
        "mode": "supervised_split",
        "train_size": len(train_examples),
        "test_size": len(test_examples),
    }
    return train_examples, test_examples, metadata


def _build_text_payload(example: SignificanceExample) -> str:
    return "\n".join(
        part
        for part in [
            example.old_text,
            example.new_text,
            example.description,
            example.notes,
            example.change_type,
            example.predicted_semantic_type,
        ]
        if part
    )


def extract_ml_features(example: SignificanceExample) -> dict[str, float]:
    old_text = _normalize_text(example.old_text)
    new_text = _normalize_text(example.new_text)
    combined = _normalize_text(" ".join([old_text, new_text, example.description, example.notes]))
    old_len = len(old_text)
    new_len = len(new_text)
    length_delta = abs(new_len - old_len)
    max_len = max(old_len, new_len, 1)

    return {
        "op_added": float(example.operation == "added"),
        "op_removed": float(example.operation == "removed"),
        "op_modified": float(example.operation == "modified"),
        "op_moved": float(example.operation == "moved"),
        "change_type_deadline": float(example.change_type == "deadline_change"),
        "change_type_obligation": float(example.change_type == "added_obligation"),
        "change_type_refusal": float(example.change_type == "refusal_ground_change"),
        "semantic_deadline": float(example.predicted_semantic_type == "deadline"),
        "semantic_document": float(example.predicted_semantic_type == "document"),
        "semantic_obligation": float(example.predicted_semantic_type == "obligation"),
        "semantic_procedure": float(example.predicted_semantic_type == "procedure"),
        "semantic_refusal": float(example.predicted_semantic_type == "refusal"),
        "semantic_editorial": float(example.predicted_semantic_type == "editorial"),
        "semantic_responsibility": float(example.predicted_semantic_type == "responsibility"),
        "old_length": float(old_len),
        "new_length": float(new_len),
        "absolute_length_delta": float(length_delta),
        "relative_length_delta": round(length_delta / max_len, 4),
        "has_number": float(bool(NUMBER_RE.search(combined))),
        "has_date_like_pattern": float(bool(DATE_LIKE_RE.search(combined))),
        "has_legal_reference": float(bool(LEGAL_REFERENCE_RE.search(combined))),
        "has_modal_obligation_words": float(bool(OBLIGATION_RE.search(combined))),
        "has_refusal_words": float(bool(REFUSAL_RE.search(combined))),
        "has_deadline_words": float(bool(DEADLINE_RE.search(combined))),
        "has_document_words": float(bool(DOCUMENT_RE.search(combined))),
        "has_responsibility_words": float(bool(RESPONSIBILITY_RE.search(combined))),
        "has_procedure_words": float(bool(PROCEDURE_RE.search(combined))),
        "has_editorial_words": float(bool(EDITORIAL_RE.search(combined))),
        "requires_manual_review_flag": float(example.requires_manual_review),
    }


def _build_training_matrix(
    examples: list[SignificanceExample],
) -> tuple[Any, Any, Any, list[str]]:
    texts = [_build_text_payload(item) for item in examples]
    text_vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        max_features=2000,
    )
    meta_vectorizer = DictVectorizer(sparse=True)
    text_matrix = text_vectorizer.fit_transform(texts)
    meta_matrix = meta_vectorizer.fit_transform(
        [extract_ml_features(item) for item in examples]
    )
    matrix = hstack([text_matrix, meta_matrix]).tocsr()
    feature_names = [
        *[f"tfidf:{name}" for name in text_vectorizer.get_feature_names_out()],
        *[f"meta:{name}" for name in meta_vectorizer.get_feature_names_out()],
    ]
    return text_vectorizer, meta_vectorizer, matrix, feature_names


def train_ml_classifier(
    examples: list[SignificanceExample],
    labels: list[str],
) -> ModelBundle:
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn is not available in the current environment.")
    text_vectorizer, meta_vectorizer, matrix, feature_names = _build_training_matrix(examples)
    model = LogisticRegression(
        max_iter=2500,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(matrix, labels)
    return ModelBundle(
        text_vectorizer=text_vectorizer,
        meta_vectorizer=meta_vectorizer,
        model=model,
        feature_names=feature_names,
    )


def _transform_examples(bundle: ModelBundle, examples: list[SignificanceExample]) -> Any:
    text_matrix = bundle.text_vectorizer.transform([_build_text_payload(item) for item in examples])
    meta_matrix = bundle.meta_vectorizer.transform(
        [extract_ml_features(item) for item in examples]
    )
    return hstack([text_matrix, meta_matrix]).tocsr()


def _majority_label(labels: list[str]) -> str:
    if not labels:
        return "important"
    return Counter(labels).most_common(1)[0][0]


def _label_probability_map(classes: list[str], probabilities: list[float]) -> dict[str, float]:
    mapping = {label: 0.0 for label in LABELS}
    for label, probability in zip(classes, probabilities):
        mapping[str(label)] = round(float(probability), 6)
    return mapping


def _compute_multiclass_metrics(
    true_labels: list[str],
    predicted_labels: list[str],
) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        true_labels,
        predicted_labels,
        labels=list(LABELS),
        zero_division=0,
    )
    matrix = confusion_matrix(true_labels, predicted_labels, labels=list(LABELS))
    return {
        "accuracy": round(float(accuracy_score(true_labels, predicted_labels)), 4),
        "macro_precision": round(float(sum(precision) / len(LABELS)), 4),
        "macro_recall": round(float(sum(recall) / len(LABELS)), 4),
        "macro_f1": round(float(sum(f1) / len(LABELS)), 4),
        "per_label": {
            label: {
                "precision": round(float(label_precision), 4),
                "recall": round(float(label_recall), 4),
                "f1": round(float(label_f1), 4),
                "support": int(label_support),
            }
            for label, label_precision, label_recall, label_f1, label_support in zip(
                LABELS, precision, recall, f1, support
            )
        },
        "confusion_matrix_labels": list(LABELS),
        "confusion_matrix": matrix.tolist(),
    }


def _compute_binary_metrics(
    true_labels: list[str],
    predicted_labels: list[str],
) -> dict[str, Any]:
    true_binary = [map_high_priority(item) for item in true_labels]
    pred_binary = [map_high_priority(item) for item in predicted_labels]
    tp = sum(1 for truth, pred in zip(true_binary, pred_binary) if truth == 1 and pred == 1)
    fp = sum(1 for truth, pred in zip(true_binary, pred_binary) if truth == 0 and pred == 1)
    fn = sum(1 for truth, pred in zip(true_binary, pred_binary) if truth == 1 and pred == 0)
    tn = sum(1 for truth, pred in zip(true_binary, pred_binary) if truth == 0 and pred == 0)
    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    f1 = _safe_divide(2 * precision * recall, precision + recall) if precision and recall else 0.0
    editorial_high_priority_false_positive_count = sum(
        1 for truth, pred in zip(true_labels, predicted_labels) if truth == "editorial" and pred in HIGH_PRIORITY_LABELS
    )
    important_critical_miss_count = sum(
        1 for truth, pred in zip(true_labels, predicted_labels) if truth in HIGH_PRIORITY_LABELS and pred not in HIGH_PRIORITY_LABELS
    )
    return {
        "high_priority_precision": precision,
        "high_priority_recall": recall,
        "high_priority_f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "editorial_high_priority_false_positive_count": editorial_high_priority_false_positive_count,
        "important_critical_miss_count": important_critical_miss_count,
    }


def evaluate_rule_based(examples: list[SignificanceExample]) -> dict[str, Any]:
    true_labels = [item.true_label for item in examples]
    predicted_labels = [item.rule_based_label for item in examples]
    metrics = _compute_multiclass_metrics(true_labels, predicted_labels)
    metrics["binary"] = _compute_binary_metrics(true_labels, predicted_labels)
    return metrics


def evaluate_ml_classifier(
    examples: list[SignificanceExample],
    *,
    train_examples: list[SignificanceExample] | None = None,
    test_examples: list[SignificanceExample] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not SKLEARN_AVAILABLE:
        warnings.append("scikit-learn is not available; ML classifier was not evaluated.")
        return [], {"status": "missing"}, [], warnings

    if train_examples is not None and test_examples is not None:
        if not train_examples or not test_examples:
            warnings.append("Insufficient supervised train/test examples for ML training.")
            return [], {"status": "partial"}, [], warnings
        if len({item.true_label for item in train_examples}) < 2:
            warnings.append("Training split does not contain at least two significance classes.")
            return [], {"status": "partial"}, [], warnings

        bundle = train_ml_classifier(train_examples, [item.true_label for item in train_examples])
        matrix = _transform_examples(bundle, test_examples)
        predictions = bundle.model.predict(matrix).tolist()
        if hasattr(bundle.model, "predict_proba"):
            probability_rows = bundle.model.predict_proba(matrix).tolist()
            probability_maps = [
                _label_probability_map(list(bundle.model.classes_), probabilities)
                for probabilities in probability_rows
            ]
            confidences = [round(max(probability_map.values()), 6) for probability_map in probability_maps]
        else:
            probability_maps = [{label: float(label == predicted) for label in LABELS} for predicted in predictions]
            confidences = [1.0 for _ in predictions]

        prediction_rows = []
        for example, predicted_label, confidence, probability_map in zip(
            test_examples,
            predictions,
            confidences,
            probability_maps,
        ):
            prediction_rows.append(
                {
                    "example_id": example.example_id,
                    "pair_id": example.pair_id,
                    "change_id": example.change_id,
                    "ml_label": str(predicted_label),
                    "ml_confidence": confidence,
                    "ml_probability_map": probability_map,
                }
            )

        true_labels = [item.true_label for item in test_examples]
        predicted_labels = [row["ml_label"] for row in prediction_rows]
        metrics = _compute_multiclass_metrics(true_labels, predicted_labels)
        metrics["binary"] = _compute_binary_metrics(true_labels, predicted_labels)
        metrics["status"] = "available"
        metrics["evaluation_plan"] = "fixed_train_test_split"
        metrics["train_size"] = len(train_examples)
        metrics["test_size"] = len(test_examples)

        feature_report_rows: list[dict[str, Any]] = []
        try:
            for class_index, class_label in enumerate(bundle.model.classes_):
                coefficients = bundle.model.coef_[class_index]
                top_indexes = coefficients.argsort()[-10:][::-1]
                for rank, feature_index in enumerate(top_indexes, start=1):
                    feature_name = bundle.feature_names[int(feature_index)]
                    feature_report_rows.append(
                        {
                            "model": "ml_text_model",
                            "class_label": class_label,
                            "rank": rank,
                            "feature_name": feature_name,
                            "feature_type": feature_name.split(":", 1)[0],
                            "coefficient": round(float(coefficients[int(feature_index)]), 6),
                        }
                    )
        except Exception as exc:  # pragma: no cover
            warnings.append(f"Feature report is partial: {exc}")
        return prediction_rows, metrics, feature_report_rows, warnings

    if len(examples) < 2 or len({item.true_label for item in examples}) < 2:
        warnings.append("Insufficient labeled examples for ML training.")
        return [], {"status": "partial"}, [], warnings

    labels = [item.true_label for item in examples]
    label_distribution = Counter(labels)
    evaluation_plan = "leave_one_out" if any(count < 2 for count in label_distribution.values()) else "stratified_cv_fallback_leave_one_out"
    if evaluation_plan == "leave_one_out":
        warnings.append(
            "Leave-one-out evaluation was used because at least one significance label has fewer than two examples."
        )

    prediction_rows: list[dict[str, Any]] = []
    for test_index, example in enumerate(examples):
        train_examples = [item for idx, item in enumerate(examples) if idx != test_index]
        train_labels = [item.true_label for idx, item in enumerate(examples) if idx != test_index]
        if len(set(train_labels)) < 2:
            predicted_label = _majority_label(train_labels)
            confidence = 1.0
            probability_map = {label: float(label == predicted_label) for label in LABELS}
        else:
            bundle = train_ml_classifier(train_examples, train_labels)
            matrix = _transform_examples(bundle, [example])
            predicted_label = str(bundle.model.predict(matrix)[0])
            probabilities = bundle.model.predict_proba(matrix)[0].tolist()
            probability_map = _label_probability_map(
                list(bundle.model.classes_),
                probabilities,
            )
            confidence = round(max(probability_map.values()), 6)

        prediction_rows.append(
            {
                "example_id": example.example_id,
                "pair_id": example.pair_id,
                "change_id": example.change_id,
                "ml_label": predicted_label,
                "ml_confidence": confidence,
                "ml_probability_map": probability_map,
            }
        )

    true_labels = [item.true_label for item in examples]
    predicted_labels = [row["ml_label"] for row in prediction_rows]
    metrics = _compute_multiclass_metrics(true_labels, predicted_labels)
    metrics["binary"] = _compute_binary_metrics(true_labels, predicted_labels)
    metrics["status"] = "available"
    metrics["evaluation_plan"] = evaluation_plan

    feature_report_rows: list[dict[str, Any]] = []
    try:
        full_bundle = train_ml_classifier(examples, labels)
        for class_index, class_label in enumerate(full_bundle.model.classes_):
            coefficients = full_bundle.model.coef_[class_index]
            top_indexes = coefficients.argsort()[-10:][::-1]
            for rank, feature_index in enumerate(top_indexes, start=1):
                feature_name = full_bundle.feature_names[int(feature_index)]
                feature_report_rows.append(
                    {
                        "model": "ml_text_model",
                        "class_label": class_label,
                        "rank": rank,
                        "feature_name": feature_name,
                        "feature_type": feature_name.split(":", 1)[0],
                        "coefficient": round(float(coefficients[int(feature_index)]), 6),
                    }
                )
    except Exception as exc:  # pragma: no cover - best effort report
        warnings.append(f"Feature report is partial: {exc}")

    return prediction_rows, metrics, feature_report_rows, warnings


def _predict_hybrid_label(
    *,
    rule_label: str,
    ml_label: str,
    ml_confidence: float,
    probability_map: dict[str, float],
) -> tuple[str, str]:
    rule_is_high = rule_label in HIGH_PRIORITY_LABELS
    ml_is_high = ml_label in HIGH_PRIORITY_LABELS
    ml_high_confidence = probability_map.get("critical", 0.0) + probability_map.get("important", 0.0)

    if rule_label == "critical":
        return "critical", "rule_critical_lock"
    if rule_is_high and ml_is_high:
        return rule_label, "high_priority_confirmed"
    if not rule_is_high and ml_is_high and ml_confidence >= 0.75 and ml_high_confidence >= 0.75:
        return "important", "conservative_ml_promotion"
    if rule_is_high and not ml_is_high:
        return rule_label, "rule_priority_preserved"
    if not rule_is_high and not ml_is_high and ml_confidence >= 0.6:
        return ml_label, "low_priority_ml_selection"
    return rule_label, "fallback_rule_based"


def evaluate_hybrid_strategy(
    examples: list[SignificanceExample],
    ml_prediction_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hybrid_rows: list[dict[str, Any]] = []
    for example, ml_row in zip(examples, ml_prediction_rows):
        hybrid_label, hybrid_reason = _predict_hybrid_label(
            rule_label=example.rule_based_label,
            ml_label=str(ml_row.get("ml_label") or ""),
            ml_confidence=float(ml_row.get("ml_confidence") or 0.0),
            probability_map=dict(ml_row.get("ml_probability_map") or {}),
        )
        hybrid_rows.append(
            {
                "example_id": example.example_id,
                "pair_id": example.pair_id,
                "change_id": example.change_id,
                "hybrid_label": hybrid_label,
                "hybrid_reason": hybrid_reason,
            }
        )

    true_labels = [item.true_label for item in examples]
    predicted_labels = [row["hybrid_label"] for row in hybrid_rows]
    metrics = _compute_multiclass_metrics(true_labels, predicted_labels)
    metrics["binary"] = _compute_binary_metrics(true_labels, predicted_labels)
    metrics["status"] = "available"
    return hybrid_rows, metrics


def _build_confusion_matrix_rows(
    metrics_by_model: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_name, metrics in metrics_by_model.items():
        labels = metrics.get("confusion_matrix_labels") or []
        matrix = metrics.get("confusion_matrix") or []
        for true_index, true_label in enumerate(labels):
            for predicted_index, predicted_label in enumerate(labels):
                rows.append(
                    {
                        "model": model_name,
                        "true_label": true_label,
                        "predicted_label": predicted_label,
                        "count": matrix[true_index][predicted_index],
                    }
                )
    return rows


def _build_prediction_rows(
    examples: list[SignificanceExample],
    ml_prediction_rows: list[dict[str, Any]],
    hybrid_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    disagreement_count = 0
    ml_index = {row["example_id"]: row for row in ml_prediction_rows}
    hybrid_index = {row["example_id"]: row for row in hybrid_rows}

    for example in examples:
        ml_row = ml_index.get(example.example_id, {})
        hybrid_row = hybrid_index.get(example.example_id, {})
        ml_label = str(ml_row.get("ml_label") or "")
        hybrid_label = str(hybrid_row.get("hybrid_label") or example.rule_based_label)
        if ml_label and ml_label != example.rule_based_label:
            disagreement_count += 1
        rows.append(
            {
                "example_id": example.example_id,
                "pair_id": example.pair_id,
                "change_id": example.change_id,
                "true_label": example.true_label,
                "rule_based_label": example.rule_based_label,
                "ml_label": ml_label,
                "hybrid_label": hybrid_label,
                "ml_confidence": ml_row.get("ml_confidence", ""),
                "rule_based_correct": int(example.rule_based_label == example.true_label),
                "ml_correct": int(ml_label == example.true_label) if ml_label else "",
                "hybrid_correct": int(hybrid_label == example.true_label),
                "text_preview": _truncate(f"{example.old_text} || {example.new_text} || {example.description}"),
                "source": example.source,
            }
        )
    return rows, disagreement_count


def _build_error_rows(
    examples: list[SignificanceExample],
    prediction_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example, prediction_row in zip(examples, prediction_rows):
        reasons: list[str] = []
        if not prediction_row["rule_based_correct"]:
            reasons.append("rule_based_error")
        if prediction_row.get("ml_correct", "") == 0:
            reasons.append("ml_error")
        if not prediction_row["hybrid_correct"]:
            reasons.append("hybrid_error")
        if prediction_row.get("ml_label") and prediction_row["ml_label"] != prediction_row["rule_based_label"]:
            reasons.append("rule_ml_disagreement")
        if not reasons:
            continue
        rows.append(
            {
                "example_id": example.example_id,
                "true_label": example.true_label,
                "rule_based_label": prediction_row["rule_based_label"],
                "ml_label": prediction_row.get("ml_label", ""),
                "hybrid_label": prediction_row["hybrid_label"],
                "error_type": "|".join(reasons),
                "text_preview": prediction_row["text_preview"],
                "explanation": _truncate(example.description or example.notes or example.new_text or example.old_text),
            }
        )
    return rows


def write_significance_ml_outputs(
    *,
    output_dir: Path,
    summary_payload: dict[str, Any],
    prediction_rows: list[dict[str, Any]],
    confusion_rows: list[dict[str, Any]],
    feature_report_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
) -> dict[str, str]:
    summary_path = output_dir / "significance_ml_summary.json"
    predictions_path = output_dir / "significance_ml_predictions.csv"
    confusion_path = output_dir / "significance_ml_confusion_matrix.csv"
    feature_report_path = output_dir / "significance_ml_feature_report.csv"
    error_examples_path = output_dir / "significance_ml_error_examples.csv"

    _write_json(summary_path, summary_payload)
    _write_csv(
        predictions_path,
        prediction_rows,
        headers=[
            "example_id",
            "pair_id",
            "change_id",
            "true_label",
            "rule_based_label",
            "ml_label",
            "hybrid_label",
            "ml_confidence",
            "rule_based_correct",
            "ml_correct",
            "hybrid_correct",
            "text_preview",
            "source",
        ],
    )
    _write_csv(
        confusion_path,
        confusion_rows,
        headers=["model", "true_label", "predicted_label", "count"],
    )
    _write_csv(
        feature_report_path,
        feature_report_rows,
        headers=[
            "model",
            "class_label",
            "rank",
            "feature_name",
            "feature_type",
            "coefficient",
        ],
    )
    _write_csv(
        error_examples_path,
        error_rows,
        headers=[
            "example_id",
            "true_label",
            "rule_based_label",
            "ml_label",
            "hybrid_label",
            "error_type",
            "text_preview",
            "explanation",
        ],
    )
    return {
        "summary": rel_repo_path(summary_path),
        "predictions": rel_repo_path(predictions_path),
        "confusion_matrix": rel_repo_path(confusion_path),
        "feature_report": rel_repo_path(feature_report_path),
        "error_examples": rel_repo_path(error_examples_path),
    }


def run_significance_ml_experiment(
    *,
    dataset_csv_path: Path = DEFAULT_DATASET_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    supervised_corpus_dir: Path = DEFAULT_SUPERVISED_CORPUS_DIR,
) -> dict[str, Any]:
    train_csv_path = supervised_corpus_dir / "train.csv"
    test_csv_path = supervised_corpus_dir / "test.csv"

    train_examples: list[SignificanceExample] | None = None
    test_examples: list[SignificanceExample] | None = None
    if train_csv_path.exists() and test_csv_path.exists():
        train_examples, test_examples, metadata = collect_significance_dataset_from_supervised_corpus(
            train_csv_path=train_csv_path,
            test_csv_path=test_csv_path,
        )
        examples = [*train_examples, *test_examples]
    else:
        examples, metadata = collect_significance_dataset(dataset_csv_path)

    warnings = list(metadata.get("warnings") or [])
    label_distribution = dict(metadata.get("label_distribution") or {})

    evaluation_examples = test_examples if test_examples is not None else examples
    rule_metrics = evaluate_rule_based(evaluation_examples) if evaluation_examples else {"status": "missing"}
    ml_prediction_rows, ml_metrics, feature_report_rows, ml_warnings = evaluate_ml_classifier(
        examples,
        train_examples=train_examples,
        test_examples=test_examples,
    )
    warnings.extend(ml_warnings)
    hybrid_rows, hybrid_metrics = (
        evaluate_hybrid_strategy(evaluation_examples, ml_prediction_rows)
        if ml_prediction_rows
        else ([], {"status": "partial"})
    )
    prediction_rows, disagreement_count = _build_prediction_rows(
        evaluation_examples,
        ml_prediction_rows,
        hybrid_rows,
    )
    error_rows = _build_error_rows(evaluation_examples, prediction_rows)

    metrics_by_model = {
        "rule_based_baseline": rule_metrics if rule_metrics.get("confusion_matrix") else {},
        "ml_text_model": ml_metrics if ml_metrics.get("confusion_matrix") else {},
        "hybrid_model": hybrid_metrics if hybrid_metrics.get("confusion_matrix") else {},
    }
    confusion_rows = _build_confusion_matrix_rows(
        {key: value for key, value in metrics_by_model.items() if value}
    )

    limitations = [
        "This is an offline research experiment and not a production replacement for the rule-based significance layer.",
        "The labeled corpus is small and class-imbalanced; metric stability is limited, especially for singleton labels.",
        "The ML model uses only lightweight lexical, structural and TF-IDF features without external models or network access.",
        "Hybrid predictions are conservative by design and prioritize high-priority recall over aggressive promotion.",
        "Real-world regression outputs may be used later as weak inference material, but they are not treated here as strict training labels.",
    ]

    summary_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_source": metadata.get("dataset_source"),
        "total_examples": len(examples),
        "label_distribution": label_distribution,
        "train_size": metadata.get("train_size", max(len(examples) - 1, 0) if examples else 0),
        "test_size": metadata.get("test_size", 1 if examples else 0),
        "cv_folds": 0 if test_examples is not None else (len(examples) if examples else 0),
        "models_evaluated": [
            "rule_based_baseline",
            *(
                ["ml_text_model", "hybrid_model"]
                if ml_prediction_rows
                else []
            ),
        ],
        "rule_based_metrics": rule_metrics,
        "ml_metrics": ml_metrics,
        "hybrid_metrics": hybrid_metrics,
        "binary_high_priority_metrics": {
            "rule_based_baseline": rule_metrics.get("binary", {}),
            "ml_text_model": ml_metrics.get("binary", {}),
            "hybrid_model": hybrid_metrics.get("binary", {}),
        },
        "disagreement_count": disagreement_count,
        "limitations": limitations,
        "warnings": warnings,
    }

    output_files = write_significance_ml_outputs(
        output_dir=output_dir,
        summary_payload={},
        prediction_rows=prediction_rows,
        confusion_rows=confusion_rows,
        feature_report_rows=feature_report_rows,
        error_rows=error_rows,
    )
    summary_payload["output_files"] = output_files
    _write_json(output_dir / "significance_ml_summary.json", summary_payload)
    return summary_payload
