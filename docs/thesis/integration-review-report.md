# Integration Review Report for Chapters 1–3

## 1. Проверенные документы

Проверены и использованы следующие документы:

- `docs/thesis/chapter-1-draft.md`
- `docs/thesis/chapter-1-source-map.md`
- `docs/thesis/chapter-1-review-notes.md`
- `docs/thesis/chapter-1-figures-and-tables-map.md`
- `docs/thesis/chapter-2-draft.md`
- `docs/thesis/chapter-2-source-map.md`
- `docs/thesis/chapter-2-review-notes.md`
- `docs/thesis/chapter-2-figures-and-tables-map.md`
- `docs/thesis/chapter-3-draft.md`
- `docs/thesis/chapter-3-source-map.md`
- `docs/thesis/chapter-3-review-notes.md`
- `docs/thesis/chapter-3-figures-and-tables-map.md`
- `docs/research/hybrid-method.md`
- `docs/research/structural-chunking-method.md`
- `docs/research/version-comparison-method.md`
- `docs/research/significance-method.md`
- `docs/research/quiz-generation-method.md`
- `docs/architecture/system-architecture.md`
- `docs/architecture/erd.md`
- `docs/architecture/service-boundaries.md`
- `docs/experiments/final-method-evaluation.md`
- `docs/experiments/final-figures-and-tables.md`
- `docs/experiments/README.md`
- `docs/scope/mvp-freeze.md`
- `PROJECT_SCOPE.md`
- `README.md`

## 2. Логическая связность глав

Глава 1 выстроена по цепочке: актуальность задачи анализа изменений → специфика нормативно-правовых и внутренних регламентных документов → проблемы ручного отслеживания → анализ классов существующих решений → требования → объект, предмет, цель и задачи → постановка задачи разработки системы.

Глава 2 раскрывает заявленное в главе 1 проектное решение: формализует гибридный метод `M = <E, N, S, C, P, G, R>`, описывает local-first архитектуру, модель данных, materialized artifacts, structural chunking, comparison, significance-layer, summary-layer, quiz generation, approval workflow, result fixation и ограничения MVP.

Глава 3 оценивает именно те компоненты, которые описаны в главе 2: `S`, `C`, `P`, downstream-компоненты `G-summary` и `G-quiz`, а также integrated end-to-end прохождение important/critical changes. Ограничения главы 3 согласуются с ограничениями главы 2: synthetic corpus, key-change annotation, baseline nature significance/quiz, отсутствие OCR/PDF extraction variability и необходимость human-in-the-loop.

В `integrated-main-draft.md` добавлены короткие переходные фразы после глав 1 и 2, чтобы основной текст воспринимался как единый академический черновик.

## 3. Терминологическая согласованность

Создан `terminology-glossary.md`. Основные решения:

- этап метода называется `comparison` / «сравнение редакций», а `diff` используется для технического результата или baseline-подхода;
- для слоя `P` используется «significance-layer» / «слой оценки значимости», без хаотичного смешения с `importance`;
- `summary` трактуется как человеко-читаемая выжимка, а не юридическое заключение;
- `quiz generation` трактуется как генерация контрольно-обучающих материалов, требующих approval;
- `human-in-the-loop` закреплён как обязательный quality gate;
- `local-first` описывает локальную воспроизводимую архитектуру MVP;
- deterministic/rule-based baseline не подаётся как окончательная экспертная система.

## 4. Согласованность цели и задач

Формулировки объекта, предмета и цели в разделе 1.7 согласованы с главами 2–3:

- объект соответствует процессам анализа изменений документов в информационных системах организации;
- предмет соответствует методам и программным средствам structural analysis, significance assessment и generation of control-learning materials;
- цель соответствует разработке и экспериментальной оценке локальной интеллектуальной информационной системы;
- задачи 1–10 покрывают анализ предметной области, требования, разработку метода, архитектуру, pipeline, evaluation corpus и экспериментальную оценку.

Цель не формулируется как создание юридической экспертной системы или универсального legal chatbot.

## 5. Согласованность метода M = <E, N, S, C, P, G, R>

Метод описан последовательно:

| Этап | Смысл | Проверка |
|---|---|---|
| `E` | extraction текста из документа | Есть в главах 1–2; в главе 3 не оценивается отдельно, что указано как ограничение |
| `N` | normalization текста | Есть в главах 1–2; влияет на downstream pipeline |
| `S` | structural chunking | Подробно описан в главе 2 и оценён в разделе 3.4 |
| `C` | comparison / сравнение редакций | Подробно описан в главе 2 и оценён в разделе 3.5 |
| `P` | prioritization / significance | Подробно описан в главе 2 и оценён в разделе 3.6 |
| `G` | generation of summary and quiz | Описан в разделах 2.8–2.9 и оценён в 3.7–3.8 |
| `R` | result fixation | Описан в разделе 2.10; в главе 3 присутствует как часть end-to-end сценария и граница оценки |

Глава 1 упоминает метод как целевую постановку, глава 2 формализует метод, глава 3 оценивает метод экспериментально. Это соответствует требуемой логике.

## 6. Согласованность ограничений

Ограничения согласованы между главами:

- система не заменяет юридическую экспертизу;
- LLM не является обязательным ядром;
- MVP не включает OCR для сканированных документов;
- MVP не включает enterprise RBAC/IAM, BI/dashboard, полноценную LMS, LangGraph/agent runtime, external legal integrations и cloud/distributed deployment;
- significance-layer и quiz generation являются baseline-компонентами;
- generated quiz требует human-in-the-loop approval;
- результаты главы 3 ограничены synthetic evaluation corpus и key-change annotation.

## 7. Рисунки и таблицы

Карты рисунков и таблиц проверены.

| Глава | Материалы | Итог |
|---|---|---|
| 1 | Таблица 1.1, Таблица 1.2; optional Figures 1.1–1.3 | Таблицы включены, рисунки требуют ручной подготовки при финальной вёрстке |
| 2 | Таблица 2.1; Figures 2.1–2.5; optional Tables 2.2–2.3 | Таблица 2.1 включена, схемы Mermaid/ERD требуют финальной вставки |
| 3 | Таблицы 3.1–3.9; Figures 3.1–3.5 | Табличные данные и PNG-источники указаны, нужна финальная нумерация и вставка изображений |

Ссылки вида «Рисунок 3.x» и «Таблица 3.x» должны рассматриваться как placeholders до финальной сборки полного документа.

## 8. Библиографические placeholders

Создан `bibliography-placeholders.md`. Зафиксированы места, где нужны внешние источники, без выдумывания авторов и ГОСТ-записей. Основные категории: электронный документооборот, DMS, document comparison/diff, legal NLP, LLM reliability/hallucinations, human-in-the-loop, employee training/compliance learning, evaluation methodology.

## 9. Найденные проблемы

1. В главах 2–3 встречались внутренние ссылки на номера проектных фаз, что нежелательно для академического текста основной части диссертации.
2. В исходных notes сохранялась необходимость унифицировать `comparison/diff`, `significance/importance`, `summary/выжимка`, `quiz/тест`.
3. В главах оставлены placeholders для внешней библиографии.
4. Рисунки и часть таблиц требуют финальной вставки и нумерации при сборке DOCX/PDF.
5. В главе 3 нужно сохранять осторожную интерпретацию результатов из-за small synthetic corpus и key-change annotation.

## 10. Исправленные проблемы

1. Убраны фазовые формулировки из академического текста глав 2–3: заменены на нейтральные формулировки про зафиксированные экспериментальные артефакты, компонентные проверки и MVP scope.
2. В `integrated-main-draft.md` добавлены переходы после глав 1 и 2.
3. Создан терминологический глоссарий для единообразного употребления ключевых терминов.
4. Создана cross-chapter consistency checklist.
5. Создан файл bibliography placeholders.
6. Создан файл open issues для ручной проверки следующих фаз.

## 11. Что требует ручной проверки

- Подбор реальных внешних источников и оформление списка литературы по требованиям кафедры/ГОСТ.
- Финальная нумерация рисунков и таблиц после сборки полного текста диссертации.
- Вставка Mermaid/PNG/ERD-рисунков в финальный DOCX/PDF.
- Согласование формулировок объекта, предмета, цели и задач с научным руководителем.
- Решение, оставлять ли англоязычные технические термины `pipeline`, `summary`, `quiz`, `baseline`, `human-in-the-loop`, `local-first` или переводить часть из них.
- Проверка, нужно ли выносить крупные таблицы главы 3 в приложения.

## 12. Вывод

Главы 1–3 готовы как интегрированный академический черновик основной части диссертации. Логика «актуальность и требования → метод и архитектура → экспериментальная оценка» выдержана. Объект, предмет, цель и задачи согласованы с разработанным методом и экспериментальной частью. Метод `M = <E, N, S, C, P, G, R>` описан последовательно. Ограничения MVP и границы интерпретации результатов зафиксированы осторожно. Следующий содержательный шаг после Фазы 24 — Фаза 25: подготовка введения и заключения либо сборка полного черновика диссертации.
