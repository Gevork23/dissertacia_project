# Significance Layer Evaluation

## 1. Цель эксперимента

Эксперимент оценивает этап `P — Prioritization / Significance classification` гибридного метода. Цель — проверить, насколько текущий deterministic/rule-based baseline назначает уровни значимости вручную размеченным изменениям и насколько он отделяет содержательные изменения от редакционных.

## 2. Связь с гибридным методом

В методе `M = <E, N, S, C, P, G, R>` данный эксперимент проверяет компонент `P`. Этап получает change candidates после сравнения редакций и формирует `semantic_type`, `significance_label`, score, rules, reason и manual-review flag. Эти поля затем используются summary и quiz generation.

## 3. Evaluation corpus

Использован `data/evaluation_corpus/`: 10 пар документов и 13 manually annotated expected changes. Разметка содержит `old_text`, `new_text`, `importance`, `semantic_type`, `change_type`, темы summary/quiz и known difficulties.

Распределение expected labels:

| Expected label | Count |
|---|---|
| critical | 8 |
| editorial | 3 |
| important | 1 |
| informational | 1 |

## 4. Что именно оценивается

Основной запуск оценивает production wrapper `documents.domain.change_enrichment.enrich_change()`. На вход подаются только корректные oracle change spans (`old_text`/`new_text`) из annotation. Gold `importance` используется только как target label; gold `semantic_type` не передаётся в основной классификатор, чтобы не превращать эксперимент в проверку простого mapping `semantic_type -> importance`.

Дополнительно сохранён semantic-hint diagnostic: тот же production wrapper вызывается с annotated `semantic_type`. Этот режим показывает верхнюю границу для final importance mapping при идеальном semantic-type сигнале, но не используется как основная метрика.

## 5. Oracle-change evaluation vs pipeline evaluation

Основная метрика — oracle-change evaluation: сравниваются expected changes из annotation и predicted importance от significance-layer. Это отделяет оценку `P` от ошибок поиска изменений на этапе `C`.

Pipeline significance evaluation не смешивается с основной метрикой. Для анализа pipeline использованы результаты Фазы 15: structural diff нашёл все 10 meaningful/key changes в strict-режиме и дал 3 FP/noise, поэтому в реальном pipeline significance получает более чистый вход, чем plain text и paragraph baselines, но всё равно зависит от пропусков и noise comparison-layer.

## 6. Классы значимости

| Label | Meaning | Used in evaluation |
|---|---|---|
| critical | Изменения сроков, обязанностей, отказов, документов, ответственности | yes |
| important | Изменения процедуры или условий взаимодействия | yes |
| informational | Справочная или поясняющая информация | yes |
| editorial | Редакционные или структурные изменения без смыслового влияния | yes |
| not_evaluated | Техническое default-состояние модели | technical/default only |

В проекте отсутствуют `medium` и `minor`. Mapping не применялся: annotation уже использует штатные labels проекта `critical`, `important`, `informational`, `editorial`. `not_evaluated` является техническим default-состоянием и в corpus не встречается.

## 7. Метрики

Считались exact-label accuracy, binary precision/recall/F1 для high-priority класса, confusion matrix, editorial false positive rate, macro/weighted F1 и per-class precision/recall/F1.

## 8. Important/Critical positive class

Основной positive class: `{critical, important}`. Эти изменения должны попадать в summary/quiz с высоким приоритетом. Negative class: `{informational, editorial, not_evaluated}`. Отдельно в JSON сохранён diagnostic meaningful-class вариант `{critical, important, informational}`.

## 9. Editorial false positive policy

Broad editorial false positive: expected `editorial`, predicted one of `{critical, important, informational}`. Strict high-priority editorial false positive: expected `editorial`, predicted one of `{critical, important}`.

## 10. Результаты

| Pair | Change | Expected importance | Predicted importance | Correct |
|---|---|---|---|---|
| pair_01_deadline_change | chg_001 | critical | critical | yes |
| pair_02_added_obligation | chg_001 | critical | critical | yes |
| pair_03_document_list_change | chg_001 | critical | important | no |
| pair_04_refusal_ground_change | chg_001 | critical | critical | yes |
| pair_05_editorial_change | chg_001 | editorial | important | no |
| pair_06_procedure_change | chg_001 | important | important | yes |
| pair_07_responsibility_change | chg_001 | critical | critical | yes |
| pair_08_reordered_structure | chg_001 | editorial | editorial | yes |
| pair_09_mixed_significant_and_editorial | chg_001 | critical | critical | yes |
| pair_09_mixed_significant_and_editorial | chg_002 | editorial | important | no |
| pair_09_mixed_significant_and_editorial | chg_003 | critical | critical | yes |
| pair_09_mixed_significant_and_editorial | chg_004 | informational | important | no |
| pair_10_weakly_structured_document | chg_001 | critical | critical | yes |

## 11. Aggregate metrics

| Metric | Value |
|---|---|
| Accuracy | 0.6923 |
| Important/Critical Precision | 0.7500 |
| Important/Critical Recall | 1.0000 |
| Important/Critical F1 | 0.8571 |
| Editorial false positive rate | 0.6667 |
| Editorial high-priority FP rate | 0.6667 |
| Macro F1 | 0.4416 |
| Weighted F1 | 0.7154 |

Semantic-hint diagnostic upper bound:

| Metric | Value |
|---|---|
| Accuracy | 1.0000 |
| Important/Critical Precision | 1.0000 |
| Important/Critical Recall | 1.0000 |
| Editorial false positive rate | 0.0000 |

## 12. Confusion matrix

Матрица: rows = expected importance, columns = predicted importance.

| Expected \ Predicted | critical | important | informational | editorial |
|---|---|---|---|---|
| critical | 7 | 1 | 0 | 0 |
| important | 0 | 1 | 0 | 0 |
| informational | 0 | 1 | 0 | 0 |
| editorial | 0 | 2 | 0 | 1 |

PNG: `experiments/significance/significance_confusion_matrix.png`.

## 13. Per-class analysis

| Class | Support | Precision | Recall | F1 |
|---|---|---|---|---|
| critical | 8 | 1.0000 | 0.8750 | 0.9333 |
| important | 1 | 0.2000 | 1.0000 | 0.3333 |
| informational | 1 | 0.0000 | 0.0000 | 0.0000 |
| editorial | 3 | 1.0000 | 0.3333 | 0.5000 |

Классы `critical` и `important` имеют recall 1.0 в binary high-priority постановке: значимые изменения не были потеряны. Основные ошибки exact-label связаны не с пропуском high-priority changes, а с завышением низкоприоритетных или редакционных изменений до `important`, а также с недооценкой одного document-list change с `critical` до `important`.

## 14. Editorial false positives

В корпусе 3 expected editorial changes. Broad editorial FP: 2 (0.6667). Strict high-priority editorial FP: 2 (0.6667).

Две редакционные замены глагола `осуществляет` -> `выполняет` были подняты до `important` через fallback/manual-review path. Это показывает ограничение лексического rule-based baseline: он не всегда распознаёт синонимическую редакционную замену без дополнительного editorial signal от comparison-layer.

## 15. Error examples

- `pair_03_document_list_change/chg_001`: expected `critical`, predicted `important`; rules: `important_keywords`.
- `pair_05_editorial_change/chg_001`: expected `editorial`, predicted `important`; rules: `fallback_manual_review`.
- `pair_09_mixed_significant_and_editorial/chg_002`: expected `editorial`, predicted `important`; rules: `fallback_manual_review`.
- `pair_09_mixed_significant_and_editorial/chg_004`: expected `informational`, predicted `important`; rules: `fallback_manual_review`.

Подробные примеры сохранены в `experiments/significance/significance_error_examples.md`.

## 16. Связь с diff/comparison evaluation

Significance работает поверх changes. Если comparison пропускает изменение, significance не сможет его классифицировать. Если comparison создаёт noise, significance попытается назначить label шумовому элементу, что может породить ложный high-priority highlight.

Фаза 15 показала для structural chunk diff: micro precision = 0.7692, micro recall = 1.0000, micro F1 = 0.8695, noise_count = 3. Это лучше plain text и paragraph baselines по strict key-change evaluation и означает, что `P` получает менее шумный вход при использовании structural comparison.

## 17. Ограничения эксперимента

- Corpus малый и синтетический: 10 пар, 13 expected changes.
- Разметка является key-change gold standard, а не exhaustive full-document benchmark.
- Основной oracle-change запуск использует корректные spans, но не использует gold semantic labels; поэтому он строже, чем semantic-hint upper bound, но всё ещё не полностью равен real pipeline.
- Production pipeline может дать дополнительные `change_classification` signals, которые улучшают editorial detection; эта связь вынесена в diagnostic discussion, а не смешана с основной метрикой.
- `medium` и `minor` в текущей реализации отсутствуют, поэтому не оценивались.
- Rule-based baseline ограничен полнотой регулярных выражений и не выполняет глубокое юридико-семантическое сравнение синонимов и условий.

## 18. Вывод для диссертации

Экспериментальная оценка significance-layer показала, что rule-based baseline надёжно находит high-priority changes в текущем corpus: для класса `{critical, important}` recall = 1.0000, F1 = 0.8571. Система корректно выделяет изменения сроков, обязанностей и ответственности. Основные ограничения проявляются в точной градации severity и в отделении редакционных/информационных формулировок от важных при отсутствии semantic hints. Это подтверждает целесообразность этапа `P` в составе метода `M = <E, N, S, C, P, G, R>`, но показывает необходимость human-in-the-loop контроля, расширения корпуса и дальнейшего уточнения правил для сложных юридических формулировок.
