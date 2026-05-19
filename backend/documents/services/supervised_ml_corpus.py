from __future__ import annotations

import csv
import json
import math
import os
import re
import warnings
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:  # pragma: no cover
    plt = None
    MATPLOTLIB_AVAILABLE = False

from documents.services.importance import classify_change_importance

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "experiments" / "ml_corpus"
DEFAULT_SIGNIFICANCE_RESULTS_PATH = (
    PROJECT_ROOT / "experiments" / "significance" / "significance_results.csv"
)
DEFAULT_EVALUATION_CORPUS_DIR = PROJECT_ROOT / "data" / "evaluation_corpus"
DEFAULT_REAL_WORLD_TRACE_PATH = (
    PROJECT_ROOT / "experiments" / "real_world" / "real_world_trace.csv"
)
DEFAULT_RUSLAWOD_CASES_PATH = PROJECT_ROOT / "regression" / "ruslawod_test_cases.json"
DEFAULT_ANNOTATION_EXPORT_JSON = PROJECT_ROOT / "exports" / "annotations_export.json"
DEFAULT_ANNOTATION_EXPORT_CSV = PROJECT_ROOT / "exports" / "annotations_export.csv"

SIGNIFICANCE_LABELS = ("critical", "important", "informational", "editorial")
HIGH_PRIORITY_LABELS = {"critical", "important"}

NUMBER_RE = re.compile(r"\d")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?|\d{1,2}\s+[а-яё]+\s+\d{4}\s+г\.?)\b",
    re.IGNORECASE,
)
DEADLINE_RE = re.compile(r"\b(срок|дней|дня|рабочих|рабочие|календарных)\b", re.IGNORECASE)
OBLIGATION_RE = re.compile(r"\b(обязан|обязаны|обязана|должен|должна|должны|подлежит)\b", re.IGNORECASE)
REFUSAL_RE = re.compile(r"\b(отказ|отказать|основание|приостанавливается)\b", re.IGNORECASE)
DOCUMENT_RE = re.compile(r"\b(документ|документов|справк|копи|доверенност|заявлен)\b", re.IGNORECASE)
RESPONSIBILITY_RE = re.compile(
    r"\b(ответственност|дисциплинар|санкц|штраф|нарушени)\b",
    re.IGNORECASE,
)
PROCEDURE_RE = re.compile(
    r"\b(процедур|порядок|подач|портал|уведомлен|последовательност|маршрут)\b",
    re.IGNORECASE,
)
PAYMENT_RE = re.compile(r"\b(пошлин|платеж|оплат|сбор|тариф|стоимост)\b", re.IGNORECASE)
EDITORIAL_RE = re.compile(
    r"\b(редакцион|формулировк|уточнен|переимен|структур|орфограф|пунктуац)\b",
    re.IGNORECASE,
)
LEGAL_REFERENCE_RE = re.compile(
    r"\b(статья|ст\.|пункт|п\.|раздел|глава|приказ|постановление|регламент|приложение)\b",
    re.IGNORECASE,
)
MODAL_RE = re.compile(r"\b(может|вправе|обязан|должен|подлежит|необходимо)\b", re.IGNORECASE)


@dataclass
class CorpusExample:
    example_id: str
    source: str
    source_file: str
    pair_id: str
    change_id: str
    old_text: str
    new_text: str
    combined_text: str
    operation_type: str
    semantic_type: str
    significance_label: str
    high_priority_label: int
    is_gold: int
    is_synthetic: int
    is_weak: int
    label_source: str
    confidence: float
    notes: str
    old_length: int
    new_length: int
    length_delta: int
    relative_length_delta: float
    has_number: int
    has_date: int
    has_deadline_terms: int
    has_obligation_terms: int
    has_refusal_terms: int
    has_document_terms: int
    has_responsibility_terms: int
    has_procedure_terms: int
    has_payment_terms: int
    has_editorial_terms: int
    has_legal_reference: int
    has_modal_verbs: int
    text_complexity_bucket: str
    y_significance: str
    y_high_priority: int
    y_semantic_type: str
    rule_based_label: str
    rule_based_confidence: float
    rule_based_reason: str
    rule_based_requires_manual_review: int


def rel_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _high_priority(value: str) -> int:
    return int(str(value or "").strip().lower() in HIGH_PRIORITY_LABELS)


def _complexity_bucket(length: int) -> str:
    if length < 120:
        return "short"
    if length < 260:
        return "medium"
    return "long"


def _feature_flags(text: str) -> dict[str, int]:
    normalized = _normalize_text(text)
    return {
        "has_number": int(bool(NUMBER_RE.search(normalized))),
        "has_date": int(bool(DATE_RE.search(normalized))),
        "has_deadline_terms": int(bool(DEADLINE_RE.search(normalized))),
        "has_obligation_terms": int(bool(OBLIGATION_RE.search(normalized))),
        "has_refusal_terms": int(bool(REFUSAL_RE.search(normalized))),
        "has_document_terms": int(bool(DOCUMENT_RE.search(normalized))),
        "has_responsibility_terms": int(bool(RESPONSIBILITY_RE.search(normalized))),
        "has_procedure_terms": int(bool(PROCEDURE_RE.search(normalized))),
        "has_payment_terms": int(bool(PAYMENT_RE.search(normalized))),
        "has_editorial_terms": int(bool(EDITORIAL_RE.search(normalized))),
        "has_legal_reference": int(bool(LEGAL_REFERENCE_RE.search(normalized))),
        "has_modal_verbs": int(bool(MODAL_RE.search(normalized))),
    }


def _make_example(
    *,
    example_id: str,
    source: str,
    source_file: str,
    pair_id: str,
    change_id: str,
    old_text: str,
    new_text: str,
    operation_type: str,
    semantic_type: str,
    significance_label: str,
    is_gold: bool,
    is_synthetic: bool,
    is_weak: bool,
    label_source: str,
    confidence: float,
    notes: str,
) -> CorpusExample:
    old_text = _normalize_text(old_text)
    new_text = _normalize_text(new_text)
    combined_text = _normalize_text(" ".join(part for part in [old_text, new_text] if part))
    old_length = len(old_text)
    new_length = len(new_text)
    length_delta = abs(new_length - old_length)
    relative_length_delta = round(length_delta / max(old_length, new_length, 1), 4)
    flags = _feature_flags(combined_text)
    prediction = classify_change_importance(
        old_text=old_text,
        new_text=new_text,
        change_type=semantic_type if semantic_type.endswith("_change") else semantic_type,
        diff_text=f"OLD: {old_text}\nNEW: {new_text}",
    )

    return CorpusExample(
        example_id=example_id,
        source=source,
        source_file=source_file,
        pair_id=pair_id,
        change_id=change_id,
        old_text=old_text,
        new_text=new_text,
        combined_text=combined_text,
        operation_type=operation_type,
        semantic_type=semantic_type,
        significance_label=significance_label,
        high_priority_label=_high_priority(significance_label),
        is_gold=int(is_gold),
        is_synthetic=int(is_synthetic),
        is_weak=int(is_weak),
        label_source=label_source,
        confidence=round(float(confidence), 4),
        notes=notes,
        old_length=old_length,
        new_length=new_length,
        length_delta=length_delta,
        relative_length_delta=relative_length_delta,
        has_number=flags["has_number"],
        has_date=flags["has_date"],
        has_deadline_terms=flags["has_deadline_terms"],
        has_obligation_terms=flags["has_obligation_terms"],
        has_refusal_terms=flags["has_refusal_terms"],
        has_document_terms=flags["has_document_terms"],
        has_responsibility_terms=flags["has_responsibility_terms"],
        has_procedure_terms=flags["has_procedure_terms"],
        has_payment_terms=flags["has_payment_terms"],
        has_editorial_terms=flags["has_editorial_terms"],
        has_legal_reference=flags["has_legal_reference"],
        has_modal_verbs=flags["has_modal_verbs"],
        text_complexity_bucket=_complexity_bucket(len(combined_text)),
        y_significance=significance_label,
        y_high_priority=_high_priority(significance_label),
        y_semantic_type=semantic_type,
        rule_based_label=prediction.label,
        rule_based_confidence=round(float(prediction.confidence), 4),
        rule_based_reason=prediction.explanation,
        rule_based_requires_manual_review=int(prediction.requires_manual_review),
    )


def _dedupe_examples(examples: list[CorpusExample]) -> list[CorpusExample]:
    seen: dict[str, CorpusExample] = {}
    for item in examples:
        seen.setdefault(item.example_id, item)
    return list(seen.values())


def collect_gold_examples_from_significance_results(
    path: Path = DEFAULT_SIGNIFICANCE_RESULTS_PATH,
) -> list[CorpusExample]:
    if not path.exists():
        return []
    items: list[CorpusExample] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            pair_id = str(row.get("pair_id") or "")
            change_id = str(row.get("change_id") or "")
            label = str(row.get("expected_importance") or "").strip().lower()
            if not pair_id or not change_id or label not in SIGNIFICANCE_LABELS:
                continue
            items.append(
                _make_example(
                    example_id=f"{pair_id}:{change_id}",
                    source="significance_gold_results",
                    source_file=rel_repo_path(path),
                    pair_id=pair_id,
                    change_id=change_id,
                    old_text=str(row.get("old_text") or ""),
                    new_text=str(row.get("new_text") or ""),
                    operation_type=str(row.get("operation") or "modified"),
                    semantic_type=str(row.get("semantic_type") or "mixed_change"),
                    significance_label=label,
                    is_gold=True,
                    is_synthetic=False,
                    is_weak=False,
                    label_source="significance_results_csv",
                    confidence=1.0,
                    notes=str(row.get("description") or row.get("notes") or ""),
                )
            )
    return items


def collect_gold_examples_from_evaluation_corpus(
    directory: Path = DEFAULT_EVALUATION_CORPUS_DIR,
) -> list[CorpusExample]:
    if not directory.exists():
        return []
    items: list[CorpusExample] = []
    for annotation_path in sorted(directory.glob("*/annotation.json")):
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        pair_id = str(payload.get("pair_id") or annotation_path.parent.name)
        for raw_change in payload.get("expected_changes", []):
            label = str(raw_change.get("importance") or "").strip().lower()
            if label not in SIGNIFICANCE_LABELS:
                continue
            change_id = str(raw_change.get("id") or f"chg_{len(items)+1:04d}")
            items.append(
                _make_example(
                    example_id=f"{pair_id}:{change_id}",
                    source="evaluation_corpus_annotation",
                    source_file=rel_repo_path(annotation_path),
                    pair_id=pair_id,
                    change_id=change_id,
                    old_text=str(raw_change.get("old_text") or ""),
                    new_text=str(raw_change.get("new_text") or ""),
                    operation_type=str(raw_change.get("type") or "modified"),
                    semantic_type=str(raw_change.get("change_type") or raw_change.get("semantic_type") or "mixed_change"),
                    significance_label=label,
                    is_gold=True,
                    is_synthetic=False,
                    is_weak=False,
                    label_source="evaluation_annotation_json",
                    confidence=1.0,
                    notes=str(raw_change.get("description") or ""),
                )
            )
    return items


def collect_annotation_examples_from_db() -> tuple[list[CorpusExample], list[str]]:
    warnings: list[str] = []
    try:
        from django.apps import apps
        from django.db import OperationalError, ProgrammingError

        if not apps.ready:
            warnings.append("Django app registry is not ready; annotation DB source was skipped.")
            return [], warnings

        from documents.models import GoldChangeAnnotation

        queryset = (
            GoldChangeAnnotation.objects.select_related(
                "change_item__comparison__document",
                "change_item__comparison__from_version",
                "change_item__comparison__to_version",
            )
            .exclude(corrected_significance_label="")
            .all()
        )
        items: list[CorpusExample] = []
        for annotation in queryset:
            change_item = annotation.change_item
            label = str(annotation.corrected_significance_label or "").strip().lower()
            if label not in SIGNIFICANCE_LABELS:
                continue
            pair_id = f"comparison_{change_item.comparison_id}"
            change_id = f"change_item_{change_item.id}"
            items.append(
                _make_example(
                    example_id=f"db:{annotation.id}",
                    source="annotation_studio_db",
                    source_file="database:GoldChangeAnnotation",
                    pair_id=pair_id,
                    change_id=change_id,
                    old_text=str(getattr(change_item, "old_text", "") or ""),
                    new_text=str(getattr(change_item, "new_text", "") or ""),
                    operation_type=str(getattr(change_item, "change_type", "modified") or "modified"),
                    semantic_type=str(annotation.corrected_semantic_type or getattr(change_item, "semantic_type", "") or "mixed_change"),
                    significance_label=label,
                    is_gold=True,
                    is_synthetic=False,
                    is_weak=False,
                    label_source="gold_change_annotation_db",
                    confidence=1.0,
                    notes=str(annotation.comment or ""),
                )
            )
        return items, warnings
    except Exception as exc:  # pragma: no cover - optional source
        warnings.append(f"Annotation DB source was skipped: {exc}")
        return [], warnings


def collect_annotation_examples_from_exports(
    json_path: Path = DEFAULT_ANNOTATION_EXPORT_JSON,
    csv_path: Path = DEFAULT_ANNOTATION_EXPORT_CSV,
) -> tuple[list[CorpusExample], list[str]]:
    warnings: list[str] = []
    items: list[CorpusExample] = []
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            change_annotations = payload.get("change_annotations", [])
            for index, row in enumerate(change_annotations, start=1):
                label = str(row.get("corrected_significance_label") or "").strip().lower()
                if label not in SIGNIFICANCE_LABELS:
                    continue
                pair_id = str(row.get("comparison_id") or f"export_pair_{index:04d}")
                change_id = str(row.get("change_item_id") or f"change_{index:04d}")
                items.append(
                    _make_example(
                        example_id=f"export_json:{change_id}:{index}",
                        source="annotation_export_json",
                        source_file=rel_repo_path(json_path),
                        pair_id=pair_id,
                        change_id=change_id,
                        old_text=str(row.get("old_text") or ""),
                        new_text=str(row.get("new_text") or ""),
                        operation_type=str(row.get("operation_type") or "modified"),
                        semantic_type=str(row.get("corrected_semantic_type") or row.get("semantic_type") or "mixed_change"),
                        significance_label=label,
                        is_gold=True,
                        is_synthetic=False,
                        is_weak=False,
                        label_source="annotation_export_json",
                        confidence=1.0,
                        notes=str(row.get("comment") or ""),
                    )
                )
        except Exception as exc:  # pragma: no cover
            warnings.append(f"Annotation export JSON was skipped: {exc}")
    elif csv_path.exists():
        warnings.append("Only CSV annotation export is available; direct change-level reconstruction is limited and was skipped.")
    return items, warnings


def _variant_records(*records: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"old": old, "new": new, "note": note} for old, new, note in records]


CURATED_FAMILIES: list[dict[str, Any]] = [
    {
        "semantic_type": "deadline_change",
        "label": "critical",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Срок рассмотрения заявления составляет 15 рабочих дней.", "Срок рассмотрения заявления составляет 10 рабочих дней.", "Сокращение срока рассмотрения."),
            ("Запрос подлежит обработке в течение 20 календарных дней.", "Запрос подлежит обработке в течение 12 календарных дней.", "Сокращен календарный срок обработки."),
            ("Справка выдается не позднее 7 рабочих дней.", "Справка выдается не позднее 3 рабочих дней.", "Срок выдачи справки сокращен."),
            ("Сотрудник направляет ответ в течение 5 рабочих дней.", "Сотрудник направляет ответ в течение 2 рабочих дней.", "Сокращен срок направления ответа."),
            ("Обращение хранится до 30 календарных дней.", "Обращение хранится до 10 календарных дней.", "Сокращен срок хранения обращения."),
            ("Срок повторной проверки составляет 14 дней.", "Срок повторной проверки составляет 5 дней.", "Сокращен срок повторной проверки."),
            ("Уточнение документов допускается в течение 9 рабочих дней.", "Уточнение документов допускается в течение 4 рабочих дней.", "Сокращен срок уточнения документов."),
            ("Информация о результате предоставляется в течение 6 рабочих дней.", "Информация о результате предоставляется в течение 1 рабочего дня.", "Изменен срок информирования."),
            ("Срок ответа на внутренний запрос составляет 11 рабочих дней.", "Срок ответа на внутренний запрос составляет 5 рабочих дней.", "Сокращен внутренний срок ответа."),
            ("Проверка полномочий проводится в течение 8 рабочих дней.", "Проверка полномочий проводится в течение 2 рабочих дней.", "Сокращен срок проверки полномочий."),
        ),
    },
    {
        "semantic_type": "obligation_change",
        "label": "critical",
        "operation_type": "added",
        "variants": _variant_records(
            ("", "Сотрудник обязан уведомить заявителя о результатах проверки в день принятия решения.", "Добавлена новая обязанность уведомления."),
            ("", "Ответственный специалист обязан проверить комплектность документов до регистрации обращения.", "Добавлена обязанность предварительной проверки."),
            ("", "Сотрудник обязан зафиксировать причину отказа в журнале регистрации.", "Добавлена обязанность фиксации причины отказа."),
            ("", "Специалист обязан приложить копию доверенности к электронному досье.", "Добавлена обязанность приложить документ."),
            ("", "Сотрудник обязан направить запрос в профильное подразделение при выявлении расхождений.", "Добавлена обязанность межведомственного запроса."),
            ("", "Ответственный специалист обязан уведомить руководителя о нарушении срока обработки.", "Добавлена обязанность эскалации."),
            ("", "Сотрудник обязан сформировать проект ответа в течение одного рабочего дня.", "Добавлена обязанность оперативной подготовки ответа."),
            ("", "Исполнитель обязан проверить наличие обязательных приложений перед передачей дела.", "Добавлена обязанность проверки приложений."),
            ("", "Сотрудник обязан уведомить заявителя о приостановлении процедуры через портал.", "Добавлена обязанность уведомления о приостановлении."),
            ("", "Специалист обязан внести отметку о проведении консультации в учетную систему.", "Добавлена обязанность регистрации консультации."),
        ),
    },
    {
        "semantic_type": "refusal_ground_change",
        "label": "critical",
        "operation_type": "added",
        "variants": _variant_records(
            ("", "Основанием для отказа является непредставление обязательных документов в установленный срок.", "Добавлено основание отказа по сроку."),
            ("", "Основанием для отказа является несоответствие доверенности установленной форме.", "Добавлено основание отказа по доверенности."),
            ("", "Основанием для отказа является отсутствие подтверждения оплаты обязательного сбора.", "Добавлено основание отказа по оплате."),
            ("", "Основанием для отказа является предоставление недостоверных сведений о заявителе.", "Добавлено основание отказа по достоверности."),
            ("", "Основанием для отказа является нарушение срока подачи повторного заявления.", "Добавлено основание отказа по сроку подачи."),
            ("", "Основанием для отказа является отсутствие документа, подтверждающего полномочия представителя.", "Добавлено основание отказа по полномочиям."),
            ("", "Основанием для отказа является отсутствие согласия на обработку персональных данных.", "Добавлено основание отказа по согласию."),
            ("", "Основанием для отказа является непредставление оригинала платежного документа.", "Добавлено основание отказа по платежному документу."),
            ("", "Основанием для отказа является несоблюдение установленного канала подачи заявления.", "Добавлено основание отказа по каналу подачи."),
            ("", "Основанием для отказа является нарушение условий допуска к процедуре.", "Добавлено основание отказа по условиям допуска."),
        ),
    },
    {
        "semantic_type": "responsibility_change",
        "label": "critical",
        "operation_type": "added",
        "variants": _variant_records(
            ("", "За нарушение срока обработки заявления сотрудник несет дисциплинарную ответственность.", "Добавлена дисциплинарная ответственность."),
            ("", "За несвоевременное уведомление заявителя ответственный специалист несет персональную ответственность.", "Добавлена персональная ответственность."),
            ("", "За неправомерный отказ в приеме документов сотрудник подлежит служебной проверке.", "Добавлена ответственность за неправомерный отказ."),
            ("", "За неполную фиксацию результатов проверки исполнитель несет ответственность в соответствии с регламентом.", "Добавлена ответственность за неполную фиксацию."),
            ("", "За разглашение служебной информации сотрудник несет ответственность по внутренним правилам.", "Добавлена ответственность за разглашение."),
            ("", "За утрату бумажного досье сотрудник несет материальную ответственность.", "Добавлена материальная ответственность."),
            ("", "За несоблюдение порядка передачи дела сотрудник несет дисциплинарную ответственность.", "Добавлена ответственность за передачу дела."),
            ("", "За искажение сведений в учетной системе специалист подлежит внутреннему разбирательству.", "Добавлена ответственность за искажение сведений."),
            ("", "За нарушение сроков согласования руководитель подразделения несет персональную ответственность.", "Добавлена ответственность руководителя."),
            ("", "За отсутствие отметки о консультации сотрудник несет ответственность по правилам подразделения.", "Добавлена ответственность за отсутствие отметки."),
        ),
    },
    {
        "semantic_type": "procedure_change",
        "label": "important",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Заявление подается на бумажном носителе через ответственное подразделение.", "Заявление может быть подано через ответственное подразделение либо через электронную форму портала.", "Изменен порядок подачи заявления."),
            ("Проверка сведений проводится после регистрации обращения.", "Проверка сведений проводится до регистрации обращения.", "Изменена последовательность проверки."),
            ("Уведомление направляется после завершения согласования.", "Уведомление направляется до передачи дела на согласование.", "Изменен порядок уведомления."),
            ("Сотрудник принимает документы без предварительной записи.", "Сотрудник принимает документы по предварительной записи через внутренний портал.", "Добавлена запись через портал."),
            ("Запрос в профильное подразделение направляется вручную.", "Запрос в профильное подразделение направляется через электронную систему маршрутизации.", "Изменен способ направления запроса."),
            ("Повторная проверка выполняется тем же специалистом.", "Повторная проверка выполняется профильным подразделением.", "Изменен исполнитель повторной проверки."),
            ("Результат проверки согласуется только руководителем сектора.", "Результат проверки согласуется руководителем сектора и начальником отдела.", "Изменен маршрут согласования."),
            ("Заявитель получает уведомление по телефону.", "Заявитель получает уведомление через портал и по телефону.", "Изменен порядок уведомления о результате."),
            ("Дело передается на хранение после подготовки ответа.", "Дело передается на хранение после подтверждения получения ответа заявителем.", "Изменен порядок передачи на хранение."),
            ("Учетная запись создается после приема документов.", "Учетная запись создается до приема документов для предварительной проверки.", "Изменена последовательность создания записи."),
        ),
    },
    {
        "semantic_type": "document_list_change",
        "label": "important",
        "operation_type": "added",
        "variants": _variant_records(
            ("", "В перечень документов включается копия документа, подтверждающего полномочия представителя.", "Добавлен документ о полномочиях представителя."),
            ("", "К заявлению прилагается копия документа, подтверждающего регистрацию по месту пребывания.", "Добавлен документ о регистрации."),
            ("", "В комплект документов включается справка о составе семьи.", "Добавлена справка о составе семьи."),
            ("", "Заявитель представляет копию платежного документа об оплате внутреннего сбора.", "Добавлен платежный документ."),
            ("", "При подаче заявления прилагается копия согласия на обработку персональных данных.", "Добавлено согласие на обработку данных."),
            ("", "В комплект документов включается копия доверенности представителя.", "Добавлена доверенность представителя."),
            ("", "Заявитель представляет выписку из внутренней учетной системы.", "Добавлена выписка из учетной системы."),
            ("", "В перечень обязательных документов включается копия решения комиссии.", "Добавлено решение комиссии."),
            ("", "К заявлению прилагается подтверждение направления электронного уведомления.", "Добавлено подтверждение уведомления."),
            ("", "В комплект документов включается заявление о согласовании электронного канала связи.", "Добавлено заявление о канале связи."),
        ),
    },
    {
        "semantic_type": "eligibility_change",
        "label": "important",
        "operation_type": "modified",
        "variants": _variant_records(
            ("К процедуре допускаются только сотрудники основного подразделения.", "К процедуре допускаются сотрудники основного и профильного подразделений.", "Расширены условия допуска."),
            ("Заявление принимается при наличии одного документа, подтверждающего полномочия.", "Заявление принимается при наличии двух документов, подтверждающих полномочия.", "Изменены условия допуска по документам."),
            ("Повторное заявление может быть подано через 30 дней.", "Повторное заявление может быть подано через 15 дней.", "Изменен срок повторного допуска."),
            ("Консультация предоставляется только руководителям подразделений.", "Консультация предоставляется руководителям и ответственным специалистам подразделений.", "Изменен круг допущенных лиц."),
            ("Электронная подача доступна только после личной идентификации.", "Электронная подача доступна после личной или усиленной электронной идентификации.", "Изменены условия электронной идентификации."),
            ("Участие в согласовании допускается после внутреннего обучения.", "Участие в согласовании допускается после внутреннего обучения и подтверждения квалификации.", "Уточнены условия допуска к согласованию."),
            ("Прием документов допускается только в будние дни.", "Прием документов допускается в будние дни и в первую субботу месяца.", "Расширены временные условия допуска."),
            ("Повторная подача допустима после письменного уведомления.", "Повторная подача допустима после письменного или электронного уведомления.", "Изменены условия повторной подачи."),
            ("Запрос принимается только от самого заявителя.", "Запрос принимается от заявителя или его уполномоченного представителя.", "Расширены условия представительства."),
            ("К проверке допускаются только заявления в бумажной форме.", "К проверке допускаются заявления в бумажной и электронной форме.", "Расширены форматы допуска."),
        ),
    },
    {
        "semantic_type": "payment_or_fee_change",
        "label": "important",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Размер внутреннего сбора составляет 300 рублей.", "Размер внутреннего сбора составляет 500 рублей.", "Изменен размер внутреннего сбора."),
            ("Оплата производится после завершения проверки.", "Оплата производится до начала проверки.", "Изменен момент оплаты."),
            ("Подтверждение оплаты представляется в бумажном виде.", "Подтверждение оплаты представляется в бумажном или электронном виде.", "Изменен способ подтверждения оплаты."),
            ("Комиссия не взимается при электронной подаче.", "Комиссия взимается в размере 100 рублей при электронной подаче.", "Изменена льгота по оплате."),
            ("Платежный документ хранится в подразделении 10 дней.", "Платежный документ хранится в подразделении 30 дней.", "Изменен срок хранения платежного документа."),
            ("Возврат переплаты производится по письменному заявлению.", "Возврат переплаты производится по письменному или электронному заявлению.", "Изменен порядок возврата переплаты."),
            ("Размер пошлины для повторного обращения составляет 150 рублей.", "Размер пошлины для повторного обращения составляет 250 рублей.", "Изменен размер пошлины для повторного обращения."),
            ("Оплата допускается только через кассу подразделения.", "Оплата допускается через кассу подразделения и личный кабинет портала.", "Изменены каналы оплаты."),
            ("Подтверждение оплаты проверяется вручную.", "Подтверждение оплаты проверяется автоматически через учетную систему.", "Изменен способ проверки оплаты."),
            ("Комиссия начисляется после регистрации обращения.", "Комиссия начисляется до регистрации обращения.", "Изменен момент начисления комиссии."),
        ),
    },
    {
        "semantic_type": "contact_or_channel_change",
        "label": "informational",
        "operation_type": "added",
        "variants": _variant_records(
            ("", "Справочная информация о ходе процедуры доступна по телефону 8-800-100-10-10.", "Добавлен справочный телефон."),
            ("", "Информация о статусе обращения доступна в личном кабинете портала.", "Добавлен справочный электронный канал."),
            ("", "Контактный адрес подразделения размещен на внутреннем портале.", "Добавлен адрес подразделения."),
            ("", "Для консультаций используется дополнительный электронный адрес support@mfc.local.", "Добавлен консультационный адрес."),
            ("", "Информация о режиме работы публикуется на официальной странице подразделения.", "Добавлен канал информирования о режиме работы."),
            ("", "О справочном номере регистрации можно узнать через голосовое меню.", "Добавлен справочный канал через голосовое меню."),
            ("", "Уведомления о технических работах размещаются в разделе новостей портала.", "Добавлен информационный канал о технических работах."),
            ("", "Справочный чат доступен в локальной системе учета обращений.", "Добавлен чатовый справочный канал."),
            ("", "Контактное лицо для консультаций указывается в приложении к регламенту.", "Добавлено контактное лицо."),
            ("", "Адрес кабинета для личного приема публикуется на стенде подразделения.", "Добавлен адрес кабинета приема."),
        ),
    },
    {
        "semantic_type": "clarification_change",
        "label": "informational",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Заявитель получает справочную информацию по запросу.", "Заявитель получает справочную информацию по мотивированному запросу.", "Уточнено справочное условие без правового эффекта."),
            ("Сведения отображаются в учетной системе.", "Сведения отображаются в учетной системе в справочном режиме.", "Уточнен режим отображения сведений."),
            ("Пояснение приводится в приложении.", "Пояснение приводится в приложении для удобства использования.", "Добавлено пояснение без изменения порядка."),
            ("Информация предоставляется в устной форме.", "Информация предоставляется в устной форме при необходимости дополнительного разъяснения.", "Уточнены условия разъяснения."),
            ("Справка содержит сведения о статусе обращения.", "Справка содержит актуальные сведения о статусе обращения.", "Уточнено описание справки."),
            ("Контрольный номер указывается в уведомлении.", "Контрольный номер указывается в уведомлении для последующей справки.", "Уточнено назначение номера."),
            ("Результат отображается в журнале учета.", "Результат отображается в журнале учета в виде справочной отметки.", "Уточнен вид отметки."),
            ("Заявитель вправе ознакомиться с информацией о ходе процедуры.", "Заявитель вправе ознакомиться со справочной информацией о ходе процедуры.", "Уточнен тип информации."),
            ("Сообщение публикуется после обновления данных.", "Сообщение публикуется после обновления данных в информационных целях.", "Уточнено назначение сообщения."),
            ("Пояснение предоставляется сотрудником подразделения.", "Пояснение предоставляется сотрудником подразделения в рамках консультации.", "Уточнен контекст пояснения."),
        ),
    },
    {
        "semantic_type": "reference_change",
        "label": "informational",
        "operation_type": "modified",
        "variants": _variant_records(
            ("В приложении приведена ссылка на регламент подразделения.", "В приложении приведена ссылка на актуальный регламент подразделения.", "Уточнена справочная ссылка на регламент."),
            ("См. пункт 4 приложения.", "См. пункт 4 приложения и статью 3 регламента.", "Расширена справочная ссылка."),
            ("Сведения приведены в разделе 5.", "Сведения приведены в разделе 5 приложения 2.", "Уточнена ссылка на приложение."),
            ("См. внутренний порядок согласования.", "См. внутренний порядок согласования, утвержденный приказом № 14.", "Уточнена ссылка на приказ."),
            ("Форма уведомления указана в приложении.", "Форма уведомления указана в приложении 3 к регламенту.", "Уточнена ссылка на форму."),
            ("Пояснение содержится в методических материалах.", "Пояснение содержится в методических материалах, утвержденных приказом № 22.", "Уточнена ссылка на методические материалы."),
            ("Актуальная версия формы размещена на портале.", "Актуальная версия формы размещена на портале и в приложении 1.", "Уточнена ссылка на форму."),
            ("Перечень контактов приводится в приложении.", "Перечень контактов приводится в приложении 4.", "Уточнена ссылка на приложение с контактами."),
            ("См. пункт 2.4 настоящего регламента.", "См. пункт 2.4 настоящего регламента и приложение 5.", "Расширена ссылка на источник."),
            ("Форма заявления приведена в конце документа.", "Форма заявления приведена в приложении к документу.", "Уточнено местоположение формы."),
        ),
    },
    {
        "semantic_type": "mixed_change",
        "label": "informational",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Заявитель получает справочную информацию после регистрации обращения.", "Заявитель получает справочную информацию после регистрации обращения через портал.", "Добавлен информационный канал без изменения обязанности."),
            ("Пояснение по форме заявления размещается в приложении.", "Пояснение по форме заявления размещается в приложении и на стенде подразделения.", "Добавлено дублирующее пояснение."),
            ("Информация о порядке записи предоставляется устно.", "Информация о порядке записи предоставляется устно и в виде памятки.", "Добавлена памятка без изменения процедуры."),
            ("Сведения о статусе запроса доступны в учетной системе.", "Сведения о статусе запроса доступны в учетной системе и в справочном сообщении.", "Добавлено информационное сообщение."),
            ("Контактные данные публикуются на портале.", "Контактные данные публикуются на портале и в приложении к регламенту.", "Добавлен второй информационный источник."),
            ("Справочная информация обновляется ежемесячно.", "Справочная информация обновляется ежемесячно и при изменении регламента.", "Уточнен цикл обновления справки."),
            ("Сообщение о приеме публикуется на стенде.", "Сообщение о приеме публикуется на стенде и в разделе новостей.", "Добавлен дополнительный информационный канал."),
            ("Пояснение по оплате размещается в памятке.", "Пояснение по оплате размещается в памятке и на странице подразделения.", "Добавлено дублирующее пояснение по оплате."),
            ("Сведения о номере обращения предоставляются сотрудником.", "Сведения о номере обращения предоставляются сотрудником и через автоответчик.", "Добавлен справочный автоответчик."),
            ("Описание процедуры размещается в приложении.", "Описание процедуры размещается в приложении и в краткой памятке для заявителя.", "Добавлена памятка для заявителя."),
        ),
    },
    {
        "semantic_type": "terminology_change",
        "label": "editorial",
        "operation_type": "modified",
        "variants": _variant_records(
            ("Сотрудник осуществляет проверку комплектности документов.", "Сотрудник выполняет проверку комплектности документов.", "Замена глагола без смыслового эффекта."),
            ("Проверка проводится в соответствии с регламентом.", "Проверка проводится согласно регламенту.", "Замена речевой конструкции."),
            ("Заявитель направляет письменное уведомление.", "Заявитель направляет письменное сообщение.", "Терминологическая замена."),
            ("Ответственный специалист осуществляет прием документов.", "Ответственный специалист выполняет прием документов.", "Терминологическая замена без изменения действия."),
            ("Документы подлежат последующей проверке.", "Документы подлежат дальнейшей проверке.", "Замена синонима."),
            ("Сотрудник информирует заявителя о результате.", "Сотрудник уведомляет заявителя о результате.", "Замена слова без изменения обязательства."),
            ("Заявление регистрируется уполномоченным сотрудником.", "Заявление регистрируется ответственным сотрудником.", "Замена обозначения роли."),
            ("Сведения размещаются в локальной системе учета.", "Сведения размещаются в внутренней системе учета.", "Терминологическое уточнение."),
            ("Документ оформляется в письменной форме.", "Документ оформляется письменно.", "Редакционное сокращение формулировки."),
            ("Результат проверки отражается в журнале.", "Результат проверки фиксируется в журнале.", "Редакционная замена глагола."),
        ),
    },
    {
        "semantic_type": "formatting_or_editorial_change",
        "label": "editorial",
        "operation_type": "moved",
        "variants": _variant_records(
            ("Контроль полноты сведений проводится до регистрации обращения.", "Контроль полноты сведений проводится до регистрации обращения.", "Перенос фрагмента без изменения содержания."),
            ("Порядок уведомления заявителя определяется регламентом.", "Порядок уведомления заявителя определяется регламентом.", "Структурный перенос без изменения текста."),
            ("Форма заявления приведена в приложении 1.", "Форма заявления приведена в приложении 1.", "Перенос строки в другой раздел без изменения смысла."),
            ("Справочный номер обращения указывается в уведомлении.", "Справочный номер обращения указывается в уведомлении.", "Редакционный перенос пункта."),
            ("Контактные данные публикуются на стенде подразделения.", "Контактные данные публикуются на стенде подразделения.", "Техническая перестановка без смыслового эффекта."),
            ("Заявитель вправе получить консультацию сотрудника.", "Заявитель вправе получить консультацию сотрудника.", "Перестановка блока без изменения текста."),
            ("Документы проверяются после регистрации обращения.", "Документы проверяются после регистрации обращения.", "Изменена позиция фрагмента без изменения смысла."),
            ("Информация о графике приема публикуется ежемесячно.", "Информация о графике приема публикуется ежемесячно.", "Технический перенос справочного пункта."),
            ("Результат проверки отражается в журнале учета.", "Результат проверки отражается в журнале учета.", "Перенос записи в другой раздел."),
            ("Уточнение сведений выполняется ответственным специалистом.", "Уточнение сведений выполняется ответственным специалистом.", "Редакционный перенос без смыслового эффекта."),
        ),
    },
    {
        "semantic_type": "reference_change",
        "label": "editorial",
        "operation_type": "modified",
        "variants": _variant_records(
            ("См. приложение.", "См. приложение 1.", "Уточнение номера приложения без изменения нормы."),
            ("См. раздел 5.", "См. раздел 5 настоящего документа.", "Редакционное уточнение ссылки."),
            ("Сведения приведены в приложении.", "Сведения приведены в приложении к регламенту.", "Редакционное уточнение источника."),
            ("См. пункт 2.", "См. пункт 2 настоящего раздела.", "Техническое уточнение ссылки."),
            ("См. форму заявления.", "См. форму заявления в приложении.", "Редакционное уточнение местоположения формы."),
            ("См. внутренний порядок.", "См. внутренний порядок подразделения.", "Техническое уточнение ссылки."),
            ("См. регламент.", "См. действующий регламент.", "Редакционное уточнение формулировки."),
            ("См. инструкцию.", "См. инструкцию по работе с обращениями.", "Уточнение названия инструкции."),
            ("См. приложение 2.", "См. приложение 2 к настоящему документу.", "Уточнение контекста приложения."),
            ("См. раздел 3 приложения.", "См. раздел 3 приложения к регламенту.", "Уточнение ссылки на приложение."),
        ),
    },
    {
        "semantic_type": "clarification_change",
        "label": "editorial",
        "operation_type": "modified",
        "variants": _variant_records(
            ("При необходимости предоставляется пояснение.", "При необходимости может быть предоставлено пояснение.", "Редакционное смягчение формулировки."),
            ("Информация предоставляется сотрудником подразделения.", "Информация предоставляется сотрудником соответствующего подразделения.", "Техническое уточнение без изменения смысла."),
            ("Справка оформляется по установленной форме.", "Справка оформляется по утвержденной форме.", "Терминологическое уточнение."),
            ("Сообщение направляется после обработки.", "Сообщение направляется после завершения обработки.", "Уточнение без изменения режима работы."),
            ("Пояснение включается в уведомление.", "Пояснение может включаться в уведомление.", "Редакционное уточнение модальности."),
            ("Контроль проводится сотрудником.", "Контроль проводится уполномоченным сотрудником.", "Техническое уточнение роли."),
            ("Заявление передается на проверку.", "Заявление передается на последующую проверку.", "Редакционное уточнение последовательности без эффекта."),
            ("Сведения хранятся в системе.", "Сведения хранятся в информационной системе.", "Уточнение названия системы."),
            ("Пояснение размещается в приложении.", "Пояснение размещается в соответствующем приложении.", "Техническое уточнение."),
            ("Информация публикуется на странице подразделения.", "Информация публикуется на официальной странице подразделения.", "Редакционное уточнение канала."),
        ),
    },
]


def generate_curated_synthetic_examples() -> list[CorpusExample]:
    items: list[CorpusExample] = []
    for family_index, family in enumerate(CURATED_FAMILIES, start=1):
        for variant_index, variant in enumerate(family["variants"], start=1):
            pair_id = f"synthetic_{family['semantic_type']}_{variant_index:03d}"
            items.append(
                _make_example(
                    example_id=f"{pair_id}:chg_001",
                    source="curated_synthetic",
                    source_file="generated:curated_synthetic",
                    pair_id=pair_id,
                    change_id="chg_001",
                    old_text=variant["old"],
                    new_text=variant["new"],
                    operation_type=family["operation_type"],
                    semantic_type=family["semantic_type"],
                    significance_label=family["label"],
                    is_gold=False,
                    is_synthetic=True,
                    is_weak=False,
                    label_source="curated_synthetic",
                    confidence=0.9,
                    notes=variant["note"],
                )
            )
    return items


def collect_weak_examples(
    trace_path: Path = DEFAULT_REAL_WORLD_TRACE_PATH,
) -> list[CorpusExample]:
    if not trace_path.exists():
        return []
    items: list[CorpusExample] = []
    with trace_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            label = str(row.get("significance_label") or "").strip().lower()
            if label not in SIGNIFICANCE_LABELS:
                continue
            pair_id = str(row.get("pair_id") or f"weak_pair_{index:04d}")
            change_id = str(row.get("change_index") or index)
            items.append(
                _make_example(
                    example_id=f"weak:{pair_id}:{change_id}",
                    source="real_world_weak_trace",
                    source_file=rel_repo_path(trace_path),
                    pair_id=pair_id,
                    change_id=f"chg_{change_id}",
                    old_text=str(row.get("old_preview") or ""),
                    new_text=str(row.get("new_preview") or ""),
                    operation_type=str(row.get("operation_type") or "modified"),
                    semantic_type=str(row.get("semantic_type") or "mixed_change"),
                    significance_label=label,
                    is_gold=False,
                    is_synthetic=False,
                    is_weak=True,
                    label_source="real_world_weak_trace",
                    confidence=0.4,
                    notes=str(row.get("warning") or row.get("explanation") or ""),
                )
            )
    return items


def _coerce_row(row: CorpusExample | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, CorpusExample):
        return asdict(row)
    return dict(row)


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _group_stratified_split(
    strict_df: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    groups = []
    for pair_id, group in strict_df.groupby("pair_id"):
        label_counts = Counter(group["y_significance"].tolist())
        groups.append(
            {
                "pair_id": pair_id,
                "size": len(group),
                "label_counts": label_counts,
                "dominant_label": max(label_counts.items(), key=lambda item: (item[1], item[0]))[0],
            }
        )

    test_target = max(1, round(len(strict_df) * test_size))
    overall = Counter(strict_df["y_significance"].tolist())
    test_counts = Counter()
    selected_test_pairs: set[str] = set()

    groups = sorted(
        groups,
        key=lambda item: (-item["size"], overall[item["dominant_label"]], item["pair_id"]),
    )

    for group in groups:
        if sum(test_counts.values()) >= test_target:
            break
        proposed = test_counts + group["label_counts"]
        current_ratio = {
            label: proposed[label] / max(1, test_target)
            for label in SIGNIFICANCE_LABELS
        }
        global_ratio = {
            label: overall[label] / max(1, len(strict_df))
            for label in SIGNIFICANCE_LABELS
        }
        deviation = sum(abs(current_ratio[label] - global_ratio[label]) for label in SIGNIFICANCE_LABELS)
        if sum(proposed.values()) <= test_target + max(1, group["size"] // 2) or deviation < 0.3:
            selected_test_pairs.add(group["pair_id"])
            test_counts = proposed

    test_df = strict_df[strict_df["pair_id"].isin(selected_test_pairs)].copy()
    train_df = strict_df[~strict_df["pair_id"].isin(selected_test_pairs)].copy()
    metadata = {
        "split_method": "group_aware_stratified_greedy",
        "random_state": random_state,
        "test_target_examples": test_target,
        "selected_test_pairs": sorted(selected_test_pairs),
        "leakage_pair_overlap": sorted(set(train_df["pair_id"]).intersection(set(test_df["pair_id"]))),
    }
    return train_df, test_df, metadata


def _create_validation_split(
    train_df: pd.DataFrame,
    *,
    validation_fraction_of_total: float = 0.1,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(train_df) < 20:
        return train_df, pd.DataFrame(columns=train_df.columns)
    group_rows = (
        train_df.groupby("pair_id")["y_significance"]
        .agg(lambda values: Counter(values).most_common(1)[0][0])
        .reset_index()
        .rename(columns={"y_significance": "group_label"})
    )
    group_pairs = group_rows["pair_id"].tolist()
    group_labels = group_rows["group_label"].tolist()
    val_size = max(1, round((len(train_df) / max(len(train_df), 1)) * validation_fraction_of_total * len(group_pairs)))
    val_size = min(max(val_size, 1), max(len(group_pairs) - 1, 1))
    try:
        train_pairs, val_pairs = train_test_split(
            group_pairs,
            test_size=val_size,
            random_state=random_state,
            stratify=group_labels if len(set(group_labels)) > 1 else None,
        )
    except ValueError:
        train_pairs, val_pairs = train_test_split(
            group_pairs,
            test_size=val_size,
            random_state=random_state,
            stratify=None,
        )
    final_train = train_df[train_df["pair_id"].isin(train_pairs)].copy()
    validation = train_df[train_df["pair_id"].isin(val_pairs)].copy()
    return final_train, validation


def _distribution_rows(df: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    counts = df[column].value_counts().sort_index()
    return [{"column": column, "label": index, "count": int(value)} for index, value in counts.items()]


def _save_distribution_plot(
    series: pd.Series,
    *,
    title: str,
    output_path: Path,
    xlabel: str,
) -> None:
    if not MATPLOTLIB_AVAILABLE:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    values = series.sort_values(ascending=False)
    ax.bar(range(len(values)), values.values, color="#2563eb")
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(values.index, rotation=30, ha="right")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _save_histogram(values: pd.Series, *, title: str, output_path: Path, xlabel: str) -> None:
    if not MATPLOTLIB_AVAILABLE:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values.values, bins=12, color="#0f766e", edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _build_dataset_quality_report(
    *,
    profile: dict[str, Any],
    output_dir: Path,
) -> None:
    report_path = output_dir / "dataset_quality_report.md"
    lines = [
        "# Dataset quality report",
        "",
        "## Назначение",
        "",
        "Корпус предназначен для supervised ML-экспериментов по классификации значимости изменений и не заменяет production rule-based significance layer.",
        "",
        "## Источники данных",
        "",
    ]
    for key, value in profile["sources"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Размер корпуса",
            "",
            f"- Всего examples: {profile['total_examples']}",
            f"- Strict supervised examples: {profile['strict_examples']}",
            f"- Weak examples: {profile['weak_examples']}",
            f"- Train size: {profile['split']['train_size']}",
            f"- Test size: {profile['split']['test_size']}",
            f"- Validation size: {profile['split']['validation_size']}",
            "",
            "## Распределение labels",
            "",
        ]
    )
    for label, count in profile["label_distribution"].items():
        lines.append(f"- {label}: {count}")
    lines.extend(
        [
            "",
            "## Распределение semantic types",
            "",
        ]
    )
    for label, count in profile["semantic_type_distribution"].items():
        lines.append(f"- {label}: {count}")
    lines.extend(
        [
            "",
            "## Распределение operation types",
            "",
        ]
    )
    for label, count in profile["operation_type_distribution"].items():
        lines.append(f"- {label}: {count}")
    lines.extend(
        [
            "",
            "## Средние длины текстов",
            "",
            f"- Средняя длина old_text: {profile['text_lengths']['old_mean']}",
            f"- Средняя длина new_text: {profile['text_lengths']['new_mean']}",
            f"- Средняя длина combined_text: {profile['text_lengths']['combined_mean']}",
            "",
            "## Доли источников",
            "",
            f"- Gold: {profile['source_proportions']['gold']}",
            f"- Synthetic: {profile['source_proportions']['synthetic']}",
            f"- Weak: {profile['source_proportions']['weak']}",
            "",
            "## Leakage checks",
            "",
            f"- Pair overlap train/test: {profile['split']['leakage_pair_overlap']}",
            "",
            "## Ограничения",
            "",
            "- Curated synthetic examples являются controlled supervised corpus и не являются real-world legal benchmark.",
            "- Weak real-world examples вынесены в отдельный inference layer и не используются в strict train/test split.",
            "- Annotation Studio examples подключаются как optional high-priority gold source и зависят от наличия локальной базы или export artifacts.",
            "",
            "## Пригодность для scikit-learn",
            "",
            "Корпус содержит текстовые поля, бинарные lexical features, numeric length features и устойчивые target columns (`y_significance`, `y_high_priority`, `y_semantic_type`), что делает его пригодным для классических supervised ML baseline-экспериментов.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_supervised_ml_corpus(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    significance_results_path: Path = DEFAULT_SIGNIFICANCE_RESULTS_PATH,
    evaluation_corpus_dir: Path = DEFAULT_EVALUATION_CORPUS_DIR,
    real_world_trace_path: Path = DEFAULT_REAL_WORLD_TRACE_PATH,
    target_per_label: int = 40,
    random_state: int = 42,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    warnings: list[str] = []

    gold_examples = _dedupe_examples(
        collect_gold_examples_from_significance_results(significance_results_path)
        + collect_gold_examples_from_evaluation_corpus(evaluation_corpus_dir)
    )
    annotation_examples_db, db_warnings = collect_annotation_examples_from_db()
    annotation_examples_export, export_warnings = collect_annotation_examples_from_exports()
    warnings.extend(db_warnings)
    warnings.extend(export_warnings)
    annotation_examples = _dedupe_examples(annotation_examples_db + annotation_examples_export)

    curated_examples = generate_curated_synthetic_examples()
    if target_per_label > 0:
        counts = Counter(example.significance_label for example in curated_examples)
        if any(counts[label] < target_per_label for label in SIGNIFICANCE_LABELS):
            warnings.append("Curated synthetic generator produced fewer examples than requested target_per_label for at least one class.")

    weak_examples = collect_weak_examples(real_world_trace_path)
    full_examples = _dedupe_examples(gold_examples + annotation_examples + curated_examples + weak_examples)

    full_df = pd.DataFrame([asdict(item) for item in full_examples])
    strict_df = full_df[full_df["is_weak"] == 0].copy()
    weak_df = full_df[full_df["is_weak"] == 1].copy()

    train_df, test_df, split_info = _group_stratified_split(
        strict_df,
        test_size=0.2,
        random_state=random_state,
    )
    train_df, validation_df = _create_validation_split(
        train_df,
        validation_fraction_of_total=0.1,
        random_state=random_state,
    )

    split_info.update(
        {
            "train_size": int(len(train_df)),
            "test_size": int(len(test_df)),
            "validation_size": int(len(validation_df)),
            "train_label_distribution": train_df["y_significance"].value_counts().sort_index().to_dict(),
            "test_label_distribution": test_df["y_significance"].value_counts().sort_index().to_dict(),
            "validation_label_distribution": validation_df["y_significance"].value_counts().sort_index().to_dict(),
        }
    )

    full_dataset_path = output_dir / "full_dataset.csv"
    train_path = output_dir / "train.csv"
    test_path = output_dir / "test.csv"
    validation_path = output_dir / "validation.csv"
    weak_path = output_dir / "weak_inference_dataset.csv"
    split_metadata_path = output_dir / "split_metadata.json"
    label_distribution_path = output_dir / "label_distribution.csv"
    feature_schema_path = output_dir / "feature_schema.json"
    dataset_profile_path = output_dir / "dataset_profile.json"

    full_df.to_csv(full_dataset_path, index=False, encoding="utf-8")
    train_df.to_csv(train_path, index=False, encoding="utf-8")
    test_df.to_csv(test_path, index=False, encoding="utf-8")
    validation_df.to_csv(validation_path, index=False, encoding="utf-8")
    weak_df.to_csv(weak_path, index=False, encoding="utf-8")
    _write_json(split_metadata_path, split_info)

    label_distribution_rows = []
    label_distribution_rows.extend(_distribution_rows(full_df, "y_significance"))
    label_distribution_rows.extend(_distribution_rows(full_df, "y_semantic_type"))
    label_distribution_rows.extend(_distribution_rows(full_df, "operation_type"))
    _write_csv(
        label_distribution_path,
        label_distribution_rows,
        headers=["column", "label", "count"],
    )

    feature_schema = {
        "text_columns": ["old_text", "new_text", "combined_text"],
        "categorical_columns": ["operation_type", "semantic_type", "significance_label", "text_complexity_bucket"],
        "binary_feature_columns": [
            "has_number",
            "has_date",
            "has_deadline_terms",
            "has_obligation_terms",
            "has_refusal_terms",
            "has_document_terms",
            "has_responsibility_terms",
            "has_procedure_terms",
            "has_payment_terms",
            "has_editorial_terms",
            "has_legal_reference",
            "has_modal_verbs",
        ],
        "numeric_feature_columns": [
            "old_length",
            "new_length",
            "length_delta",
            "relative_length_delta",
            "rule_based_confidence",
        ],
        "target_columns": {
            "y_significance": list(SIGNIFICANCE_LABELS),
            "y_high_priority": [0, 1],
            "y_semantic_type": sorted(full_df["y_semantic_type"].dropna().unique().tolist()),
        },
    }
    _write_json(feature_schema_path, feature_schema)

    label_series = full_df["y_significance"].value_counts().sort_index()
    semantic_series = full_df["y_semantic_type"].value_counts().sort_values(ascending=False)
    operation_series = full_df["operation_type"].value_counts().sort_values(ascending=False)
    _save_distribution_plot(
        label_series,
        title="Significance label distribution",
        output_path=figures_dir / "label_distribution.png",
        xlabel="Label",
    )
    _save_distribution_plot(
        semantic_series,
        title="Semantic type distribution",
        output_path=figures_dir / "semantic_type_distribution.png",
        xlabel="Semantic type",
    )
    _save_distribution_plot(
        operation_series,
        title="Operation type distribution",
        output_path=figures_dir / "operation_type_distribution.png",
        xlabel="Operation type",
    )
    _save_histogram(
        full_df["new_length"],
        title="New text length distribution",
        output_path=figures_dir / "text_length_distribution.png",
        xlabel="Characters in new_text",
    )
    if MATPLOTLIB_AVAILABLE:
        split_counts = pd.Series(
            {
                "train": len(train_df),
                "validation": len(validation_df),
                "test": len(test_df),
            }
        )
        _save_distribution_plot(
            split_counts,
            title="Train / validation / test distribution",
            output_path=figures_dir / "train_test_distribution.png",
            xlabel="Split",
        )

    profile = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "total_examples": int(len(full_df)),
        "strict_examples": int(len(strict_df)),
        "weak_examples": int(len(weak_df)),
        "sources": {
            "significance_results": int(len(collect_gold_examples_from_significance_results(significance_results_path))),
            "evaluation_corpus": int(len(collect_gold_examples_from_evaluation_corpus(evaluation_corpus_dir))),
            "annotation_examples": int(len(annotation_examples)),
            "curated_synthetic": int(len(curated_examples)),
            "real_world_weak": int(len(weak_examples)),
        },
        "label_distribution": full_df["y_significance"].value_counts().sort_index().to_dict(),
        "semantic_type_distribution": full_df["y_semantic_type"].value_counts().sort_values(ascending=False).to_dict(),
        "operation_type_distribution": full_df["operation_type"].value_counts().sort_values(ascending=False).to_dict(),
        "text_lengths": {
            "old_mean": round(float(full_df["old_length"].mean()), 2),
            "new_mean": round(float(full_df["new_length"].mean()), 2),
            "combined_mean": round(float(full_df["combined_text"].str.len().mean()), 2),
        },
        "source_proportions": {
            "gold": round(float(full_df["is_gold"].mean()), 4),
            "synthetic": round(float(full_df["is_synthetic"].mean()), 4),
            "weak": round(float(full_df["is_weak"].mean()), 4),
        },
        "split": split_info,
        "warnings": warnings,
        "artifacts": {
            "full_dataset": rel_repo_path(full_dataset_path),
            "train": rel_repo_path(train_path),
            "validation": rel_repo_path(validation_path),
            "test": rel_repo_path(test_path),
            "weak_inference_dataset": rel_repo_path(weak_path),
            "split_metadata": rel_repo_path(split_metadata_path),
            "dataset_quality_report": rel_repo_path(output_dir / "dataset_quality_report.md"),
            "figures_dir": rel_repo_path(figures_dir),
        },
    }
    _write_json(dataset_profile_path, profile)
    _build_dataset_quality_report(profile=profile, output_dir=output_dir)
    return profile


def _build_numeric_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    numeric_columns = [
        "old_length",
        "new_length",
        "length_delta",
        "relative_length_delta",
        "has_number",
        "has_date",
        "has_deadline_terms",
        "has_obligation_terms",
        "has_refusal_terms",
        "has_document_terms",
        "has_responsibility_terms",
        "has_procedure_terms",
        "has_payment_terms",
        "has_editorial_terms",
        "has_legal_reference",
        "has_modal_verbs",
        "high_priority_label",
        "rule_based_confidence",
        "rule_based_requires_manual_review",
    ]
    return df[numeric_columns].fillna(0.0).astype(float), numeric_columns


def train_baseline_ml_models(
    *,
    corpus_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    train_path = corpus_dir / "train.csv"
    test_path = corpus_dir / "test.csv"
    if not train_path.exists() or not test_path.exists():
        raise FileNotFoundError("train.csv and test.csv are required before baseline training.")

    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True)
    X_train_text = tfidf.fit_transform(train_df["combined_text"].fillna(""))
    X_test_text = tfidf.transform(test_df["combined_text"].fillna(""))
    train_numeric, numeric_columns = _build_numeric_matrix(train_df)
    test_numeric, _ = _build_numeric_matrix(test_df)
    feature_names = [f"tfidf:{name}" for name in tfidf.get_feature_names_out()] + [
        f"meta:{name}" for name in numeric_columns
    ]
    X_train = np.hstack([X_train_text.toarray(), train_numeric.to_numpy(dtype=float)])
    X_test = np.hstack([X_test_text.toarray(), test_numeric.to_numpy(dtype=float)])
    y_train = train_df["y_significance"].astype(str)
    y_test = test_df["y_significance"].astype(str)

    models = {
        "LogisticRegression": LogisticRegression(max_iter=2500, class_weight="balanced", random_state=42),
        "LinearSVC": LinearSVC(class_weight="balanced", random_state=42, max_iter=50000),
        "ComplementNB": ComplementNB(),
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
        ),
    }

    results_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    label_order = sorted(set(y_train.tolist() + y_test.tolist()))
    for model_name, model in models.items():
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        report = classification_report(
            y_test,
            predictions,
            labels=label_order,
            output_dict=True,
            zero_division=0,
        )
        results_rows.append(
            {
                "model": model_name,
                "accuracy": round(float(report["accuracy"]), 4),
                "macro_precision": round(float(report["macro avg"]["precision"]), 4),
                "macro_recall": round(float(report["macro avg"]["recall"]), 4),
                "macro_f1": round(float(report["macro avg"]["f1-score"]), 4),
                "weighted_f1": round(float(report["weighted avg"]["f1-score"]), 4),
                "support": int(report["macro avg"]["support"]),
            }
        )
        matrix = confusion_matrix(y_test, predictions, labels=label_order)
        for true_index, true_label in enumerate(label_order):
            for pred_index, predicted_label in enumerate(label_order):
                confusion_rows.append(
                    {
                        "model": model_name,
                        "true_label": true_label,
                        "predicted_label": predicted_label,
                        "count": int(matrix[true_index][pred_index]),
                    }
                )

        if hasattr(model, "coef_"):
            coef_matrix = model.coef_
            model_labels = list(model.classes_)
            for class_index, class_label in enumerate(model_labels):
                class_coefs = coef_matrix[class_index]
                top_indices = np.argsort(class_coefs)[-10:][::-1]
                for rank, feature_index in enumerate(top_indices, start=1):
                    feature_rows.append(
                        {
                            "model": model_name,
                            "class_label": class_label,
                            "rank": rank,
                            "feature_name": feature_names[int(feature_index)],
                            "importance": round(float(class_coefs[int(feature_index)]), 6),
                        }
                    )
        elif hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            top_indices = np.argsort(importances)[-20:][::-1]
            for rank, feature_index in enumerate(top_indices, start=1):
                feature_rows.append(
                    {
                        "model": model_name,
                        "class_label": "global",
                        "rank": rank,
                        "feature_name": feature_names[int(feature_index)],
                        "importance": round(float(importances[int(feature_index)]), 6),
                    }
                )

    results_path = corpus_dir / "baseline_model_results.csv"
    confusion_path = corpus_dir / "baseline_confusion_matrix.csv"
    feature_path = corpus_dir / "baseline_feature_importance.csv"
    pd.DataFrame(results_rows).to_csv(results_path, index=False, encoding="utf-8")
    pd.DataFrame(confusion_rows).to_csv(confusion_path, index=False, encoding="utf-8")
    pd.DataFrame(feature_rows).to_csv(feature_path, index=False, encoding="utf-8")

    return {
        "train_size": int(len(train_df)),
        "test_size": int(len(test_df)),
        "results_rows": results_rows,
        "output_files": {
            "results": rel_repo_path(results_path),
            "confusion_matrix": rel_repo_path(confusion_path),
            "feature_importance": rel_repo_path(feature_path),
        },
    }
