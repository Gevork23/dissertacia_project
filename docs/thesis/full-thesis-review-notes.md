# Full Thesis Review Notes

## 1. Что собрано

В рамках Фазы 25 собраны и подготовлены следующие материалы:

- `docs/thesis/introduction-draft.md` — академический черновик введения;
- `docs/thesis/conclusion-draft.md` — академический черновик заключения;
- `docs/thesis/full-thesis-draft.md` — полный markdown-черновик диссертации, включающий введение, главы 1–3, заключение, placeholder списка литературы и placeholder приложений;
- `docs/thesis/final-thesis-structure.md` — структура финального текста диссертации;
- `docs/thesis/full-thesis-review-notes.md` — текущие заметки для ручной доработки полного черновика.

При подготовке использованы главы 1–3, `integrated-main-draft.md`, `integration-review-report.md`, `terminology-glossary.md`, `cross-chapter-consistency-checklist.md`, `bibliography-placeholders.md`, `thesis-open-issues.md`, `hybrid-method.md`, экспериментальные отчёты, `PROJECT_SCOPE.md`, `README.md` и `mvp-freeze.md`.

## 2. Какие разделы готовы содержательно

Содержательно готовы:

- введение с актуальностью, объектом, предметом, целью, задачами, научной новизной, практической значимостью, методами исследования, положениями на защиту и структурой диссертации;
- заключение с итогами работы, решением задач, научными и практическими результатами, экспериментальными результатами, ограничениями и направлениями дальнейшего развития;
- полный черновик, логически объединяющий введение, главу 1, главу 2, главу 3 и заключение;
- осторожные формулировки о local-first MVP, deterministic/rule-based/hybrid pipeline, optional/fallback роли LLM и human-in-the-loop approval.

## 3. Где нужны внешние источники

Финальная версия требует ручного подбора реальных источников. Нельзя добавлять выдуманные библиографические записи. Основные категории источников сохранены из `docs/thesis/bibliography-placeholders.md`:

- рост объёма нормативной информации и электронного документооборота;
- document management systems / СЭД / ECM;
- правовые справочные системы и legal tech;
- document comparison, diff algorithms, structure-aware comparison;
- legal NLP и document intelligence;
- LLM reliability, hallucinations, grounded generation, traceability;
- human-in-the-loop systems и responsible AI;
- employee training, compliance learning, knowledge transfer;
- methodology for NLP/document system evaluation and threats to validity.

В `introduction-draft.md` оставлен явный placeholder для источника о росте объёмов нормативной информации / электронного документооборота.

## 4. Где нужны номера рисунков и таблиц

Финальная сборка требует проверки:

- сквозной нумерации таблиц глав 1–3;
- нумерации рисунков 1.x, 2.x, 3.x;
- соответствия ссылок в тексте фактическим рисункам и таблицам;
- вставки Mermaid/PNG/ERD-материалов из архитектурных и экспериментальных артефактов;
- решения, какие крупные таблицы оставить в тексте, а какие перенести в приложения.

Особенно важно проверить рисунки главы 2 и финальные экспериментальные графики главы 3, так как текущий markdown-черновик не является финальной DOCX/PDF-вёрсткой.

## 5. Где нужна проверка научным руководителем

Рекомендуется согласовать с научным руководителем:

- формулировки объекта, предмета, цели и задач;
- формулировку научной новизны;
- положения, выносимые на защиту;
- допустимость англоязычных технических терминов `pipeline`, `summary`, `quiz`, `baseline`, `local-first`, `human-in-the-loop`;
- объём и глубину раздела о степени разработанности проблемы;
- необходимость расширения или сокращения ограничений работы;
- состав приложений и перенос технических деталей из основной части.

## 6. Какие формулировки нужно держать осторожными

В тексте необходимо сохранять следующие ограничения:

- система не является универсальным чат-ботом по законам;
- система не заменяет юридическую экспертизу;
- LLM не является обязательным ядром метода и может рассматриваться только как optional/fallback enhancement;
- результаты экспериментов относятся к prepared synthetic evaluation corpus;
- разметка является key-change annotation, а не full-document gold standard;
- rule-based significance-layer является explainable baseline и может overclassify editorial/noise changes;
- summary может содержать unsupported claims и требует контроля grounding;
- quiz generation требует approval workflow;
- strict end-to-end success rate = 0.8889 означает 8 из 9 important/critical changes на данном корпусе, а не универсальную гарантию;
- основной bottleneck — `pair_06_procedure_change`.

## 7. Что не входит в текущий черновик

В текущий черновик намеренно не входят:

- финальная библиография по ГОСТ;
- финальная DOCX/PDF-вёрстка;
- новые эксперименты или пересчёт метрик;
- изменение backend, алгоритмов или corpus;
- новые графики сверх уже подготовленных экспериментальных артефактов;
- полная enterprise-архитектура, BI/dashboard, полноценная LMS, OCR, RAG-first сценарий, LangGraph/agent runtime, external legal monitoring;
- переход к Фазе 26.
