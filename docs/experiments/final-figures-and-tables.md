# Финальные рисунки и таблицы для главы 3

Документ подготовлен для Фазы 20. Он использует уже созданные результаты Фаз 14–19 и не добавляет новые эксперименты, corpus или алгоритмические изменения.

## Source artifact audit

| Источник | Файл | Найден | Используется для |
| --- | --- | --- | --- |
| Final metrics | experiments/final/final_metrics_summary.json | yes | итоговая таблица, pipeline overview |
| End-to-end summary | experiments/final/end_to_end_summary.json | yes | funnel |
| End-to-end trace | experiments/final/end_to_end_trace.csv | yes | bottleneck analysis |
| Pipeline stage summary | experiments/final/pipeline_stage_summary.csv | yes | сводная интерпретация этапов |
| Final evaluation report | docs/experiments/final-method-evaluation.md | yes | контекст и cautious claims |
| Chunking results | experiments/chunking/chunking_results.csv | yes | проверка источников Phase 14 |
| Chunking summary | experiments/chunking/chunking_summary.json | yes | метрики S / structural chunking |
| Diff results | experiments/diff/diff_results.csv | yes | проверка источников Phase 15 |
| Diff summary | experiments/diff/diff_summary.json | yes | comparison chart |
| Significance results | experiments/significance/significance_results.csv | yes | проверка источников Phase 16 |
| Significance summary | experiments/significance/significance_summary.json | yes | significance-layer metrics |
| Summary results | experiments/summary/summary_results.csv | yes | проверка источников Phase 17 |
| Summary evaluation | experiments/summary/summary_evaluation_summary.json | yes | summary chart |
| Quiz results | experiments/quiz/quiz_results.csv | yes | проверка источников Phase 18 |
| Quiz pair results | experiments/quiz/quiz_pair_results.csv | yes | проверка topic coverage |
| Quiz evaluation | experiments/quiz/quiz_evaluation_summary.json | yes | quiz chart |
| Chunking report | docs/experiments/chunking-evaluation.md | yes | раздел эксперимента S |
| Diff report | docs/experiments/diff-evaluation.md | yes | раздел эксперимента C |
| Significance report | docs/experiments/significance-evaluation.md | yes | раздел эксперимента P |
| Summary report | docs/experiments/summary-evaluation.md | yes | раздел эксперимента G-summary |
| Quiz report | docs/experiments/quiz-generation-evaluation.md | yes | раздел эксперимента G-quiz |


## Финальные рисунки

### Рисунок 3.1 — Сводная оценка этапов гибридного метода

Файл: `experiments/final_visuals/figures/pipeline_stage_overview.png`

Подпись: На рисунке показаны нормализованные показатели качества основных этапов метода: структурного разбиения, сравнения редакций, оценки значимости, формирования выжимки, генерации тестовых материалов и end-to-end прохождения важных изменений через pipeline.

Краткая интерпретация: Рисунок полезен как обзорный материал. Он показывает сопоставимые нормализованные показатели, но подчёркивает, что F1 structural chunking измерялся на selected key-boundary annotation и не должен трактоваться как полный segmentation benchmark.

Рекомендуемое место: Глава 3, раздел 3.3 «Сводная оценка результатов экспериментов».

### Рисунок 3.2 — Сравнение методов обнаружения изменений

Файл: `experiments/final_visuals/figures/diff_baseline_comparison.png`

Подпись: На рисунке сопоставлены strict micro F1 и noise_count для plain text diff, paragraph diff и structural chunk diff.

Краткая интерпретация: Ключевой вывод: structural chunk diff показал более высокий F1 и меньший noise_count на подготовленном corpus. Это поддерживает выбор структурных фрагментов как основы этапа C.

Рекомендуемое место: Глава 3, раздел 3.4 «Оценка сравнения редакций документа».

### Рисунок 3.3 — End-to-end funnel важных изменений

Файл: `experiments/final_visuals/figures/end_to_end_funnel.png`

Подпись: На рисунке показано прохождение 9 important/critical changes через этапы diff detection, significance classification, summary coverage и quiz coverage.

Краткая интерпретация: Это главный защитный график: 9/9 изменений обнаружены diff-layer и классифицированы как significant, 8/9 отражены в summary и 8/9 покрыты quiz.

Рекомендуемое место: Глава 3, раздел 3.6 «Интегральная оценка pipeline».

### Рисунок 3.4 — Качество summary и quiz generation

Файл: `experiments/final_visuals/figures/summary_quiz_quality.png`

Подпись: На рисунке показаны summary overall average, quiz average question score, quiz coverage, source/explanation rate, correct question rate и relevant question rate.

Краткая интерпретация: График показывает сильную source traceability, но также фиксирует ограничение: correct/relevant question rate равен 0.6667, поэтому quiz generation следует позиционировать как baseline с обязательным approval workflow.

Рекомендуемое место: Глава 3, разделы 3.5 и 3.6, где обсуждаются downstream-этапы G.

### Рисунок 3.5 — Анализ bottleneck для pair_06_procedure_change

Файл: `experiments/final_visuals/figures/bottleneck_analysis.png`

Подпись: На рисунке показано, что изменение pair_06_procedure_change было найдено diff-layer и классифицировано как significant, но не было покрыто summary и quiz.

Краткая интерпретация: Bottleneck связан не с обнаружением изменения, а с downstream topic coverage: expected topic про электронную форму подачи заявления не был отражён в summary/quiz.

Рекомендуемое место: Глава 3, раздел 3.6 «Интегральная оценка pipeline» или подраздел «Error propagation».

## Финальные таблицы

### Таблица 3.1 — Аудит исходных экспериментальных артефактов

Файл: `experiments/final_visuals/tables/table_00_source_audit.md`

Подпись: В таблице перечислены исходные файлы Фаз 14–19, использованные для построения финальных визуализаций и dissertation-ready tables.

Рекомендуемое место: Начало раздела 3.3 или приложение к главе 3.

### Таблица 3.2 — Сводные результаты по этапам метода

Файл: `experiments/final_visuals/tables/table_01_experiment_summary.md`

Подпись: Таблица объединяет основные показатели S, C, P, G-summary, G-quiz и end-to-end pipeline.

Рекомендуемое место: Глава 3, раздел 3.3 «Сводная оценка результатов экспериментов».

### Таблица 3.3 — Сравнение diff baseline и structural chunk diff

Файл: `experiments/final_visuals/tables/table_02_diff_comparison.md`

Подпись: Таблица фиксирует F1 и noise_count для трёх подходов к сравнению редакций.

Рекомендуемое место: Глава 3, раздел 3.4 «Оценка сравнения редакций документа».

### Таблица 3.4 — End-to-end coverage важных изменений

Файл: `experiments/final_visuals/tables/table_03_end_to_end_coverage.md`

Подпись: Таблица показывает count/rate прохождения important/critical changes через pipeline.

Рекомендуемое место: Глава 3, раздел 3.6 «Интегральная оценка pipeline».

### Таблица 3.5 — Качество summary и quiz generation

Файл: `experiments/final_visuals/tables/table_04_summary_quiz_quality.md`

Подпись: Таблица фиксирует качество human-readable summary и baseline quiz questions.

Рекомендуемое место: Глава 3, раздел 3.5 «Оценка формирования выжимки и контрольных материалов».

### Таблица 3.6 — Ограничения экспериментальной оценки

Файл: `experiments/final_visuals/tables/table_05_limitations.md`

Подпись: Таблица перечисляет ограничения, влияющие на интерпретацию результатов и формулировку выводов.

Рекомендуемое место: Глава 3, раздел «Threats to validity» или заключительная часть раздела 3.6.

## Готовые формулировки для главы 3

На подготовленном evaluation corpus этап структурного разбиения показал лучший F1 среди рассмотренных baseline-подходов и достиг key recall = 1.0000 для аннотированных ключевых фрагментов. При этом результат следует трактовать как оценку selected key-boundary annotation, а не как полный full-document segmentation benchmark.

Структурно-ориентированное сравнение редакций показало более высокий strict micro F1 и меньший noise_count по сравнению с plain text и paragraph baselines. Это подтверждает целесообразность использования структурных фрагментов документа в качестве основы для этапа сравнения редакций в рамках разработанного MVP.

Significance-layer в текущей конфигурации работает как recall-oriented deterministic baseline: все important/critical changes из evaluation corpus были отнесены к high-priority классу. Одновременно precision ограничен из-за overclassification отдельных editorial/informational изменений, поэтому результаты слоя P следует использовать совместно с human-in-the-loop проверкой.

Summary-layer обеспечивает понятное human-readable представление результатов diff/significance и получил overall average = 4.1167 / 5. Основное ограничение данного этапа связано с upstream-зависимостью: unsupported claims и editorial/noise overemphasis могут переходить из предыдущих стадий pipeline в итоговую выжимку.

Quiz generation покрыл 8 из 9 expected important/critical topics и получил average question score = 3.8333 / 5. Полученные вопросы применимы как baseline control-learning materials, но не должны использоваться без approval workflow ответственным лицом.

Интегральная end-to-end оценка показала, что 8 из 9 important/critical changes прошли полный путь diff detection → significance classification → summary coverage → quiz coverage. Основной bottleneck зафиксирован для pair_06_procedure_change: изменение было обнаружено и классифицировано, но downstream summary/quiz не покрыли expected topic про электронную форму подачи заявления.

Ограничения эксперимента связаны с небольшим синтетическим corpus, key-change annotation вместо full-document gold standard и baseline-природой rule-based significance/quiz generation. Поэтому выводы корректно формулировать как подтверждение применимости метода в рамках локального MVP-сценария, а не как универсальное превосходство над всеми существующими методами анализа нормативных документов.

## Что можно утверждать

- На текущем evaluation corpus structural chunk diff показал лучший F1 и меньший noise_count среди сравниваемых diff-подходов.
- Pipeline обнаружил и классифицировал как significant все 9 important/critical changes, зафиксированные в end-to-end trace.
- Summary и quiz покрыли 8 из 9 important/critical topics, что даёт strict end-to-end success rate = 0.8889.
- Human-in-the-loop approval является необходимым элементом практического использования quiz generation.
- Результаты подтверждают применимость гибридного метода для локального MVP-сценария работы с регламентными документами.

## Что нужно формулировать осторожно

- Не утверждать универсальное превосходство метода над всеми diff algorithms и всеми видами нормативных документов.
- Не трактовать key-change recall/F1 как полную юридическую полноту анализа документа.
- Не утверждать, что significance-layer заменяет экспертную юридическую оценку.
- Не утверждать, что generated quiz questions всегда полностью корректны без проверки человеком.
- Не обобщать результаты за пределы synthetic evaluation corpus без дополнительных экспериментов.

## Recommended thesis inserts

| Chapter section | Insert | Source file |
| --- | --- | --- |
| 3.2 Evaluation corpus | Table/text: corpus overview | docs/evaluation/evaluation-corpus-description.md |
| 3.3 Structural chunking results | Figure: pipeline_stage_overview.png | experiments/final_visuals/figures/pipeline_stage_overview.png |
| 3.3 Experiment summary | Table: table_01_experiment_summary.md | experiments/final_visuals/tables/table_01_experiment_summary.md |
| 3.4 Diff evaluation | Figure: diff_baseline_comparison.png | experiments/final_visuals/figures/diff_baseline_comparison.png |
| 3.4 Diff evaluation | Table: table_02_diff_comparison.md | experiments/final_visuals/tables/table_02_diff_comparison.md |
| 3.5 Summary and quiz evaluation | Figure: summary_quiz_quality.png | experiments/final_visuals/figures/summary_quiz_quality.png |
| 3.5 Summary and quiz evaluation | Table: table_04_summary_quiz_quality.md | experiments/final_visuals/tables/table_04_summary_quiz_quality.md |
| 3.6 Integrated evaluation | Figure: end_to_end_funnel.png | experiments/final_visuals/figures/end_to_end_funnel.png |
| 3.6 Integrated evaluation | Figure: bottleneck_analysis.png | experiments/final_visuals/figures/bottleneck_analysis.png |
| 3.6 Integrated evaluation | Table: table_03_end_to_end_coverage.md | experiments/final_visuals/tables/table_03_end_to_end_coverage.md |
| 3.7 Threats to validity | Table: table_05_limitations.md | experiments/final_visuals/tables/table_05_limitations.md |


## Bottleneck note

Основной miss из `end_to_end_summary.json`: pair_06_procedure_change: detected by diff and classified as important, but not represented in summary/quiz topic coverage.

При включении результатов в диссертацию рекомендуется явно отделить upstream success (diff/significance) от downstream coverage (summary/quiz), чтобы не завышать интерпретацию end-to-end результата.
