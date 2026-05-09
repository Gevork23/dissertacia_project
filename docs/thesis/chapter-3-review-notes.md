# Chapter 3 Review Notes

## 1. Что уже готово

- Создан полноценный черновик `docs/thesis/chapter-3-draft.md` с разделами 3.1–3.12.
- Включено описание цели экспериментальной оценки, evaluation corpus, методики, component-level результатов и end-to-end trace.
- Использованы фактические значения из артефактов Фаз 14–20 без пересчёта метрик вручную.
- Включены результаты structural chunking, diff/comparison, significance-layer, summary-layer, quiz generation и integrated evaluation.
- Включён bottleneck `pair_06_procedure_change` с корректной интерпретацией: upstream diff/significance сработали, downstream summary/quiz не покрыли expected topic.
- Добавлены ограничения, threats to validity и аккуратные выводы без завышенных утверждений.
- Создана карта источников `docs/thesis/chapter-3-source-map.md`.
- Создана карта рисунков и таблиц `docs/thesis/chapter-3-figures-and-tables-map.md`.

## 2. Какие места требуют ручной проверки

- Нумерация таблиц и рисунков после включения главы в общий текст диссертации.
- Соответствие формата таблиц требованиям кафедры и методическим указаниям.
- Нужно ли переводить англоязычные термины `pipeline`, `summary`, `quiz`, `baseline`, `human-in-the-loop` везде или оставить как технические термины проекта.
- Формулировки про synthetic corpus: они должны оставаться осторожными и не должны звучать как промышленный benchmark.
- Раздел 3.11 можно дополнительно согласовать с научным руководителем, поскольку threats to validity иногда требуют более формального оформления.
- Необходимо проверить, не требуется ли вынести большие таблицы корпуса в приложение, если объём главы будет превышать лимит.

## 3. Где нужно вставить рисунки

| Рисунок | Файл | Рекомендуемый раздел | Назначение |
|---|---|---|---|
| Рисунок 3.1 | `experiments/final_visuals/figures/pipeline_stage_overview.png` | 3.3 / 3.4 | Сводная нормализованная оценка этапов pipeline |
| Рисунок 3.2 | `experiments/final_visuals/figures/diff_baseline_comparison.png` | 3.5 | Сравнение plain text, paragraph и structural chunk diff |
| Рисунок 3.3 | `experiments/final_visuals/figures/summary_quiz_quality.png` | 3.7 / 3.8 | Качество summary и quiz generation |
| Рисунок 3.4 | `experiments/final_visuals/figures/end_to_end_funnel.png` | 3.9 | Funnel прохождения important/critical changes |
| Рисунок 3.5 | `experiments/final_visuals/figures/bottleneck_analysis.png` | 3.9 / 3.10 | Bottleneck `pair_06_procedure_change` |

## 4. Где нужно вставить таблицы

| Таблица | Основа | Рекомендуемый раздел | Назначение |
|---|---|---|---|
| Таблица 3.1 | `docs/evaluation/evaluation-corpus-description.md` | 3.2 | Характеристика evaluation corpus |
| Таблица 3.2 | `experiments/final_visuals/tables/table_01_experiment_summary.md` | 3.3 | Сводные результаты по этапам метода |
| Таблица 3.3 | `experiments/chunking/chunking_summary.json` | 3.4 | Результаты structural chunking |
| Таблица 3.4 | `experiments/final_visuals/tables/table_02_diff_comparison.md` | 3.5 | Сравнение diff approaches |
| Таблица 3.5 | `experiments/significance/significance_summary.json` | 3.6 | Метрики significance-layer |
| Таблица 3.6 | `experiments/summary/summary_evaluation_summary.json` | 3.7 | Метрики summary-layer |
| Таблица 3.7 | `experiments/quiz/quiz_evaluation_summary.json` | 3.8 | Метрики quiz generation |
| Таблица 3.8 | `experiments/final_visuals/tables/table_03_end_to_end_coverage.md` | 3.9 | End-to-end coverage |
| Таблица 3.9 | `experiments/final_visuals/tables/table_05_limitations.md` | 3.10 / 3.11 | Ограничения экспериментальной оценки |

## 5. Какие значения нужно перепроверить перед финальной сдачей

| Значение | Сейчас в главе | Источник |
|---|---:|---|
| Structural chunking micro F1 | 0.2930 | `experiments/chunking/chunking_summary.json` |
| Structural chunking micro recall | 1.0000 | `experiments/chunking/chunking_summary.json` |
| Structural chunking key recall | 1.0000 | `experiments/chunking/chunking_summary.json` |
| Plain text diff F1 / noise | 0.6667 / 10 | `experiments/diff/diff_summary.json` |
| Paragraph diff F1 / noise | 0.3636 / 8 | `experiments/diff/diff_summary.json` |
| Structural chunk diff F1 / noise | 0.8695 / 3 | `experiments/diff/diff_summary.json` |
| Significance accuracy | 0.6923 | `experiments/significance/significance_summary.json` |
| Significance important/critical recall | 1.0000 | `experiments/significance/significance_summary.json` |
| Significance important/critical F1 | 0.8571 | `experiments/significance/significance_summary.json` |
| Summary overall average | 4.1167 | `experiments/summary/summary_evaluation_summary.json` |
| Summary coverage | 8 / 9 | `experiments/summary/summary_evaluation_summary.json` |
| Quiz important change coverage | 0.8889 | `experiments/quiz/quiz_evaluation_summary.json` |
| Quiz average question score | 3.8333 | `experiments/quiz/quiz_evaluation_summary.json` |
| Quiz correct/relevant question rate | 0.6667 / 0.6667 | `experiments/quiz/quiz_evaluation_summary.json` |
| End-to-end success rate | 0.8889 | `experiments/final/end_to_end_summary.json` |
| Bottleneck | `pair_06_procedure_change` | `experiments/final/end_to_end_summary.json` |

## 6. Какие формулировки нужно держать осторожными

- Писать: «на подготовленном evaluation corpus», а не «во всех документах».
- Писать: «подтверждает применимость метода в рамках MVP», а не «доказывает универсальное превосходство».
- Писать: «key-boundary annotation», а не «полный эталон сегментации документа».
- Писать: «significance-layer является recall-oriented deterministic baseline», а не «заменяет эксперта».
- Писать: «quiz generation требует human-in-the-loop approval», а не «автоматически создаёт полностью корректные учебные материалы».
- Писать: «summary делает diff/significance results понятными», а не «формирует юридическое заключение».
- Подчёркивать, что source/explanation rate = 1.0000 не равен correctness = 1.0000.

## 7. Что можно улучшить в будущих версиях

- Расширить evaluation corpus за счёт реальных обезличенных документов и большего числа типов регламентов.
- Добавить full-document segmentation gold standard для более строгой оценки structural chunking.
- Отдельно оценить extraction/OCR для DOCX/PDF и scanned PDF.
- Улучшить semantic representation для procedure changes, чтобы избежать повторения bottleneck `pair_06_procedure_change`.
- Добавить более точное распознавание editorial/informational noise в significance-layer.
- Разделить evaluation of quiz templates и evaluation of upstream-induced errors более формально.
- Добавить inter-annotator agreement или внешнюю экспертную проверку rubric для summary/quiz.
- Подготовить финальную версию главы с единым стилем ссылок, нумерацией рисунков/таблиц и переносом крупных таблиц в приложение при необходимости.
