from __future__ import annotations

import csv
import json
import mimetypes
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FINAL_DIR = PROJECT_ROOT / "experiments" / "final"
FINAL_VISUALS_DIR = PROJECT_ROOT / "experiments" / "final_visuals"
FINAL_FIGURES_DIR = FINAL_VISUALS_DIR / "figures"
FINAL_TABLES_DIR = FINAL_VISUALS_DIR / "tables"
REAL_WORLD_DIR = PROJECT_ROOT / "experiments" / "real_world"
SIGNIFICANCE_ML_DIR = PROJECT_ROOT / "experiments" / "significance_ml"
ML_CORPUS_DIR = PROJECT_ROOT / "experiments" / "ml_corpus"
DOCS_EXPERIMENTS_DIR = PROJECT_ROOT / "docs" / "experiments"

ARTIFACT_ROOTS = (
    FINAL_DIR,
    FINAL_FIGURES_DIR,
    FINAL_TABLES_DIR,
    REAL_WORLD_DIR,
    SIGNIFICANCE_ML_DIR,
    ML_CORPUS_DIR,
    DOCS_EXPERIMENTS_DIR,
)

METHOD_FORMULA = "M = <E, N, S, C, P, G, R>"

PIPELINE_STAGES = (
    {
        "slug": "chunking",
        "title": "Structural chunking",
        "stage_codes": {"S"},
        "artifact_paths": [
            "docs/experiments/chunking-evaluation.md",
            "experiments/chunking/chunking_summary.json",
            "experiments/chunking/chunking_results.csv",
        ],
    },
    {
        "slug": "diff",
        "title": "Version comparison / diff",
        "stage_codes": {"C"},
        "artifact_paths": [
            "docs/experiments/diff-evaluation.md",
            "experiments/diff/diff_summary.json",
            "experiments/diff/diff_results.csv",
        ],
    },
    {
        "slug": "significance",
        "title": "Significance classification",
        "stage_codes": {"P"},
        "artifact_paths": [
            "docs/experiments/significance-evaluation.md",
            "experiments/significance/significance_summary.json",
            "experiments/significance/significance_results.csv",
        ],
    },
    {
        "slug": "summary",
        "title": "Summary generation",
        "stage_codes": {"G-summary"},
        "artifact_paths": [
            "docs/experiments/summary-evaluation.md",
            "experiments/summary/summary_evaluation_summary.json",
            "experiments/summary/summary_results.csv",
        ],
    },
    {
        "slug": "quiz",
        "title": "Quiz generation",
        "stage_codes": {"G-quiz"},
        "artifact_paths": [
            "docs/experiments/quiz-generation-evaluation.md",
            "experiments/quiz/quiz_evaluation_summary.json",
            "experiments/quiz/quiz_results.csv",
        ],
    },
    {
        "slug": "end-to-end",
        "title": "End-to-end pipeline",
        "stage_codes": {"S", "C", "P", "G-summary", "G-quiz"},
        "artifact_paths": [
            "docs/experiments/final-method-evaluation.md",
            "experiments/final/end_to_end_summary.json",
            "experiments/final/pipeline_stage_summary.csv",
            "experiments/final/error_propagation.csv",
        ],
    },
)


def format_label(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().title()


def humanize_stem(stem: str) -> str:
    return format_label(stem)


def rel_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "available": False,
            "path": rel_repo_path(path),
            "data": None,
            "warning": "artifact missing / not available",
        }
    try:
        return {
            "available": True,
            "path": rel_repo_path(path),
            "data": json.loads(path.read_text(encoding="utf-8")),
            "warning": None,
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "path": rel_repo_path(path),
            "data": None,
            "warning": f"artifact read error: {exc}",
        }


def safe_read_text_preview(path: Path, max_chars: int = 1200) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "available": False,
            "path": rel_repo_path(path),
            "preview": "",
            "warning": "artifact missing / not available",
        }
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "available": False,
            "path": rel_repo_path(path),
            "preview": "",
            "warning": f"artifact read error: {exc}",
        }
    preview = text[:max_chars]
    if len(text) > max_chars:
        preview = preview.rstrip() + "\n..."
    return {
        "available": True,
        "path": rel_repo_path(path),
        "preview": preview,
        "warning": None,
    }


def safe_read_csv_preview(path: Path, max_rows: int = 10) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "available": False,
            "path": rel_repo_path(path),
            "headers": [],
            "rows": [],
            "warning": "artifact missing / not available",
        }
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, [])
            rows: list[list[str]] = []
            for index, row in enumerate(reader):
                if index >= max_rows:
                    break
                rows.append(row)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return {
            "available": False,
            "path": rel_repo_path(path),
            "headers": [],
            "rows": [],
            "warning": f"artifact read error: {exc}",
        }
    return {
        "available": True,
        "path": rel_repo_path(path),
        "headers": headers,
        "rows": rows,
        "warning": None,
    }


def flatten_metrics(payload: Any, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_metrics(value, next_prefix))
        return rows
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            for index, item in enumerate(payload):
                next_prefix = f"{prefix}[{index}]"
                rows.extend(flatten_metrics(item, next_prefix))
        else:
            rows.append({"key": prefix, "value": ", ".join(map(str, payload))})
        return rows
    rows.append({"key": prefix, "value": payload})
    return rows


def _artifact_status(found: int, total: int) -> str:
    if total == 0 or found == 0:
        return "missing"
    if found == total:
        return "available"
    return "partially available"


def _build_artifact_ref(path_str: str) -> dict[str, Any]:
    path = PROJECT_ROOT / Path(path_str)
    return {
        "path": path_str.replace("\\", "/"),
        "exists": path.exists(),
    }


def _pick_stage_metrics(
    metrics: list[dict[str, Any]], stage_codes: set[str], limit: int = 4
) -> list[dict[str, Any]]:
    picked = [row for row in metrics if str(row.get("stage")) in stage_codes]
    return picked[:limit]


def collect_final_metrics() -> dict[str, Any]:
    json_payload = safe_read_json(FINAL_DIR / "final_metrics_summary.json")
    csv_preview = safe_read_csv_preview(FINAL_DIR / "final_metrics_summary.csv")

    structured_metrics = []
    artifact_audit = []
    flattened = []
    if json_payload["available"] and isinstance(json_payload["data"], dict):
        structured_metrics = list(json_payload["data"].get("metrics", []))
        artifact_audit = list(json_payload["data"].get("artifact_audit", []))
        flattened = flatten_metrics(json_payload["data"])

    return {
        "json": json_payload,
        "csv_preview": csv_preview,
        "metrics": structured_metrics,
        "artifact_audit": artifact_audit,
        "flattened": flattened,
        "status": "available" if json_payload["available"] or csv_preview["available"] else "missing",
    }


def collect_figure_artifacts() -> dict[str, Any]:
    if not FINAL_FIGURES_DIR.exists():
        return {
            "status": "missing",
            "items": [],
            "warning": "artifact missing / not available",
        }

    items = []
    for path in sorted(FINAL_FIGURES_DIR.glob("*.png")):
        items.append(
            {
                "title": humanize_stem(path.stem),
                "path": rel_repo_path(path),
                "content_type": mimetypes.guess_type(path.name)[0] or "image/png",
            }
        )
    return {
        "status": "available" if items else "missing",
        "items": items,
        "warning": None if items else "artifact missing / not available",
    }


def collect_table_artifacts() -> dict[str, Any]:
    if not FINAL_TABLES_DIR.exists():
        return {
            "status": "missing",
            "items": [],
            "warning": "artifact missing / not available",
        }

    items = []
    for path in sorted(FINAL_TABLES_DIR.iterdir()):
        if path.suffix.lower() not in {".csv", ".md"}:
            continue
        item = {
            "title": humanize_stem(path.stem),
            "path": rel_repo_path(path),
            "kind": path.suffix.lower().lstrip("."),
        }
        if path.suffix.lower() == ".csv":
            item["preview"] = safe_read_csv_preview(path, max_rows=5)
        else:
            item["preview"] = safe_read_text_preview(path, max_chars=700)
        items.append(item)
    return {
        "status": "available" if items else "missing",
        "items": items,
        "warning": None if items else "artifact missing / not available",
    }


def collect_documentation_artifacts() -> dict[str, Any]:
    if not DOCS_EXPERIMENTS_DIR.exists():
        return {
            "status": "missing",
            "items": [],
            "warning": "artifact missing / not available",
        }
    items = []
    for path in sorted(DOCS_EXPERIMENTS_DIR.glob("*.md")):
        items.append(
            {
                "title": humanize_stem(path.stem),
                "path": rel_repo_path(path),
                "preview": safe_read_text_preview(path, max_chars=500),
            }
        )
    return {
        "status": "available" if items else "missing",
        "items": items,
        "warning": None if items else "artifact missing / not available",
    }


def collect_pipeline_diagnostics() -> dict[str, Any]:
    summary = safe_read_json(FINAL_DIR / "end_to_end_summary.json")
    trace = safe_read_csv_preview(FINAL_DIR / "end_to_end_trace.csv", max_rows=8)
    error_propagation = safe_read_csv_preview(
        FINAL_DIR / "error_propagation.csv", max_rows=8
    )
    stage_summary = safe_read_csv_preview(
        FINAL_DIR / "pipeline_stage_summary.csv", max_rows=8
    )

    available_count = sum(
        1
        for item in (summary, trace, error_propagation, stage_summary)
        if item["available"]
    )
    return {
        "status": _artifact_status(available_count, 4),
        "summary": summary,
        "trace": trace,
        "error_propagation": error_propagation,
        "stage_summary": stage_summary,
    }


def collect_real_world_regression() -> dict[str, Any]:
    summary = safe_read_json(REAL_WORLD_DIR / "real_world_summary.json")
    pair_results = safe_read_csv_preview(
        REAL_WORLD_DIR / "real_world_pair_results.csv", max_rows=8
    )
    stage_summary = safe_read_csv_preview(
        REAL_WORLD_DIR / "real_world_stage_summary.csv", max_rows=8
    )
    trace = safe_read_csv_preview(REAL_WORLD_DIR / "real_world_trace.csv", max_rows=8)

    available_count = sum(
        1
        for item in (summary, pair_results, stage_summary, trace)
        if item["available"]
    )
    summary_data = summary["data"] if summary["available"] and isinstance(summary["data"], dict) else {}
    metrics = summary_data.get("metrics", {}) if isinstance(summary_data, dict) else {}
    return {
        "status": _artifact_status(available_count, 4),
        "summary": summary,
        "pair_results": pair_results,
        "stage_summary": stage_summary,
        "trace": trace,
        "metrics": metrics if isinstance(metrics, dict) else {},
        "limitations": summary_data.get("limitations", [])
        if isinstance(summary_data, dict)
        else [],
    }


def collect_significance_ml_experiment() -> dict[str, Any]:
    summary = safe_read_json(SIGNIFICANCE_ML_DIR / "significance_ml_summary.json")
    predictions = safe_read_csv_preview(
        SIGNIFICANCE_ML_DIR / "significance_ml_predictions.csv",
        max_rows=8,
    )
    confusion = safe_read_csv_preview(
        SIGNIFICANCE_ML_DIR / "significance_ml_confusion_matrix.csv",
        max_rows=8,
    )
    feature_report = safe_read_csv_preview(
        SIGNIFICANCE_ML_DIR / "significance_ml_feature_report.csv",
        max_rows=8,
    )
    error_examples = safe_read_csv_preview(
        SIGNIFICANCE_ML_DIR / "significance_ml_error_examples.csv",
        max_rows=8,
    )

    available_count = sum(
        1
        for item in (summary, predictions, confusion, feature_report, error_examples)
        if item["available"]
    )
    summary_data = summary["data"] if summary["available"] and isinstance(summary["data"], dict) else {}
    return {
        "status": _artifact_status(available_count, 5),
        "summary": summary,
        "predictions": predictions,
        "confusion": confusion,
        "feature_report": feature_report,
        "error_examples": error_examples,
        "models_evaluated": summary_data.get("models_evaluated", [])
        if isinstance(summary_data, dict)
        else [],
        "label_distribution": summary_data.get("label_distribution", {})
        if isinstance(summary_data, dict)
        else {},
        "rule_metrics": summary_data.get("rule_based_metrics", {})
        if isinstance(summary_data, dict)
        else {},
        "ml_metrics": summary_data.get("ml_metrics", {})
        if isinstance(summary_data, dict)
        else {},
        "hybrid_metrics": summary_data.get("hybrid_metrics", {})
        if isinstance(summary_data, dict)
        else {},
        "binary_metrics": summary_data.get("binary_high_priority_metrics", {})
        if isinstance(summary_data, dict)
        else {},
        "limitations": summary_data.get("limitations", [])
        if isinstance(summary_data, dict)
        else [],
        "disagreement_count": summary_data.get("disagreement_count", 0)
        if isinstance(summary_data, dict)
        else 0,
        "total_examples": summary_data.get("total_examples", 0)
        if isinstance(summary_data, dict)
        else 0,
    }


def collect_supervised_ml_corpus() -> dict[str, Any]:
    profile = safe_read_json(ML_CORPUS_DIR / "dataset_profile.json")
    split = safe_read_json(ML_CORPUS_DIR / "split_metadata.json")
    feature_schema = safe_read_json(ML_CORPUS_DIR / "feature_schema.json")
    full_dataset = safe_read_csv_preview(ML_CORPUS_DIR / "full_dataset.csv", max_rows=8)
    train = safe_read_csv_preview(ML_CORPUS_DIR / "train.csv", max_rows=8)
    test = safe_read_csv_preview(ML_CORPUS_DIR / "test.csv", max_rows=8)
    weak = safe_read_csv_preview(
        ML_CORPUS_DIR / "weak_inference_dataset.csv",
        max_rows=8,
    )
    label_distribution = safe_read_csv_preview(
        ML_CORPUS_DIR / "label_distribution.csv",
        max_rows=16,
    )
    quality_report = safe_read_text_preview(
        ML_CORPUS_DIR / "dataset_quality_report.md",
        max_chars=900,
    )

    figures_dir = ML_CORPUS_DIR / "figures"
    figure_items = []
    if figures_dir.exists():
        for path in sorted(figures_dir.glob("*.png")):
            figure_items.append(
                {
                    "title": humanize_stem(path.stem),
                    "path": rel_repo_path(path),
                }
            )

    available_count = sum(
        1
        for item in (
            profile,
            split,
            feature_schema,
            full_dataset,
            train,
            test,
            weak,
            label_distribution,
            quality_report,
        )
        if item["available"]
    )
    profile_data = profile["data"] if profile["available"] and isinstance(profile["data"], dict) else {}
    split_data = split["data"] if split["available"] and isinstance(split["data"], dict) else {}
    return {
        "status": _artifact_status(available_count, 9),
        "profile": profile,
        "split": split,
        "feature_schema": feature_schema,
        "full_dataset": full_dataset,
        "train": train,
        "test": test,
        "weak": weak,
        "label_distribution_csv": label_distribution,
        "quality_report": quality_report,
        "figures": {
            "status": "available" if figure_items else "missing",
            "items": figure_items,
            "warning": None if figure_items else "artifact missing / not available",
        },
        "total_examples": profile_data.get("total_examples", 0) if isinstance(profile_data, dict) else 0,
        "strict_examples": profile_data.get("strict_examples", 0) if isinstance(profile_data, dict) else 0,
        "weak_examples": profile_data.get("weak_examples", 0) if isinstance(profile_data, dict) else 0,
        "label_distribution": profile_data.get("label_distribution", {}) if isinstance(profile_data, dict) else {},
        "semantic_type_distribution": profile_data.get("semantic_type_distribution", {})
        if isinstance(profile_data, dict)
        else {},
        "source_proportions": profile_data.get("source_proportions", {}) if isinstance(profile_data, dict) else {},
        "train_size": split_data.get("train_size", 0) if isinstance(split_data, dict) else 0,
        "test_size": split_data.get("test_size", 0) if isinstance(split_data, dict) else 0,
        "validation_size": split_data.get("validation_size", 0) if isinstance(split_data, dict) else 0,
        "split_method": split_data.get("split_method", "") if isinstance(split_data, dict) else "",
        "balanced_split_passed": split_data.get("balanced_split_passed", profile_data.get("balanced_split_passed", False))
        if isinstance(split_data, dict)
        else profile_data.get("balanced_split_passed", False),
        "train_label_distribution": split_data.get("train_label_distribution", {}) if isinstance(split_data, dict) else {},
        "validation_label_distribution": split_data.get("validation_label_distribution", {})
        if isinstance(split_data, dict)
        else {},
        "test_label_distribution": split_data.get("test_label_distribution", {}) if isinstance(split_data, dict) else {},
        "class_coverage_passed": split_data.get("class_coverage_passed", False) if isinstance(split_data, dict) else False,
        "class_coverage_errors": split_data.get("class_coverage_errors", []) if isinstance(split_data, dict) else [],
        "leakage_warnings": split_data.get("warnings", []) if isinstance(split_data, dict) else [],
        "leakage_pair_overlap_train_test": split_data.get("leakage_pair_overlap_train_test", [])
        if isinstance(split_data, dict)
        else [],
        "warnings": profile_data.get("warnings", []) if isinstance(profile_data, dict) else [],
    }


def collect_stage_cards(
    final_metrics: dict[str, Any], diagnostics: dict[str, Any]
) -> list[dict[str, Any]]:
    metrics = list(final_metrics.get("metrics", []))
    cards = []
    for definition in PIPELINE_STAGES:
        artifact_refs = [_build_artifact_ref(path) for path in definition["artifact_paths"]]
        found = sum(1 for item in artifact_refs if item["exists"])
        card = {
            "slug": definition["slug"],
            "title": definition["title"],
            "status": _artifact_status(found, len(artifact_refs)),
            "artifacts": artifact_refs,
            "metrics": _pick_stage_metrics(metrics, definition["stage_codes"]),
        }
        if definition["slug"] == "end-to-end" and not card["metrics"]:
            summary_data = diagnostics["summary"].get("data") if diagnostics["summary"]["available"] else {}
            if isinstance(summary_data, dict):
                card["metrics"] = [
                    {"metric": key, "value": value, "interpretation": ""}
                    for key, value in list(summary_data.items())[:4]
                ]
        cards.append(card)
    return cards


def collect_artifact_inventory(
    final_metrics: dict[str, Any],
    figures: dict[str, Any],
    tables: dict[str, Any],
    documentation: dict[str, Any],
    diagnostics: dict[str, Any],
    real_world: dict[str, Any],
    significance_ml: dict[str, Any],
    supervised_ml_corpus: dict[str, Any],
) -> list[dict[str, Any]]:
    inventory = [
        {"group": "Final metrics JSON", "status": "available" if final_metrics["json"]["available"] else "missing", "path": final_metrics["json"]["path"]},
        {"group": "Final metrics CSV", "status": "available" if final_metrics["csv_preview"]["available"] else "missing", "path": final_metrics["csv_preview"]["path"]},
        {"group": "Figures", "status": figures["status"], "path": rel_repo_path(FINAL_FIGURES_DIR)},
        {"group": "Tables", "status": tables["status"], "path": rel_repo_path(FINAL_TABLES_DIR)},
        {"group": "Real-world regression", "status": real_world["status"], "path": rel_repo_path(REAL_WORLD_DIR)},
        {"group": "Significance ML experiment", "status": significance_ml["status"], "path": rel_repo_path(SIGNIFICANCE_ML_DIR)},
        {"group": "Supervised ML corpus", "status": supervised_ml_corpus["status"], "path": rel_repo_path(ML_CORPUS_DIR)},
        {"group": "Experiment docs", "status": documentation["status"], "path": rel_repo_path(DOCS_EXPERIMENTS_DIR)},
        {"group": "Pipeline diagnostics", "status": diagnostics["status"], "path": rel_repo_path(FINAL_DIR)},
    ]
    return inventory


def build_research_dashboard_context() -> dict[str, Any]:
    final_metrics = collect_final_metrics()
    figures = collect_figure_artifacts()
    tables = collect_table_artifacts()
    documentation = collect_documentation_artifacts()
    diagnostics = collect_pipeline_diagnostics()
    real_world = collect_real_world_regression()
    significance_ml = collect_significance_ml_experiment()
    supervised_ml_corpus = collect_supervised_ml_corpus()

    return {
        "project_card": {
            "method_name": "Гибридный метод анализа версий нормативных документов",
            "pipeline_description": (
                "Конвейер объединяет извлечение текста, нормализацию, структурное разбиение, "
                "сравнение редакций, приоритизацию значимости изменений, генерацию краткой "
                "выжимки и формирование контрольных материалов."
            ),
            "formula": METHOD_FORMULA,
            "stages": [
                "E — extraction",
                "N — normalization",
                "S — structural chunking",
                "C — comparison / diff",
                "P — significance prioritization",
                "G — summary generation",
                "R — quiz / review / reporting",
            ],
        },
        "stage_cards": collect_stage_cards(final_metrics, diagnostics),
        "final_metrics": final_metrics,
        "figures": figures,
        "tables": tables,
        "documentation": documentation,
        "diagnostics": diagnostics,
        "real_world": real_world,
        "significance_ml": significance_ml,
        "supervised_ml_corpus": supervised_ml_corpus,
        "limitations": [
            "Экспериментальный корпус ограничен по объёму и не исчерпывает все типы нормативных документов и редакционных сценариев.",
            "Часть выводов основана на synthetic/gold corpus и экспертной разметке, что корректно для исследовательской валидации, но не заменяет широкую полевую апробацию.",
            "Расширение real-world corpus, трассировка происхождения изменений и ML-эксперименты по значимости отнесены к следующим фазам проекта.",
            "Панель визуализирует уже рассчитанные artifacts и не пересчитывает эксперименты во время HTTP-запроса, чтобы не смешивать демонстрационный контур и исследовательский offline pipeline.",
        ],
        "artifact_inventory": collect_artifact_inventory(
            final_metrics,
            figures,
            tables,
            documentation,
            diagnostics,
            real_world,
            significance_ml,
            supervised_ml_corpus,
        ),
    }


def resolve_artifact_path(artifact_path: str) -> Path | None:
    candidate = (PROJECT_ROOT / artifact_path).resolve()
    for root in ARTIFACT_ROOTS:
        try:
            candidate.relative_to(root.resolve())
            if candidate.is_file():
                return candidate
        except ValueError:
            continue
    return None
