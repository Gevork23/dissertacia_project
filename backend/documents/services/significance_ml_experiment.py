from __future__ import annotations

import csv
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from documents.services.importance import LABELS as SIGNIFICANCE_LABELS

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:  # pragma: no cover - optional plotting
    plt = None
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    import pandas as pd
    from scipy.sparse import csr_matrix, hstack
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        precision_recall_fscore_support,
        roc_auc_score,
    )
    from sklearn.model_selection import GridSearchCV, GroupShuffleSplit, RandomizedSearchCV, train_test_split
    from sklearn.svm import LinearSVC

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback
    np = None
    pd = None
    csr_matrix = None
    hstack = None
    CalibratedClassifierCV = None
    RandomForestClassifier = None
    DictVectorizer = None
    TfidfVectorizer = None
    LogisticRegression = None
    accuracy_score = None
    classification_report = None
    confusion_matrix = None
    precision_recall_fscore_support = None
    roc_auc_score = None
    GridSearchCV = None
    GroupShuffleSplit = None
    RandomizedSearchCV = None
    LinearSVC = None
    SKLEARN_AVAILABLE = False

try:
    from xgboost import XGBClassifier

    XGBOOST_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None
    XGBOOST_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import shap

    SHAP_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    shap = None
    SHAP_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "experiments" / "significance_ml"
DEFAULT_DATASET_CSV = (
    PROJECT_ROOT / "experiments" / "significance" / "significance_results.csv"
)
DEFAULT_SUPERVISED_CORPUS_DIR = PROJECT_ROOT / "experiments" / "ml_corpus"
DEFAULT_RANDOM_SEED = 42
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

LABELS = tuple(SIGNIFICANCE_LABELS)
HIGH_PRIORITY_LABELS = {"critical", "important"}
LEAKAGE_GUARD_BLOCKLIST = {
    "true_label",
    "significance_label",
    "y_significance",
    "y_high_priority",
    "high_priority_label",
}


NUMBER_RE = __import__("re").compile(r"\d")
DATE_LIKE_RE = __import__("re").compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")
LEGAL_REFERENCE_RE = __import__("re").compile(
    r"\b(статья|ст\.|пункт|п\.|раздел|глава|приказ|постановление|регламент)\b",
    __import__("re").IGNORECASE,
)
DEADLINE_RE = __import__("re").compile(r"\b(срок|дней|дня|рабочих|рабочие)\b", __import__("re").IGNORECASE)
OBLIGATION_RE = __import__("re").compile(
    r"\b(обязан|обязаны|обязана|должен|должна|должны)\b",
    __import__("re").IGNORECASE,
)
REFUSAL_RE = __import__("re").compile(r"\b(отказ|отказать|основание)\b", __import__("re").IGNORECASE)
DOCUMENT_RE = __import__("re").compile(
    r"\b(документ|документов|справк|копи|доверенност)\b",
    __import__("re").IGNORECASE,
)
RESPONSIBILITY_RE = __import__("re").compile(
    r"\b(ответственност|дисциплинар|санкц|нарушени)\b",
    __import__("re").IGNORECASE,
)
PROCEDURE_RE = __import__("re").compile(
    r"\b(процедур|порядок|подач|портал|электронн|уведомлен)\b",
    __import__("re").IGNORECASE,
)
EDITORIAL_RE = __import__("re").compile(
    r"\b(редакцион|формулировк|уточнен|переимен|структур)\b",
    __import__("re").IGNORECASE,
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
    document_id: str = ""
    is_gold: bool = False
    is_synthetic: bool = False
    is_weak: bool = False


@dataclass(frozen=True)
class SplitDefinition:
    split_strategy: str
    train_examples: list[SignificanceExample]
    test_examples: list[SignificanceExample]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    estimator_factory: Any | None = None
    search_space: dict[str, list[Any]] | None = None
    search_type: str = "grid"
    supports_proba: bool = True


@dataclass
class ModelBundle:
    model_name: str
    family: str
    estimator: Any
    text_vectorizer: Any | None
    meta_vectorizer: Any | None
    feature_names: list[str]
    uses_embeddings: bool = False
    embedding_model_name: str = ""


def rel_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


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


def _truncate(value: str, limit: int = 220) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


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


def map_high_priority(label: str) -> int:
    return int(str(label or "").strip().lower() in HIGH_PRIORITY_LABELS)


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
    combined = _normalize_text(
        " ".join([old_text, new_text, example.description, example.notes])
    )
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
        "semantic_responsibility": float(
            example.predicted_semantic_type == "responsibility"
        ),
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


def audit_feature_leakage() -> dict[str, Any]:
    sample_feature_names = sorted(extract_ml_features(_sample_example()).keys())
    violations = [
        feature_name
        for feature_name in sample_feature_names
        if feature_name in LEAKAGE_GUARD_BLOCKLIST
    ]
    return {
        "blocked_features": sorted(LEAKAGE_GUARD_BLOCKLIST),
        "inspected_features": sample_feature_names,
        "violations": violations,
        "passed": not violations,
        "note": (
            "All ML features are derived only from raw text, rule outputs available at "
            "inference time, and structural metadata. Gold labels are never used in X."
        ),
    }


def _sample_example() -> SignificanceExample:
    return SignificanceExample(
        example_id="sample",
        document_id="doc-1",
        pair_id="pair-1",
        change_id="chg-1",
        true_label="critical",
        rule_based_label="important",
        operation="modified",
        change_type="deadline_change",
        semantic_type="deadline",
        predicted_semantic_type="deadline",
        old_text="Срок составляет 10 дней.",
        new_text="Срок составляет 5 дней.",
        description="Сокращение срока.",
        notes="",
        requires_manual_review=False,
        source="sample.csv",
    )


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
                    document_id=str(row.get("document_id") or pair_id),
                    pair_id=pair_id,
                    change_id=change_id,
                    true_label=true_label,
                    rule_based_label=rule_based_label,
                    operation=str(row.get("operation") or ""),
                    change_type=str(row.get("change_type") or ""),
                    semantic_type=str(row.get("semantic_type") or ""),
                    predicted_semantic_type=str(
                        row.get("predicted_semantic_type")
                        or row.get("semantic_type")
                        or ""
                    ),
                    old_text=str(row.get("old_text") or ""),
                    new_text=str(row.get("new_text") or ""),
                    description=str(row.get("description") or ""),
                    notes=str(row.get("notes") or ""),
                    requires_manual_review=_parse_bool(
                        row.get("requires_manual_review")
                    ),
                    source=rel_repo_path(results_csv_path),
                    is_gold=True,
                )
            )

    label_distribution = dict(sorted(Counter(item.true_label for item in examples).items()))
    return examples, {
        "dataset_source": rel_repo_path(results_csv_path),
        "warnings": warnings,
        "label_distribution": label_distribution,
        "mode": "significance_csv",
    }


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
                true_label = _normalize_label(
                    row.get("y_significance") or row.get("significance_label") or ""
                )
                rule_based_label = _normalize_label(row.get("rule_based_label") or "")
                if not true_label or not rule_based_label:
                    continue
                pair_id = str(row.get("pair_id") or f"{split_name}_pair_{index:04d}")
                change_id = str(
                    row.get("change_id") or f"{split_name}_chg_{index:04d}"
                )
                rows.append(
                    SignificanceExample(
                        example_id=str(row.get("example_id") or f"{pair_id}:{change_id}"),
                        document_id=str(
                            row.get("document_id") or row.get("pair_id") or pair_id
                        ),
                        pair_id=pair_id,
                        change_id=change_id,
                        true_label=true_label,
                        rule_based_label=rule_based_label,
                        operation=str(
                            row.get("operation_type") or row.get("operation") or ""
                        ),
                        change_type=str(
                            row.get("semantic_type") or row.get("change_type") or ""
                        ),
                        semantic_type=str(row.get("semantic_type") or ""),
                        predicted_semantic_type=str(row.get("semantic_type") or ""),
                        old_text=str(row.get("old_text") or ""),
                        new_text=str(row.get("new_text") or ""),
                        description=str(row.get("notes") or ""),
                        notes=str(row.get("notes") or ""),
                        requires_manual_review=_parse_bool(
                            row.get("rule_based_requires_manual_review")
                        ),
                        source=str(row.get("source") or rel_repo_path(path)),
                        is_gold=_parse_bool(row.get("is_gold") or "1"),
                        is_synthetic=_parse_bool(row.get("is_synthetic")),
                        is_weak=_parse_bool(row.get("is_weak")),
                    )
                )
        return rows

    train_examples = _load(train_csv_path, "train")
    test_examples = _load(test_csv_path, "test")
    label_distribution = dict(
        sorted(Counter(item.true_label for item in (train_examples + test_examples)).items())
    )
    return train_examples, test_examples, {
        "dataset_source": f"{rel_repo_path(train_csv_path)} + {rel_repo_path(test_csv_path)}",
        "warnings": warnings,
        "label_distribution": label_distribution,
        "mode": "supervised_split",
        "train_size": len(train_examples),
        "test_size": len(test_examples),
    }


def evaluate_rule_based(examples: list[SignificanceExample]) -> dict[str, Any]:
    true_labels = [item.true_label for item in examples]
    predicted_labels = [item.rule_based_label for item in examples]
    metrics = _compute_multiclass_metrics(true_labels, predicted_labels)
    metrics["binary"] = _compute_binary_metrics(true_labels, predicted_labels)
    return metrics


def evaluate_hybrid_strategy(
    examples: list[SignificanceExample],
    ml_prediction_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hybrid_rows: list[dict[str, Any]] = []
    for example, ml_row in zip(examples, ml_prediction_rows):
        hybrid_label, hybrid_reason = _predict_hybrid_label(
            rule_label=example.rule_based_label,
            ml_label=str(ml_row.get("predicted_label") or ""),
            ml_confidence=float(ml_row.get("probability") or 0.0),
            probability_map=dict(ml_row.get("probability_map") or {}),
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


def _compute_multiclass_metrics(
    true_labels: list[str],
    predicted_labels: list[str],
    *,
    probability_matrix: list[list[float]] | None = None,
    probability_labels: list[str] | None = None,
) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        true_labels,
        predicted_labels,
        labels=list(LABELS),
        zero_division=0,
    )
    matrix = confusion_matrix(true_labels, predicted_labels, labels=list(LABELS))
    metrics = {
        "accuracy": round(float(accuracy_score(true_labels, predicted_labels)), 4),
        "precision_macro": round(float(sum(precision) / len(LABELS)), 4),
        "recall_macro": round(float(sum(recall) / len(LABELS)), 4),
        "f1_macro": round(float(sum(f1) / len(LABELS)), 4),
        "f1_weighted": round(
            float(
                precision_recall_fscore_support(
                    true_labels,
                    predicted_labels,
                    labels=list(LABELS),
                    average="weighted",
                    zero_division=0,
                )[2]
            ),
            4,
        ),
        "classification_report": classification_report(
            true_labels,
            predicted_labels,
            labels=list(LABELS),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix_labels": list(LABELS),
        "confusion_matrix": matrix.tolist(),
    }
    if probability_matrix and probability_labels and roc_auc_score is not None:
        try:
            label_to_index = {label: idx for idx, label in enumerate(probability_labels)}
            aligned = []
            for row in probability_matrix:
                aligned.append([row[label_to_index[label]] for label in LABELS])
            metrics["roc_auc_macro_ovr"] = round(
                float(
                    roc_auc_score(
                        true_labels,
                        aligned,
                        multi_class="ovr",
                        average="macro",
                        labels=list(LABELS),
                    )
                ),
                4,
            )
        except Exception:  # pragma: no cover - depends on class coverage
            metrics["roc_auc_macro_ovr"] = None
    else:
        metrics["roc_auc_macro_ovr"] = None
    return metrics


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
    return {
        "high_priority_precision": precision,
        "high_priority_recall": recall,
        "high_priority_f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def _group_split(
    examples: list[SignificanceExample],
    *,
    group_attr: str,
    random_seed: int,
    test_size: float = 0.2,
) -> tuple[list[SignificanceExample], list[SignificanceExample], dict[str, Any]] | None:
    if not examples:
        return None
    group_to_examples: dict[str, list[SignificanceExample]] = defaultdict(list)
    for example in examples:
        group_to_examples[str(getattr(example, group_attr) or example.pair_id)].append(
            example
        )
    if len(group_to_examples) < 2:
        return None

    group_ids = sorted(group_to_examples.keys())
    group_labels = []
    for group_id in group_ids:
        labels = [item.true_label for item in group_to_examples[group_id]]
        group_labels.append(Counter(labels).most_common(1)[0][0])

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_seed,
    )
    indices = list(range(len(group_ids)))
    train_index, test_index = next(
        splitter.split(indices, groups=group_ids, y=group_labels)
    )
    train_groups = {group_ids[idx] for idx in train_index}
    test_groups = {group_ids[idx] for idx in test_index}
    train_examples = [
        item for item in examples if str(getattr(item, group_attr) or item.pair_id) in train_groups
    ]
    test_examples = [
        item for item in examples if str(getattr(item, group_attr) or item.pair_id) in test_groups
    ]
    return train_examples, test_examples, {
        "group_attr": group_attr,
        "train_groups": sorted(train_groups),
        "test_groups": sorted(test_groups),
    }


def _random_stratified_split(
    examples: list[SignificanceExample],
    *,
    random_seed: int,
    test_size: float = 0.2,
) -> tuple[list[SignificanceExample], list[SignificanceExample]] | None:
    if len(examples) < 4:
        return None
    labels = [item.true_label for item in examples]
    if len(set(labels)) < 2:
        return None
    min_count = min(Counter(labels).values())
    stratify = labels if min_count >= 2 else None
    try:
        train_items, test_items = train_test_split(
            examples,
            test_size=test_size,
            random_state=random_seed,
            stratify=stratify,
        )
    except ValueError:
        train_items, test_items = train_test_split(
            examples,
            test_size=test_size,
            random_state=random_seed,
            stratify=None,
        )
    return list(train_items), list(test_items)


def _build_split_definitions(
    examples: list[SignificanceExample],
    *,
    random_seed: int,
    predefined_train: list[SignificanceExample] | None = None,
    predefined_test: list[SignificanceExample] | None = None,
) -> list[SplitDefinition]:
    split_definitions: list[SplitDefinition] = []
    strict_examples = [item for item in examples if item.is_weak is False]

    if predefined_train is not None and predefined_test is not None:
        split_definitions.append(
            SplitDefinition(
                split_strategy="predefined_supervised_split",
                train_examples=list(predefined_train),
                test_examples=list(predefined_test),
                metadata={"source": "precomputed train/test csv"},
            )
        )

    random_split = _random_stratified_split(strict_examples, random_seed=random_seed)
    if random_split:
        split_definitions.append(
            SplitDefinition(
                split_strategy="random_stratified_split",
                train_examples=random_split[0],
                test_examples=random_split[1],
                metadata={"seed": random_seed},
            )
        )

    document_split = _group_split(
        strict_examples,
        group_attr="document_id",
        random_seed=random_seed,
    )
    if document_split:
        split_definitions.append(
            SplitDefinition(
                split_strategy="group_split_document_id",
                train_examples=document_split[0],
                test_examples=document_split[1],
                metadata=document_split[2],
            )
        )

    pair_split = _group_split(
        strict_examples,
        group_attr="pair_id",
        random_seed=random_seed,
    )
    if pair_split:
        split_definitions.append(
            SplitDefinition(
                split_strategy="group_split_pair_id",
                train_examples=pair_split[0],
                test_examples=pair_split[1],
                metadata=pair_split[2],
            )
        )

    sources = sorted({item.source for item in strict_examples})
    if len(sources) >= 2:
        for test_source in sources:
            train_examples = [
                item for item in strict_examples if item.source != test_source
            ]
            test_examples = [item for item in strict_examples if item.source == test_source]
            if len(train_examples) >= 4 and len(test_examples) >= 2 and len({item.true_label for item in train_examples}) >= 2:
                split_definitions.append(
                    SplitDefinition(
                        split_strategy=f"cross_source_split__{test_source.replace('/', '_')}",
                        train_examples=train_examples,
                        test_examples=test_examples,
                        metadata={"test_source": test_source},
                    )
                )

    gold_only_examples = [
        item for item in examples if item.is_gold and not item.is_synthetic and not item.is_weak
    ]
    gold_split = _random_stratified_split(gold_only_examples, random_seed=random_seed)
    if gold_split:
        split_definitions.append(
            SplitDefinition(
                split_strategy="strict_gold_only_evaluation",
                train_examples=gold_split[0],
                test_examples=gold_split[1],
                metadata={"seed": random_seed, "gold_only": True},
            )
        )

    return split_definitions


def _build_model_specs() -> list[ModelSpec]:
    specs = [
        ModelSpec(
            name="tfidf_logistic_regression",
            family="tfidf",
            estimator_factory=lambda seed: LogisticRegression(
                max_iter=4000,
                class_weight="balanced",
                random_state=seed,
            ),
            search_space={
                "C": [0.25, 0.5, 1.0, 2.0],
                "solver": ["lbfgs"],
            },
        ),
        ModelSpec(
            name="tfidf_linear_svm",
            family="tfidf",
            estimator_factory=lambda seed: CalibratedClassifierCV(
                estimator=LinearSVC(
                    class_weight="balanced",
                    random_state=seed,
                    max_iter=50000,
                ),
                method="sigmoid",
                cv=3,
            ),
            search_space={
                "estimator__C": [0.25, 0.5, 1.0, 2.0],
            },
        ),
        ModelSpec(
            name="tfidf_random_forest",
            family="tfidf",
            estimator_factory=lambda seed: RandomForestClassifier(
                n_estimators=250,
                class_weight="balanced",
                random_state=seed,
            ),
            search_space={
                "n_estimators": [150, 250],
                "max_depth": [None, 12, 24],
            },
        ),
    ]
    if XGBOOST_AVAILABLE:
        specs.append(
            ModelSpec(
                name="tfidf_xgboost",
                family="tfidf",
                estimator_factory=lambda seed: XGBClassifier(
                    n_estimators=250,
                    max_depth=6,
                    learning_rate=0.1,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="multi:softprob",
                    random_state=seed,
                    eval_metric="mlogloss",
                ),
                search_space={
                    "max_depth": [4, 6],
                    "learning_rate": [0.05, 0.1],
                    "n_estimators": [150, 250],
                },
                search_type="randomized",
            )
        )
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        specs.append(
            ModelSpec(
                name="embedding_logistic_regression",
                family="embedding",
                estimator_factory=lambda seed: LogisticRegression(
                    max_iter=4000,
                    class_weight="balanced",
                    random_state=seed,
                ),
                search_space={"C": [0.5, 1.0, 2.0]},
            )
        )
    return specs


def _get_embedding_model(cache: dict[str, Any]) -> Any | None:
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None
    if "embedding_model" in cache:
        return cache["embedding_model"]
    try:
        cache["embedding_model"] = SentenceTransformer(
            DEFAULT_EMBEDDING_MODEL,
            local_files_only=True,
        )
    except Exception:  # pragma: no cover - environment/model availability
        cache["embedding_model"] = None
    return cache["embedding_model"]


def _build_tfidf_matrix(
    examples: list[SignificanceExample],
    *,
    text_vectorizer: Any | None = None,
    meta_vectorizer: Any | None = None,
) -> tuple[Any, Any, Any, list[str]]:
    texts = [_build_text_payload(item) for item in examples]
    if text_vectorizer is None:
        text_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=3000,
            min_df=1,
        )
        text_matrix = text_vectorizer.fit_transform(texts)
    else:
        text_matrix = text_vectorizer.transform(texts)

    feature_dicts = [extract_ml_features(item) for item in examples]
    if meta_vectorizer is None:
        meta_vectorizer = DictVectorizer(sparse=True)
        meta_matrix = meta_vectorizer.fit_transform(feature_dicts)
    else:
        meta_matrix = meta_vectorizer.transform(feature_dicts)

    matrix = hstack([text_matrix, meta_matrix]).tocsr()
    feature_names = [
        *[f"tfidf:{name}" for name in text_vectorizer.get_feature_names_out()],
        *[f"meta:{name}" for name in meta_vectorizer.get_feature_names_out()],
    ]
    return text_vectorizer, meta_vectorizer, matrix, feature_names


def _build_embedding_matrix(
    examples: list[SignificanceExample],
    *,
    embedding_model: Any,
) -> tuple[Any, list[str]]:
    embeddings = embedding_model.encode(
        [_build_text_payload(item) for item in examples],
        normalize_embeddings=True,
    )
    meta_features = np.asarray([list(extract_ml_features(item).values()) for item in examples], dtype=float)
    matrix = np.hstack([embeddings, meta_features])
    feature_names = [
        *[f"embedding:{index}" for index in range(embeddings.shape[1])],
        *[f"meta:{name}" for name in extract_ml_features(examples[0]).keys()],
    ]
    return matrix, feature_names


def _fit_with_search(
    estimator: Any,
    spec: ModelSpec,
    X_train: Any,
    y_train: list[str],
) -> Any:
    if not spec.search_space or len(y_train) < 12:
        estimator.fit(X_train, y_train)
        return estimator
    cv_folds = min(3, max(2, min(Counter(y_train).values())))
    if cv_folds < 2:
        estimator.fit(X_train, y_train)
        return estimator
    if spec.search_type == "randomized":
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=spec.search_space,
            n_iter=min(4, max(len(next(iter(spec.search_space.values()))), 1)),
            scoring="f1_macro",
            cv=cv_folds,
            random_state=DEFAULT_RANDOM_SEED,
        )
    else:
        search = GridSearchCV(
            estimator=estimator,
            param_grid=spec.search_space,
            scoring="f1_macro",
            cv=cv_folds,
        )
    search.fit(X_train, y_train)
    return search.best_estimator_


def _predict_with_probabilities(bundle: ModelBundle, X_test: Any) -> tuple[list[str], list[float], list[list[float]], list[str]]:
    predicted_labels = bundle.estimator.predict(X_test).tolist()
    if hasattr(bundle.estimator, "predict_proba"):
        probabilities = bundle.estimator.predict_proba(X_test)
        probability_rows = probabilities.tolist()
        probability_labels = list(bundle.estimator.classes_)
        confidences = [round(float(max(row)), 6) for row in probability_rows]
        return predicted_labels, confidences, probability_rows, probability_labels
    probability_labels = list(getattr(bundle.estimator, "classes_", LABELS))
    probability_rows = [
        [1.0 if label == predicted else 0.0 for label in probability_labels]
        for predicted in predicted_labels
    ]
    confidences = [1.0 for _ in predicted_labels]
    return predicted_labels, confidences, probability_rows, probability_labels


def _train_model_bundle(
    spec: ModelSpec,
    train_examples: list[SignificanceExample],
    *,
    random_seed: int,
    shared_cache: dict[str, Any],
) -> ModelBundle | None:
    y_train = [item.true_label for item in train_examples]
    if spec.name == "tfidf_linear_svm":
        min_class_count = min(Counter(y_train).values())
        if min_class_count < 2:
            return None
        cv_folds = min(3, min_class_count)
        estimator = CalibratedClassifierCV(
            estimator=LinearSVC(
                class_weight="balanced",
                random_state=random_seed,
                max_iter=50000,
            ),
            method="sigmoid",
            cv=cv_folds,
        )
    else:
        estimator = spec.estimator_factory(random_seed)
    if spec.family == "embedding":
        embedding_model = _get_embedding_model(shared_cache)
        if embedding_model is None:
            return None
        X_train, feature_names = _build_embedding_matrix(
            train_examples,
            embedding_model=embedding_model,
        )
        estimator = _fit_with_search(estimator, spec, X_train, y_train)
        return ModelBundle(
            model_name=spec.name,
            family=spec.family,
            estimator=estimator,
            text_vectorizer=embedding_model,
            meta_vectorizer=None,
            feature_names=feature_names,
            uses_embeddings=True,
            embedding_model_name=DEFAULT_EMBEDDING_MODEL,
        )

    text_vectorizer, meta_vectorizer, X_train, feature_names = _build_tfidf_matrix(
        train_examples
    )
    estimator = _fit_with_search(estimator, spec, X_train, y_train)
    return ModelBundle(
        model_name=spec.name,
        family=spec.family,
        estimator=estimator,
        text_vectorizer=text_vectorizer,
        meta_vectorizer=meta_vectorizer,
        feature_names=feature_names,
    )


def _transform_examples(bundle: ModelBundle, examples: list[SignificanceExample]) -> Any:
    if bundle.uses_embeddings:
        X_matrix, _ = _build_embedding_matrix(
            examples,
            embedding_model=bundle.text_vectorizer,
        )
        return X_matrix
    _, _, matrix, _ = _build_tfidf_matrix(
        examples,
        text_vectorizer=bundle.text_vectorizer,
        meta_vectorizer=bundle.meta_vectorizer,
    )
    return matrix


def _extract_feature_importance_rows(bundle: ModelBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    estimator = bundle.estimator
    if hasattr(estimator, "coef_"):
        coef_matrix = estimator.coef_
        for class_index, class_label in enumerate(estimator.classes_):
            coefficients = coef_matrix[class_index]
            top_indexes = np.argsort(coefficients)[-20:][::-1]
            for rank, feature_index in enumerate(top_indexes, start=1):
                rows.append(
                    {
                        "model": bundle.model_name,
                        "class_label": str(class_label),
                        "rank": rank,
                        "feature_name": bundle.feature_names[int(feature_index)],
                        "importance": round(float(coefficients[int(feature_index)]), 6),
                    }
                )
    elif hasattr(estimator, "feature_importances_"):
        importances = estimator.feature_importances_
        top_indexes = np.argsort(importances)[-20:][::-1]
        for rank, feature_index in enumerate(top_indexes, start=1):
            rows.append(
                {
                    "model": bundle.model_name,
                    "class_label": "global",
                    "rank": rank,
                    "feature_name": bundle.feature_names[int(feature_index)],
                    "importance": round(float(importances[int(feature_index)]), 6),
                }
            )
    return rows


def _extract_shap_rows(
    bundle: ModelBundle,
    X_sample: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not SHAP_AVAILABLE:
        return [], warnings
    try:
        if not hasattr(bundle.estimator, "predict_proba"):
            warnings.append(f"SHAP skipped for {bundle.model_name}: model has no probabilities.")
            return [], warnings
        explainer = shap.Explainer(bundle.estimator)
        shap_values = explainer(X_sample)
        abs_means = np.abs(shap_values.values).mean(axis=0)
        if abs_means.ndim > 1:
            abs_means = abs_means.mean(axis=0)
        top_indexes = np.argsort(abs_means)[-20:][::-1]
        return (
            [
                {
                    "model": bundle.model_name,
                    "feature_name": bundle.feature_names[int(index)],
                    "mean_abs_shap": round(float(abs_means[int(index)]), 6),
                }
                for index in top_indexes
            ],
            warnings,
        )
    except Exception as exc:  # pragma: no cover - optional environment integration
        warnings.append(f"SHAP skipped for {bundle.model_name}: {exc}")
        return [], warnings


def _predict_hybrid_label(
    *,
    rule_label: str,
    ml_label: str,
    ml_confidence: float,
    probability_map: dict[str, float],
) -> tuple[str, str]:
    rule_is_high = rule_label in HIGH_PRIORITY_LABELS
    ml_is_high = ml_label in HIGH_PRIORITY_LABELS
    ml_high_confidence = probability_map.get("critical", 0.0) + probability_map.get(
        "important", 0.0
    )

    if rule_label == "critical":
        return "critical", "rule_critical_lock"
    if rule_is_high and ml_is_high:
        return rule_label, "high_priority_confirmed"
    if not rule_is_high and ml_is_high and ml_confidence >= 0.75 and ml_high_confidence >= 0.75:
        return "important", "conservative_ml_promotion"
    if rule_is_high and not ml_is_high:
        return rule_label, "rule_priority_preserved"
    if not rule_is_high and not ml_is_high and ml_confidence >= 0.60:
        return ml_label, "low_priority_ml_selection"
    return rule_label, "fallback_rule_based"


def _library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for module_name, module_ref in (
        ("numpy", np),
        ("pandas", pd),
        ("scikit-learn", __import__("sklearn") if SKLEARN_AVAILABLE else None),
        ("xgboost", __import__("xgboost") if XGBOOST_AVAILABLE else None),
        ("sentence-transformers", __import__("sentence_transformers") if SENTENCE_TRANSFORMERS_AVAILABLE else None),
        ("shap", shap if SHAP_AVAILABLE else None),
    ):
        if module_ref is not None:
            versions[module_name] = str(getattr(module_ref, "__version__", "unknown"))
    return versions


def _git_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _class_distribution(examples: list[SignificanceExample]) -> dict[str, int]:
    return dict(sorted(Counter(item.true_label for item in examples).items()))


def _prediction_rows(
    examples: list[SignificanceExample],
    predicted_labels: list[str],
    confidences: list[float],
    probability_rows: list[list[float]],
    probability_labels: list[str],
    *,
    model_name: str,
) -> list[dict[str, Any]]:
    probability_index = {label: idx for idx, label in enumerate(probability_labels)}
    rows: list[dict[str, Any]] = []
    for example, predicted_label, confidence, probability_row in zip(
        examples, predicted_labels, confidences, probability_rows
    ):
        probability_map = {
            label: round(float(probability_row[probability_index[label]]), 6)
            for label in probability_labels
        }
        rows.append(
            {
                "model": model_name,
                "example_id": example.example_id,
                "document_id": example.document_id,
                "pair_id": example.pair_id,
                "change_id": example.change_id,
                "text": _truncate(_build_text_payload(example), limit=400),
                "true_label": example.true_label,
                "predicted_label": predicted_label,
                "rule_based_label": example.rule_based_label,
                "probability": confidence,
                "probability_map": probability_map,
                "source": example.source,
            }
        )
    return rows


def _error_analysis_rows(prediction_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    error_rows = []
    for row in prediction_rows:
        if row["predicted_label"] == row["true_label"]:
            continue
        error_rows.append(
            {
                "document_id": row["document_id"],
                "text": row["text"],
                "true_label": row["true_label"],
                "predicted_label": row["predicted_label"],
                "probability": row["probability"],
                "error_type": (
                    "false_negative"
                    if map_high_priority(row["true_label"]) == 1
                    and map_high_priority(row["predicted_label"]) == 0
                    else "false_positive"
                    if map_high_priority(row["true_label"]) == 0
                    and map_high_priority(row["predicted_label"]) == 1
                    else "multiclass_misclassification"
                ),
            }
        )
    return error_rows


def _save_confusion_plot(
    output_path: Path,
    labels: list[str],
    matrix: list[list[int]],
    *,
    title: str,
) -> None:
    if not MATPLOTLIB_AVAILABLE:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    image = ax.imshow(matrix, cmap="Blues")
    ax.figure.colorbar(image, ax=ax)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_yticklabels(labels)
    ax.set_title(title)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, value, ha="center", va="center", color="black")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _save_class_distribution_plot(
    output_path: Path,
    distribution: dict[str, int],
    *,
    title: str,
) -> None:
    if not MATPLOTLIB_AVAILABLE or not distribution:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = list(distribution.keys())
    values = list(distribution.values())
    ax.bar(labels, values, color="#2563eb")
    ax.set_title(title)
    ax.set_ylabel("Count")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _run_single_model(
    split_definition: SplitDefinition,
    spec: ModelSpec,
    *,
    output_root: Path,
    random_seed: int,
    shared_cache: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    train_examples = split_definition.train_examples
    test_examples = split_definition.test_examples
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / "runs" / f"{run_timestamp}_{split_definition.split_strategy}_{spec.name}"
    plots_dir = run_dir / "plots"

    if len({item.true_label for item in train_examples}) < 2:
        return {
            "status": "skipped",
            "model_name": spec.name,
            "split_strategy": split_definition.split_strategy,
            "reason": "training split does not contain at least two classes",
        }, warnings

    bundle = _train_model_bundle(
        spec,
        train_examples,
        random_seed=random_seed,
        shared_cache=shared_cache,
    )
    if bundle is None:
        return {
            "status": "skipped",
            "model_name": spec.name,
            "split_strategy": split_definition.split_strategy,
            "reason": "optional dependency or model artifact is unavailable",
        }, warnings

    X_test = _transform_examples(bundle, test_examples)
    predicted_labels, confidences, probability_rows, probability_labels = _predict_with_probabilities(
        bundle,
        X_test,
    )
    prediction_rows = _prediction_rows(
        test_examples,
        predicted_labels,
        confidences,
        probability_rows,
        probability_labels,
        model_name=spec.name,
    )
    metrics = _compute_multiclass_metrics(
        [item.true_label for item in test_examples],
        predicted_labels,
        probability_matrix=probability_rows,
        probability_labels=probability_labels,
    )
    metrics["binary"] = _compute_binary_metrics(
        [item.true_label for item in test_examples],
        predicted_labels,
    )
    feature_rows = _extract_feature_importance_rows(bundle)
    shap_rows, shap_warnings = _extract_shap_rows(
        bundle,
        X_test[: min(len(test_examples), 12)],
    )
    warnings.extend(shap_warnings)
    error_rows = _error_analysis_rows(prediction_rows)

    false_positives = sorted(
        [
            row
            for row in error_rows
            if row["error_type"] == "false_positive"
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    false_negatives = sorted(
        [
            row
            for row in error_rows
            if row["error_type"] == "false_negative"
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    most_confident_errors = sorted(error_rows, key=lambda item: item["probability"], reverse=True)[:20]
    least_confident_predictions = sorted(prediction_rows, key=lambda item: item["probability"])[:20]

    params_payload = {
        "model_name": spec.name,
        "model_family": spec.family,
        "split_strategy": split_definition.split_strategy,
        "random_seed": random_seed,
        "search_type": spec.search_type,
        "search_space": spec.search_space or {},
        "embedding_model": bundle.embedding_model_name or None,
    }
    split_info_payload = {
        "split_strategy": split_definition.split_strategy,
        "metadata": split_definition.metadata,
        "train_size": len(train_examples),
        "test_size": len(test_examples),
        "train_class_distribution": _class_distribution(train_examples),
        "test_class_distribution": _class_distribution(test_examples),
    }
    metrics_payload = {
        key: value
        for key, value in metrics.items()
        if key not in {"classification_report", "confusion_matrix", "confusion_matrix_labels"}
    }
    classification_report_payload = metrics["classification_report"]
    confusion_rows = []
    for true_index, true_label in enumerate(metrics["confusion_matrix_labels"]):
        for pred_index, predicted_label in enumerate(metrics["confusion_matrix_labels"]):
            confusion_rows.append(
                {
                    "true_label": true_label,
                    "predicted_label": predicted_label,
                    "count": metrics["confusion_matrix"][true_index][pred_index],
                }
            )
    manifest_payload = {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_commit_sha": _git_commit_sha(),
        "random_seed": random_seed,
        "model_name": spec.name,
        "feature_set": {
            "text": "tfidf_1_2gram" if spec.family == "tfidf" else "sentence_transformer_embeddings",
            "meta_features": sorted(extract_ml_features(train_examples[0]).keys()) if train_examples else [],
        },
        "split_strategy": split_definition.split_strategy,
        "dataset_size": len(train_examples) + len(test_examples),
        "class_balance": {
            "train": _class_distribution(train_examples),
            "test": _class_distribution(test_examples),
        },
        "library_versions": _library_versions(),
    }
    _write_json(run_dir / "metrics.json", metrics_payload)
    _write_json(run_dir / "params.json", params_payload)
    _write_json(run_dir / "split_info.json", split_info_payload)
    _write_json(run_dir / "classification_report.json", classification_report_payload)
    _write_csv(
        run_dir / "confusion_matrix.csv",
        confusion_rows,
        headers=["true_label", "predicted_label", "count"],
    )
    _write_csv(
        run_dir / "feature_importance.csv",
        feature_rows,
        headers=["model", "class_label", "rank", "feature_name", "importance"],
    )
    _write_csv(
        run_dir / "predictions.csv",
        prediction_rows,
        headers=[
            "model",
            "example_id",
            "document_id",
            "pair_id",
            "change_id",
            "text",
            "true_label",
            "predicted_label",
            "rule_based_label",
            "probability",
            "source",
        ],
    )
    _write_json(run_dir / "manifest.json", manifest_payload)
    _write_csv(
        run_dir / "error_analysis.csv",
        error_rows,
        headers=[
            "document_id",
            "text",
            "true_label",
            "predicted_label",
            "probability",
            "error_type",
        ],
    )
    _write_csv(
        run_dir / "shap_summary.csv",
        shap_rows,
        headers=["model", "feature_name", "mean_abs_shap"],
    )
    _write_json(
        run_dir / "error_summary.json",
        {
            "false_positives": false_positives[:20],
            "false_negatives": false_negatives[:20],
            "most_confident_errors": most_confident_errors,
            "least_confident_predictions": least_confident_predictions,
        },
    )
    _save_confusion_plot(
        plots_dir / "confusion_matrix.png",
        metrics["confusion_matrix_labels"],
        metrics["confusion_matrix"],
        title=f"{spec.name} / {split_definition.split_strategy}",
    )
    _save_class_distribution_plot(
        plots_dir / "class_distribution.png",
        split_info_payload["train_class_distribution"],
        title=f"Train distribution / {split_definition.split_strategy}",
    )

    return {
        "status": "available",
        "run_dir": rel_repo_path(run_dir),
        "model_name": spec.name,
        "split_strategy": split_definition.split_strategy,
        "metrics": metrics,
        "params": params_payload,
        "split_info": split_info_payload,
        "feature_importance_path": rel_repo_path(run_dir / "feature_importance.csv"),
        "predictions_path": rel_repo_path(run_dir / "predictions.csv"),
        "confusion_matrix_path": rel_repo_path(run_dir / "confusion_matrix.csv"),
        "manifest_path": rel_repo_path(run_dir / "manifest.json"),
        "error_analysis_path": rel_repo_path(run_dir / "error_analysis.csv"),
        "warnings": warnings,
    }, warnings


def _select_primary_run(run_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    available_runs = [
        item
        for item in run_results
        if item.get("status") == "available" and item.get("model_name") == "tfidf_logistic_regression"
    ]
    if available_runs:
        return sorted(
            available_runs,
            key=lambda item: item["metrics"].get("f1_macro", 0.0),
            reverse=True,
        )[0]
    available_runs = [item for item in run_results if item.get("status") == "available"]
    if not available_runs:
        return None
    return sorted(
        available_runs,
        key=lambda item: item["metrics"].get("f1_macro", 0.0),
        reverse=True,
    )[0]


def _mirror_primary_artifacts(primary_run: dict[str, Any], output_dir: Path) -> dict[str, str]:
    run_dir = PROJECT_ROOT / primary_run["run_dir"]
    root_outputs = {
        "summary": output_dir / "significance_ml_summary.json",
        "predictions": output_dir / "significance_ml_predictions.csv",
        "confusion_matrix": output_dir / "significance_ml_confusion_matrix.csv",
        "feature_report": output_dir / "significance_ml_feature_report.csv",
        "error_examples": output_dir / "significance_ml_error_examples.csv",
    }
    shutil.copyfile(run_dir / "predictions.csv", root_outputs["predictions"])
    shutil.copyfile(run_dir / "confusion_matrix.csv", root_outputs["confusion_matrix"])
    shutil.copyfile(run_dir / "feature_importance.csv", root_outputs["feature_report"])
    shutil.copyfile(run_dir / "error_analysis.csv", root_outputs["error_examples"])
    return {key: rel_repo_path(path) for key, path in root_outputs.items()}


def run_significance_ml_experiment(
    *,
    dataset_csv_path: Path = DEFAULT_DATASET_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    supervised_corpus_dir: Path = DEFAULT_SUPERVISED_CORPUS_DIR,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    leakage_audit = audit_feature_leakage()
    if not leakage_audit["passed"]:
        raise RuntimeError(
            f"Target leakage guard failed: {', '.join(leakage_audit['violations'])}"
        )

    train_csv_path = supervised_corpus_dir / "train.csv"
    test_csv_path = supervised_corpus_dir / "test.csv"
    predefined_train: list[SignificanceExample] | None = None
    predefined_test: list[SignificanceExample] | None = None

    if train_csv_path.exists() and test_csv_path.exists():
        predefined_train, predefined_test, metadata = collect_significance_dataset_from_supervised_corpus(
            train_csv_path=train_csv_path,
            test_csv_path=test_csv_path,
        )
        examples = [*predefined_train, *predefined_test]
    else:
        examples, metadata = collect_significance_dataset(dataset_csv_path)

    warnings.extend(list(metadata.get("warnings") or []))
    if not SKLEARN_AVAILABLE:
        summary_payload = {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "dataset_source": metadata.get("dataset_source"),
            "total_examples": len(examples),
            "models_evaluated": ["rule_based_baseline"],
            "warnings": warnings + ["scikit-learn is not available; ML runs were skipped."],
            "leakage_audit": leakage_audit,
        }
        _write_json(output_dir / "significance_ml_summary.json", summary_payload)
        return summary_payload

    split_definitions = _build_split_definitions(
        examples,
        random_seed=random_seed,
        predefined_train=predefined_train,
        predefined_test=predefined_test,
    )
    if not split_definitions:
        summary_payload = {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "dataset_source": metadata.get("dataset_source"),
            "total_examples": len(examples),
            "models_evaluated": ["rule_based_baseline"],
            "warnings": warnings + ["No valid train/test splits were available."],
            "leakage_audit": leakage_audit,
        }
        _write_json(output_dir / "significance_ml_summary.json", summary_payload)
        return summary_payload

    rule_metrics = evaluate_rule_based(predefined_test or examples) if examples else {"status": "missing"}
    run_results: list[dict[str, Any]] = []
    model_specs = _build_model_specs()
    shared_cache: dict[str, Any] = {}

    for split_definition in split_definitions:
        for spec in model_specs:
            run_result, run_warnings = _run_single_model(
                split_definition,
                spec,
                output_root=output_dir,
                random_seed=random_seed,
                shared_cache=shared_cache,
            )
            run_results.append(run_result)
            warnings.extend(run_warnings)

    primary_run = _select_primary_run(run_results)
    if primary_run is None:
        summary_payload = {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "dataset_source": metadata.get("dataset_source"),
            "total_examples": len(examples),
            "models_evaluated": ["rule_based_baseline"],
            "warnings": warnings + ["All ML runs were skipped."],
            "leakage_audit": leakage_audit,
        }
        _write_json(output_dir / "significance_ml_summary.json", summary_payload)
        return summary_payload

    primary_run_dir = PROJECT_ROOT / primary_run["run_dir"]
    primary_prediction_rows = []
    with (primary_run_dir / "predictions.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        primary_prediction_rows = list(reader)
    primary_split_definition = next(
        (
            item
            for item in split_definitions
            if item.split_strategy == primary_run["split_strategy"]
        ),
        None,
    )
    primary_examples = (
        primary_split_definition.test_examples
        if primary_split_definition is not None
        else (predefined_test or examples)
    )
    hybrid_rows, hybrid_metrics = evaluate_hybrid_strategy(
        primary_examples,
        [
            {
                "predicted_label": row.get("predicted_label", ""),
                "probability": float(row.get("probability") or 0.0),
                "probability_map": {},
            }
            for row in primary_prediction_rows
        ],
    )
    disagreement_count = sum(
        1
        for example, row in zip(primary_examples, primary_prediction_rows)
        if row.get("predicted_label") and row.get("predicted_label") != example.rule_based_label
    )

    output_files = _mirror_primary_artifacts(primary_run, output_dir)
    output_files["summary"] = rel_repo_path(output_dir / "significance_ml_summary.json")

    summary_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_source": metadata.get("dataset_source"),
        "total_examples": len(examples),
        "train_size": primary_run["split_info"]["train_size"],
        "test_size": primary_run["split_info"]["test_size"],
        "models_evaluated": sorted(
            {
                "rule_based_baseline",
                *(item["model_name"] for item in run_results if item.get("status") == "available"),
                "hybrid_rule_ml",
            }
        ),
        "split_strategies_evaluated": sorted(
            {item["split_strategy"] for item in run_results if item.get("split_strategy")}
        ),
        "rule_based_metrics": rule_metrics,
        "ml_metrics": primary_run["metrics"],
        "hybrid_metrics": hybrid_metrics,
        "binary_high_priority_metrics": {
            "rule_based_baseline": rule_metrics.get("binary", {}),
            primary_run["model_name"]: primary_run["metrics"].get("binary", {}),
            "hybrid_rule_ml": hybrid_metrics.get("binary", {}),
        },
        "label_distribution": metadata.get("label_distribution", {}),
        "leakage_audit": leakage_audit,
        "primary_run": primary_run,
        "experiment_runs": run_results,
        "disagreement_count": disagreement_count,
        "limitations": [
            "Embedding, XGBoost and SHAP integrations are optional and depend on local environment availability.",
            "Cross-source evaluation quality depends on source diversity in the corpus; some holdouts may be skipped when class coverage is insufficient.",
            "Hybrid predictions remain conservative and preserve the rule-based signal for high-priority labels.",
        ],
        "warnings": warnings,
        "output_files": output_files,
    }
    _write_json(output_dir / "significance_ml_summary.json", summary_payload)
    return summary_payload
