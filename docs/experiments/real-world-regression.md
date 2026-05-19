# Real-world Regression Suite

## Назначение

Real-world Regression Suite добавляет в проект отдельный воспроизводимый контур проверки устойчивости pipeline на реальных или приближённых к реальным парах нормативных документов. Его задача — показать, что система оценивается не только на малом synthetic/gold evaluation corpus, но и на более широком weak-labeled материале.

Этот слой не заменяет строгую исследовательскую оценку на gold corpus и не меняет core algorithms. Он служит для regression, smoke и stress-проверки offline-контура.

## Отличие от других слоёв корпуса

### Gold / synthetic evaluation corpus

`data/evaluation_corpus/` используется для строгой оценки качества на вручную размеченных парах. В этой фазе он не меняется.

### Demo corpus

`data/demo_corpus/` используется для стабильного показательного сценария demo UI. Он также не меняется.

### Real-world regression corpus

`experiments/real_world/` использует более широкий слой weak-labeled пар:

1. `regression/ruslawod_test_cases.json` как основной источник weak real-world pairs;
2. `data/demo_corpus/` как fallback demonstration regression;
3. `data/manual_samples/` как минимальный аварийный fallback.

Если suite уходит на fallback demo corpus, это должно интерпретироваться как realistic demo regression, а не как полноценный real-world benchmark.

## Источник данных

В текущем репозитории для weak real-world regression используются уже подготовленные пары из `regression/ruslawod_test_cases.json`. Они происходят из ранее импортированного и сгруппированного RusLawOD-материала и трактуются как weak labels: без строгих expert gold expectations по каждому изменению.

Pair discovery идёт по следующему приоритету:

1. weak real-world RusLawOD pairs;
2. demo corpus pairs;
3. minimal manual fallback pair.

## Что создаёт suite

После запуска формируются следующие артефакты:

- `experiments/real_world/real_world_summary.json`
- `experiments/real_world/real_world_pair_results.csv`
- `experiments/real_world/real_world_trace.csv`
- `experiments/real_world/real_world_stage_summary.csv`

## Какие метрики считаются

Suite сознательно не использует термин strict accuracy при отсутствии ручной gold-разметки. Вместо этого считаются cautious regression-показатели:

- `total_pairs`
- `processed_pairs`
- `failed_pairs`
- `total_changes`
- `average_changes_per_pair`
- `average_chunks_old`
- `average_chunks_new`
- `significant_change_rate`
- `critical_or_important_rate`
- `summary_generation_available`
- `quiz_generation_available`
- `warning_count`
- `pipeline_success_rate`

Эти метрики показывают устойчивость и покрытие pipeline, а не юридическую полноту качества на всем реальном мире.

## Запуск

Из корня репозитория:

```bash
python experiments/real_world/evaluate_real_world.py
```

Через Django management command:

```bash
python backend/manage.py run_real_world_regression
```

## Отображение в Research Dashboard

Research Dashboard читает готовые артефакты из `experiments/real_world/` в read-only режиме и показывает отдельный блок:

- статус suite;
- число найденных и обработанных пар;
- число ошибок;
- total changes;
- pipeline success rate;
- significant change rate;
- preview pair results;
- preview stage summary;
- limitations.

Dashboard не пересчитывает regression suite на HTTP request.

## Ограничения и threats to validity

- weak real-world pairs не эквивалентны строгой gold-разметке;
- часть RusLawOD pairs построена по эвристике version-family grouping, а не по безусловно подтверждённой юридической lineage;
- suite работает по подготовленным plain-text pairs и не заменяет отдельную проверку binary extraction;
- fallback на demo corpus полезен для regression smoke, но не должен подаваться как полноценный внешний benchmark.

## Связь со следующими фазами

Этот слой логически поддерживает следующие этапы развития проекта:

- ML significance experiment;
- Audit Log;
- Export Reports.

Он также даёт дополнительную эмпирическую опору для Annotation Studio и Traceability View, не вмешиваясь в core pipeline.
