# Research Dashboard

## Назначение

Research Dashboard предназначен для демонстрации исследовательского статуса проекта `dissertacia_project` как информационной системы, которая поддерживает не только demo-сценарий, но и воспроизводимый анализ качества гибридного метода обработки версий нормативных документов.

Маршрут панели: `/demo/research/`.

Панель работает только в режиме чтения и визуализирует уже сохранённые artifacts. Она не запускает эксперименты при HTTP-запросе и не меняет существующие результаты.

## Какие artifacts читает панель

Research Dashboard использует уже существующие файлы проекта, в том числе:

- `experiments/final/final_metrics_summary.json`
- `experiments/final/final_metrics_summary.csv`
- `experiments/final/end_to_end_summary.json`
- `experiments/final/end_to_end_trace.csv`
- `experiments/final/error_propagation.csv`
- `experiments/final/pipeline_stage_summary.csv`
- `experiments/final_visuals/figures/*.png`
- `experiments/final_visuals/tables/*.csv`
- `experiments/final_visuals/tables/*.md`
- `experiments/real_world/real_world_summary.json`
- `experiments/real_world/real_world_pair_results.csv`
- `experiments/real_world/real_world_trace.csv`
- `experiments/real_world/real_world_stage_summary.csv`
- `experiments/significance_ml/significance_ml_summary.json`
- `experiments/significance_ml/significance_ml_predictions.csv`
- `experiments/significance_ml/significance_ml_confusion_matrix.csv`
- `experiments/significance_ml/significance_ml_feature_report.csv`
- `experiments/significance_ml/significance_ml_error_examples.csv`
- `docs/experiments/*.md`

Если часть artifacts отсутствует, панель не падает и показывает предупреждение `artifact missing / not available`.

## Что показывает панель

### 1. Общая карточка метода

Показываются:

- название метода;
- краткое описание pipeline;
- формула `M = <E, N, S, C, P, G, R>`.

### 2. Стадии метода

Показываются карточки стадий:

- Structural chunking
- Version comparison / diff
- Significance classification
- Summary generation
- Quiz generation
- End-to-end pipeline

Для каждой стадии отображаются метрики и ссылки на связанные artifacts, если они доступны.

### 3. Final metrics summary

Показываются:

- структурированные метрики из `final_metrics_summary.json`;
- CSV preview;
- flattened key/value view для безопасного отображения вложенных JSON-структур.

### 4. Visual artifacts

Показываются PNG figures из `experiments/final_visuals/figures/`.

### 5. Tables

Показываются:

- preview CSV-таблиц;
- preview Markdown-таблиц;
- пути к исходным artifacts.

### 6. End-to-end diagnostics

Показываются:

- summary metrics;
- stage summary;
- error propagation preview;
- end-to-end trace preview.

### 7. Real-world regression suite

Показываются:

- статус offline weak regression contour;
- количество пар;
- processed/failed pairs;
- total changes;
- pipeline success rate;
- significant change rate;
- preview pair results и stage summary;
- ограничения интерпретации weak-labeled corpus.

### 8. ML / Hybrid significance experiment

Показываются:

- статус offline ML significance experiment;
- количество примеров;
- распределение меток;
- список сравниваемых моделей;
- rule-based high-priority recall/F1;
- ML macro F1;
- hybrid macro F1;
- disagreement count;
- preview predictions;
- preview confusion matrix;
- preview feature report;
- preview error examples.

## Почему панель не пересчитывает эксперименты

Панель не запускает эксперименты в runtime по следующим причинам:

- исследовательские расчёты относятся к offline-контуру;
- runtime-пересчёт сделал бы demo UI хрупким и медленным;
- dissertation-ready artifacts уже зафиксированы в JSON/CSV/PNG/Markdown;
- смешивать демонстрационный и вычислительный контур в одном HTTP-запросе методологически нежелательно.

Таким образом, Dashboard выполняет роль витрины и интерфейса чтения, а не движка вычисления.

## Связь с научной частью проекта

Research Dashboard усиливает научную упаковку проекта за счёт:

- явной связи между стадиями метода и метриками качества;
- демонстрации воспроизводимых offline artifacts;
- визуального показа figures и tables, пригодных для главы с экспериментами;
- честной фиксации ограничений корпуса, baseline и real-world regression layers.

Это позволяет позиционировать систему как исследовательскую платформу, а не только как demo-приложение.

## Ограничения

Панель имеет сознательные ограничения:

- она отображает только уже сохранённые results;
- корректность интерпретации зависит от качества evaluation corpus;
- synthetic/gold corpus остаётся ограниченным по масштабу;
- weak real-world regression suite не равен строгому benchmark;
- ML significance experiment пока опирается на малый и несбалансированный labeled corpus.

## Следующие логические фазы

Research Dashboard логически связан со следующими слоями проекта:

- Traceability View
- Annotation Studio
- Real-world Regression Suite
- ML significance experiment
- Audit Log
- Export Reports

## Supervised ML corpus extension

Начиная с Phase 6.1, панель также читает artifacts из `experiments/ml_corpus/` и показывает отдельный блок `Supervised ML corpus`:

- `dataset_profile.json`
- `train.csv`
- `test.csv`
- `weak_inference_dataset.csv`
- `dataset_quality_report.md`
- `figures/*.png`

Этот блок предназначен для демонстрации reproducible train/test data layer для дальнейших classical ML experiments и не запускает сборку корпуса во время HTTP request.
