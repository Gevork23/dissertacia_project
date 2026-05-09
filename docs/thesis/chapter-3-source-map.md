# Chapter 3 Source Map

Документ фиксирует, из каких отчётов, данных и визуальных артефактов взяты разделы главы 3. Цель карты — упростить ручную проверку чисел, формулировок и ссылок перед финальной редактурой диссертации.

| Section | Source documents | Source data files | Figures/tables |
|---|---|---|---|
| 3.1. Цель и задачи экспериментальной оценки | `docs/experiments/final-method-evaluation.md`; `docs/research/hybrid-method.md` | `experiments/final/final_metrics_summary.json`; `experiments/final/end_to_end_summary.json` | Таблица 3.2 |
| 3.2. Описание evaluation corpus | `docs/evaluation/evaluation-corpus-description.md`; `docs/evaluation/annotation-guidelines.md` | `data/evaluation_corpus/*/annotation.json`; `scripts/validate_evaluation_corpus.py` | Таблица 3.1 |
| 3.3. Методика проведения экспериментов | `docs/experiments/README.md`; `docs/experiments/final-method-evaluation.md`; `docs/experiments/final-figures-and-tables.md` | `experiments/final/final_metrics_summary.json`; `experiments/final/pipeline_stage_summary.csv`; `experiments/final_visuals/final_visuals_manifest.json` | Таблица 3.2; Рисунок 3.1 |
| 3.4. Structural chunking | `docs/experiments/chunking-evaluation.md`; `docs/research/structural-chunking-method.md` | `experiments/chunking/chunking_summary.json`; `experiments/chunking/chunking_results.csv` | Таблица 3.3; Рисунок 3.1 |
| 3.5. Diff/comparison | `docs/experiments/diff-evaluation.md`; `docs/research/version-comparison-method.md` | `experiments/diff/diff_summary.json`; `experiments/diff/diff_results.csv`; `experiments/final_visuals/tables/table_02_diff_comparison.md` | Таблица 3.4; Рисунок 3.2 |
| 3.6. Significance-layer | `docs/experiments/significance-evaluation.md`; `docs/research/significance-method.md` | `experiments/significance/significance_summary.json`; `experiments/significance/significance_results.csv`; `experiments/significance/significance_confusion_matrix.png` | Таблица 3.5 |
| 3.7. Summary-layer | `docs/experiments/summary-evaluation.md`; `docs/experiments/final-figures-and-tables.md` | `experiments/summary/summary_evaluation_summary.json`; `experiments/summary/summary_results.csv`; `experiments/final_visuals/tables/table_04_summary_quiz_quality.md` | Таблица 3.6; Рисунок 3.3 |
| 3.8. Quiz generation | `docs/experiments/quiz-generation-evaluation.md`; `docs/research/quiz-generation-method.md` | `experiments/quiz/quiz_evaluation_summary.json`; `experiments/quiz/quiz_results.csv`; `experiments/quiz/quiz_pair_results.csv`; `experiments/final_visuals/tables/table_04_summary_quiz_quality.md` | Таблица 3.7; Рисунок 3.3 |
| 3.9. End-to-end evaluation | `docs/experiments/final-method-evaluation.md`; `docs/experiments/final-figures-and-tables.md` | `experiments/final/end_to_end_summary.json`; `experiments/final/end_to_end_trace.csv`; `experiments/final/pipeline_stage_summary.csv`; `experiments/final_visuals/tables/table_03_end_to_end_coverage.md` | Таблица 3.8; Рисунок 3.4; Рисунок 3.5 |
| 3.10. Анализ ошибок и ограничений | `docs/experiments/final-method-evaluation.md`; `docs/experiments/*-evaluation.md`; `docs/experiments/final-figures-and-tables.md` | `experiments/final/error_propagation.csv`; `experiments/final/end_to_end_trace.csv`; `experiments/final_visuals/tables/table_05_limitations.md` | Таблица 3.9; Рисунок 3.5 |
| 3.11. Threats to validity | `docs/experiments/final-method-evaluation.md`; `docs/evaluation/annotation-guidelines.md`; `docs/evaluation/evaluation-corpus-description.md` | `experiments/final_visuals/final_visuals_manifest.json`; `experiments/final/artifact_audit.csv` | Таблица 3.9 |
| 3.12. Выводы | `docs/experiments/final-method-evaluation.md`; `docs/experiments/final-figures-and-tables.md`; all Phase 14–20 experiment reports | `experiments/final/final_metrics_summary.json`; `experiments/final/end_to_end_summary.json` | Таблицы 3.2–3.9; Рисунки 3.1–3.5 |

## Source files checked for Phase 21

| Category | Files |
|---|---|
| Experiment reports | `docs/experiments/chunking-evaluation.md`; `docs/experiments/diff-evaluation.md`; `docs/experiments/significance-evaluation.md`; `docs/experiments/summary-evaluation.md`; `docs/experiments/quiz-generation-evaluation.md`; `docs/experiments/final-method-evaluation.md`; `docs/experiments/final-figures-and-tables.md`; `docs/experiments/README.md` |
| Evaluation docs | `docs/evaluation/evaluation-corpus-description.md`; `docs/evaluation/annotation-guidelines.md` |
| Research/method docs | `docs/research/hybrid-method.md`; `docs/research/structural-chunking-method.md`; `docs/research/version-comparison-method.md`; `docs/research/significance-method.md`; `docs/research/quiz-generation-method.md` |
| Final aggregation | `experiments/final/final_metrics_summary.json`; `experiments/final/end_to_end_summary.json`; `experiments/final/end_to_end_trace.csv`; `experiments/final/error_propagation.csv`; `experiments/final/pipeline_stage_summary.csv`; `experiments/final/artifact_audit.csv` |
| Final visuals | `experiments/final_visuals/final_visuals_manifest.json`; `experiments/final_visuals/figures/*.png`; `experiments/final_visuals/tables/*.md` |

## Key numeric values used in chapter 3

| Component | Value | Source |
|---|---:|---|
| Structural chunking micro F1 | 0.2930 | `experiments/chunking/chunking_summary.json` |
| Structural chunking micro recall | 1.0000 | `experiments/chunking/chunking_summary.json` |
| Structural chunking key recall | 1.0000 | `experiments/chunking/chunking_summary.json` |
| Plain text diff F1 / noise | 0.6667 / 10 | `experiments/diff/diff_summary.json` |
| Paragraph diff F1 / noise | 0.3636 / 8 | `experiments/diff/diff_summary.json` |
| Structural chunk diff F1 / noise | 0.8695 / 3 | `experiments/diff/diff_summary.json` |
| Significance important/critical recall | 1.0000 | `experiments/significance/significance_summary.json` |
| Significance important/critical F1 | 0.8571 | `experiments/significance/significance_summary.json` |
| Summary overall average | 4.1167 | `experiments/summary/summary_evaluation_summary.json` |
| Summary covered topics | 8 / 9 | `experiments/summary/summary_evaluation_summary.json` |
| Quiz important change coverage | 0.8889 | `experiments/quiz/quiz_evaluation_summary.json` |
| Quiz average question score | 3.8333 | `experiments/quiz/quiz_evaluation_summary.json` |
| Strict end-to-end success rate | 0.8889 | `experiments/final/end_to_end_summary.json` |
| Main bottleneck | `pair_06_procedure_change` | `experiments/final/end_to_end_summary.json`; `experiments/final/end_to_end_trace.csv` |
