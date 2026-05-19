# ML / Hybrid significance experiment

## Назначение

Фаза 6 добавляет в проект отдельный offline-эксперимент по классификации значимости изменений. Его задача — не заменить production-safe rule-based слой, а исследовательски сравнить три стратегии:

1. `rule_based_baseline` — действующий детерминированный слой значимости;
2. `ml_text_model` — лёгкий классификатор на TF-IDF и структурно-лексических признаках;
3. `hybrid_model` — консервативная стратегия объединения rule-based и ML сигналов.

Эксперимент усиливает научную часть проекта и позволяет обсуждать не только качество baseline-эвристик, но и потенциал гибридного подхода без изменения основного backend-контура.

## Почему production layer не меняется

Production significance layer остаётся неизменным по следующим причинам:

- он детерминирован и воспроизводим;
- он уже встроен в explainable pipeline сравнения версий;
- он безопасен для demo и защиты;
- экспериментальный ML-контур работает только offline и не становится обязательной runtime-зависимостью backend.

Таким образом, ML-слой рассматривается как исследовательский comparator, а не как production replacement.

## Источник данных

В текущей фазе используется уже существующий размеченный significance corpus:

- `experiments/significance/significance_results.csv`

Этот файл отражает результаты предыдущей строгой significance evaluation на малом gold/synthetic corpus и содержит:

- `expected_importance` — целевую метку;
- `predicted_importance` — rule-based baseline prediction;
- тексты старой и новой редакции;
- тип операции;
- semantic type;
- дополнительные поясняющие поля.

Real-world regression artifacts из Phase 5 в данном эксперименте не используются как строгие train labels. Они сохраняют статус weak / inference-ready слоя для будущих фаз.

## Используемые labels

Эксперимент работает с теми же метками, что и production significance layer:

- `critical`
- `important`
- `informational`
- `editorial`

Дополнительно вводится бинарная проекция:

- `high_priority` = `critical` или `important`
- `low_priority` = `informational` или `editorial`

Именно recall по high-priority изменениям рассматривается как ключевая прикладная метрика, так как проект ориентирован на минимизацию пропуска действительно важных изменений.

## Признаки ML-модели

Для `ml_text_model` используются только лёгкие локальные признаки, не требующие внешних моделей и сетевого доступа:

1. Текстовые признаки:
   - `old_text`
   - `new_text`
   - `description`
   - `notes`
   - TF-IDF по униграммам и биграммам

2. Структурные признаки:
   - `operation`
   - `change_type`
   - `predicted_semantic_type`
   - длины старого и нового текста
   - абсолютная и относительная разница длины

3. Лексические индикаторы:
   - маркеры сроков;
   - модальные слова обязанности;
   - маркеры отказа;
   - маркеры документов;
   - маркеры ответственности/санкций;
   - маркеры процедуры/канала;
   - editorial/noise признаки;
   - числовые и date-like паттерны;
   - признаки legal-reference.

## Сравниваемые модели

### 1. rule_based_baseline

Использует существующий production слой значимости без каких-либо изменений.

### 2. ml_text_model

Текущая реализация:

- `TfidfVectorizer`
- `DictVectorizer`
- `LogisticRegression(class_weight="balanced")`

При малом корпусе применяется `leave-one-out`, чтобы не терять примеры в train/eval split.

### 3. hybrid_model

Hybrid strategy реализована консервативно:

- если rule-based дал `critical`, это решение сохраняется;
- если rule-based и ML оба указывают на high-priority, baseline сохраняется;
- если rule-based low-priority, а ML high-priority с высокой уверенностью, изменение может быть повышено до `important`;
- если rule-based high-priority, а ML low-priority, hybrid сохраняет rule-based label и фиксирует disagreement.

Такой режим соответствует исследовательской задаче сравнения, но не подменяет production policy.

## Метрики

### Multiclass significance

Для каждой стратегии считаются:

- accuracy;
- macro precision / recall / F1;
- per-label precision / recall / F1;
- confusion matrix.

### Binary high-priority detection

Дополнительно считаются:

- `high_priority_precision`;
- `high_priority_recall`;
- `high_priority_f1`;
- `editorial_high_priority_false_positive_count`;
- `important_critical_miss_count`.

## Как запустить

Из корня репозитория:

```bash
python experiments/significance_ml/evaluate_significance_ml.py
python backend/manage.py run_significance_ml_experiment
```

## Какие outputs создаются

В директории `experiments/significance_ml/` сохраняются:

- `significance_ml_summary.json`
- `significance_ml_predictions.csv`
- `significance_ml_confusion_matrix.csv`
- `significance_ml_feature_report.csv`
- `significance_ml_error_examples.csv`

## Интеграция с Research Dashboard

Research Dashboard в `/demo/research/` читает ML artifacts в read-only режиме и показывает отдельный блок:

- статус эксперимента;
- число примеров;
- распределение меток;
- список сравниваемых моделей;
- high-priority recall/F1 для rule-based baseline;
- macro F1 для ML и hybrid;
- disagreement count;
- preview predictions, confusion matrix, feature report и error examples.

Важно: Dashboard не запускает ML-эксперимент во время HTTP request.

## Ограничения и threats to validity

Текущая фаза имеет существенные ограничения:

- labeled corpus мал и несбалансирован;
- для `important` и `informational` в текущем корпусе доступно по одному примеру;
- поэтому используется `leave-one-out`, а устойчивость multiclass-оценки ограничена;
- полученные результаты нельзя интерпретировать как окончательное доказательство превосходства ML над baseline;
- real-world weak corpus пока не используется как строгая обучающая разметка.

Это корректная исследовательская постановка, но она требует честной интерпретации.

## Связь с Annotation Studio и будущими фазами

Phase 4 (`Annotation Studio`) создаёт основу для накопления новых gold labels. По мере роста экспертной разметки возможны следующие шаги:

- расширение training corpus за счёт `GoldChangeAnnotation`;
- переоценка hybrid policy на richer corpus;
- использование real-world regression suite как weak inference layer;
- ML significance experiment на более сильной выборке;
- последующие Audit Log и Export Reports слои.

## Phase 6.1 corpus note

Начиная с Phase 6.1, если в `experiments/ml_corpus/` доступны `train.csv` и `test.csv`, ML / Hybrid significance experiment использует их как основной supervised corpus. Старый dataset `experiments/significance/significance_results.csv` сохраняется как fallback-режим.
