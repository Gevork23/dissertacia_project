# Chapter 3 Figures and Tables Map

Документ фиксирует готовые рисунки и таблицы, которые используются или рекомендуются для вставки в главу 3.

## Figures

| Figure | Caption | Source file | Used in section | Notes |
|---|---|---|---|---|
| Рисунок 3.1 | Сводная оценка этапов гибридного метода | `experiments/final_visuals/figures/pipeline_stage_overview.png` | 3.3, 3.4 | Нормализованные показатели; summary/quiz scores делятся на 5 |
| Рисунок 3.2 | Сравнение методов обнаружения изменений | `experiments/final_visuals/figures/diff_baseline_comparison.png` | 3.5 | Сравнивает F1 и noise_count для diff-подходов |
| Рисунок 3.3 | Качество summary и quiz generation | `experiments/final_visuals/figures/summary_quiz_quality.png` | 3.7, 3.8 | Показывает summary score, quiz score, coverage, source, correctness/relevance |
| Рисунок 3.4 | End-to-end funnel прохождения важных изменений через pipeline | `experiments/final_visuals/figures/end_to_end_funnel.png` | 3.9 | Главный график integrated evaluation |
| Рисунок 3.5 | Анализ bottleneck для `pair_06_procedure_change` | `experiments/final_visuals/figures/bottleneck_analysis.png` | 3.9, 3.10 | Показывает downstream miss при успешных diff/significance |

## Tables

| Table | Caption | Source file | Used in section | Notes |
|---|---|---|---|---|
| Таблица 3.1 | Характеристика evaluation corpus | `docs/evaluation/evaluation-corpus-description.md` | 3.2 | Сформирована в главе на основе описания корпуса |
| Таблица 3.2 | Сводные результаты по этапам метода | `experiments/final_visuals/tables/table_01_experiment_summary.md` | 3.3 | Готовая dissertation-ready сводка Фазы 20 |
| Таблица 3.3 | Результаты оценки structural chunking | `experiments/chunking/chunking_summary.json` | 3.4 | Сформирована из aggregate_by_method |
| Таблица 3.4 | Сравнение diff-подходов | `experiments/final_visuals/tables/table_02_diff_comparison.md` | 3.5 | Обязательная таблица diff/comparison |
| Таблица 3.5 | Результаты оценки significance-layer | `experiments/significance/significance_summary.json` | 3.6 | Сформирована из aggregate metrics Фазы 16 |
| Таблица 3.6 | Результаты оценки summary-layer | `experiments/summary/summary_evaluation_summary.json` | 3.7 | Обязательная таблица summary metrics |
| Таблица 3.7 | Результаты оценки quiz generation | `experiments/quiz/quiz_evaluation_summary.json` | 3.8 | Обязательная таблица quiz metrics |
| Таблица 3.8 | End-to-end coverage важных изменений | `experiments/final_visuals/tables/table_03_end_to_end_coverage.md` | 3.9 | Обязательная funnel table |
| Таблица 3.9 | Основные ограничения экспериментальной оценки | `experiments/final_visuals/tables/table_05_limitations.md` | 3.10, 3.11 | Можно оставить в тексте или перенести в приложение |

## Additional available tables

| Source file | Purpose | Recommended use |
|---|---|---|
| `experiments/final_visuals/tables/table_00_source_audit.md` | Аудит исходных артефактов Фаз 14–19 | Можно использовать в приложении или в source map |
| `experiments/final_visuals/tables/table_04_summary_quiz_quality.md` | Combined summary/quiz metrics | Использовано как основа для таблиц 3.6 и 3.7 |
| `experiments/final_visuals/tables/table_06_recommended_thesis_inserts.md` | Рекомендации по вставке материалов | Использовано для этой карты |

## Insert checklist

- [ ] Проверить нумерацию после объединения с главами 1–2.
- [ ] Проверить, что изображения корректно отображаются при сборке итогового документа.
- [ ] Проверить, нужно ли заменить относительные пути на финальные ссылки/подписи в DOCX/PDF.
- [ ] Проверить, не требуется ли вынести таблицу 3.1 или 3.9 в приложение.
