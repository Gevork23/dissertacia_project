# Chapter 2 Review Notes

## 1. Что уже готово

- Создан черновик `docs/thesis/chapter-2-draft.md` с разделами 2.1–2.13.
- В главу включена формализация гибридного метода `M = <E, N, S, C, P, G, R>`.
- Описаны архитектурные слои: Presentation layer, Application layer, Domain layer, Persistence layer, Optional AI layer, Infrastructure layer.
- Описана модель данных и идея materialized artifacts.
- Описаны preprocessing, structural chunking, comparison, significance-layer, summary-layer и quiz generation.
- Описан workflow approval/attempt/result без утверждения, что реализована enterprise RBAC-система.
- Включены ограничения MVP: нет OCR, нет full legal expertise, нет enterprise RBAC, нет BI/dashboard, LLM optional/fallback, local-first deployment.
- Создана карта источников `docs/thesis/chapter-2-source-map.md`.
- Создана карта рисунков и таблиц `docs/thesis/chapter-2-figures-and-tables-map.md`.

## 2. Какие места требуют ручной проверки

- Проверить, соответствует ли объём главы требованиям кафедры и методическим указаниям.
- Проверить, нужно ли переводить англоязычные термины `pipeline`, `summary`, `quiz`, `baseline`, `human-in-the-loop`, `local-first` или оставить их как технические термины проекта.
- Уточнить у научного руководителя, допустимо ли оставлять названия моделей и полей в backticks внутри основного текста диссертации.
- Проверить нумерацию рисунков после вставки диаграмм из `.mmd` в финальную версию.
- Проверить, нужно ли часть технической модели данных вынести в приложение, если глава станет слишком объёмной.
- Перед финальной сдачей сверить текст с актуальным локальным repository после переноса файлов из данного артефакта.

## 3. Где нужно вставить рисунки

| Рисунок | Файл / источник | Рекомендуемый раздел | Назначение |
|---|---|---|---|
| Рисунок 2.1 | `docs/architecture/diagrams/pipeline.mmd` | 2.2 | Общий pipeline метода |
| Рисунок 2.2 | `docs/architecture/diagrams/system-overview.mmd` | 2.3 | Общая архитектура системы |
| Рисунок 2.3 | `docs/architecture/diagrams/component-diagram.mmd` | 2.3 | Компоненты и слои системы |
| Рисунок 2.4 | `docs/architecture/diagrams/full-scenario-sequence.mmd` | 2.3 / 2.10 | Полный пользовательский сценарий |
| Рисунок 2.5 | `docs/architecture/erd.md` | 2.4 | ERD ключевых сущностей |

## 4. Где нужно вставить таблицы

| Таблица | Основа | Рекомендуемый раздел | Назначение |
|---|---|---|---|
| Таблица 2.1 | `docs/research/hybrid-method.md`, `chapter-2-draft.md` | 2.2 | Этапы гибридного метода |
| Таблица 2.2 | `docs/architecture/system-architecture.md` | 2.3 / 2.4 | Связь этапов метода с архитектурными компонентами, если потребуется |
| Таблица 2.3 | `docs/scope/mvp-freeze.md` | 2.12 | Ограничения MVP, если нужно вынести ограничения в табличный вид |

## 5. Какие термины нужно унифицировать

- `structural chunking` / структурное разбиение / structural segmentation.
- `structural chunks` / структурные фрагменты / `Chunk`.
- `path_key` как структурный ключ фрагмента.
- `comparison` / сравнение редакций / `VersionComparison`.
- `change item` / изменение / `VersionChangeItem`.
- `significance-layer` / слой оценки значимости / этап `P`.
- `summary-layer` / человеко-читаемая выжимка / `Summary`.
- `quiz generation` / генерация контрольно-обучающих материалов.
- `human-in-the-loop` / утверждение ответственным лицом.
- `materialized artifacts` / материализованные промежуточные артефакты.
- `local-first` / локальная воспроизводимая архитектура.

## 6. Какие формулировки нужно держать осторожными

- Писать: «система поддерживает анализ изменений», а не «система заменяет юридическую экспертизу».
- Писать: «rule-based/deterministic baseline», а не «идеально определяет значимость».
- Писать: «summary помогает интерпретировать diff/significance», а не «формирует юридическое заключение».
- Писать: «generated quiz требует approval», а не «автоматически создаёт полностью корректные учебные материалы».
- Писать: «LLM является optional enhancement/fallback layer», а не «LLM является ядром всей системы».
- Писать: «local-first MVP», а не «готовая production cloud platform».
- Писать: «результаты главы 3 применимы к подготовленному evaluation corpus», а не «метод универсален для всех документов».

## 7. Что нужно согласовать с главой 3

- Названия этапов `S`, `C`, `P`, `G-summary`, `G-quiz` должны совпадать с главой 3.
- В главе 2 не заявлять компонентов, которые не оценивались и не реализованы: OCR, RAG, LangGraph, enterprise RBAC, BI/dashboard.
- Ограничения significance-layer должны совпадать с выводами главы 3 про overclassification.
- Ограничения quiz generation должны совпадать с выводами главы 3 про approval workflow и correct/relevant question rate.
- Summary-layer нужно описывать как downstream от diff/significance, потому что глава 3 показывает зависимость summary от upstream representation.
- Не утверждать, что structural chunking является full-document segmentation gold standard; глава 3 оценивает selected key-boundary annotation.
- Сохранить формулировку, что end-to-end результат подтверждает применимость в рамках MVP, но не доказывает универсальность метода.
