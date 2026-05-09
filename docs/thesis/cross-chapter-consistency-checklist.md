# Cross-Chapter Consistency Checklist

## 1. Проверка наличия исходных файлов

| Группа | Файлы | Статус |
|---|---|---|
| Drafts | `chapter-1-draft.md`, `chapter-2-draft.md`, `chapter-3-draft.md` | checked |
| Source maps | `chapter-1-source-map.md`, `chapter-2-source-map.md`, `chapter-3-source-map.md` | checked |
| Review notes | `chapter-1-review-notes.md`, `chapter-2-review-notes.md`, `chapter-3-review-notes.md` | checked |
| Figures/tables maps | `chapter-1-figures-and-tables-map.md`, `chapter-2-figures-and-tables-map.md`, `chapter-3-figures-and-tables-map.md` | checked |
| Research docs | `hybrid-method.md`, `structural-chunking-method.md`, `version-comparison-method.md`, `significance-method.md`, `quiz-generation-method.md` | checked |
| Architecture docs | `system-architecture.md`, `erd.md`, `service-boundaries.md` | checked |
| Experiment docs | `final-method-evaluation.md`, `final-figures-and-tables.md`, `README.md` | checked |
| Scope docs | `mvp-freeze.md`, `PROJECT_SCOPE.md`, `README.md` | checked |

## 2. Логическая цепочка глав

| Связка | Проверка | Статус | Комментарий |
|---|---|---|---|
| Глава 1: актуальность → проблема → требования → цель и задачи | Последовательность присутствует в разделах 1.1–1.9 | pass | Глава 1 подводит к необходимости version-first pipeline и human-in-the-loop |
| Глава 2: метод → архитектура → реализация pipeline | Разделы 2.1–2.13 раскрывают метод `M`, модель данных, слои и workflow | pass | Архитектурная часть не выходит за MVP scope |
| Глава 3: corpus → эксперименты → результаты → ограничения | Разделы 3.1–3.12 описывают evaluation corpus, component-level experiments, end-to-end и threats to validity | pass | Выводы ограничены synthetic evaluation corpus |
| Переход 1 → 2 | Требования главы 1 соответствуют этапам и архитектуре главы 2 | pass | Добавлена переходная фраза в `integrated-main-draft.md` |
| Переход 2 → 3 | Компоненты главы 2 являются объектами экспериментальной оценки главы 3 | pass | Добавлена переходная фраза в `integrated-main-draft.md` |

## 3. Объект, предмет, цель и задачи

| Элемент | Итоговая формулировка | Статус |
|---|---|---|
| Объект | Объект исследования — процессы анализа изменений нормативно-правовых и внутренних регламентных документов в информационных системах организации. | aligned |
| Предмет | Предмет исследования — методы и программные средства структурного анализа редакций документов, оценки значимости изменений и формирования контрольно-обучающих материалов для сотрудников. | aligned |
| Цель | Цель работы — разработать и экспериментально оценить локальную интеллектуальную информационную систему, реализующую гибридный метод анализа изменений нормативных и регламентных документов и формирования контрольно-обучающих материалов по значимым изменениям. | aligned |
| Задачи | Задачи 1–10 в разделе 1.7 покрывают анализ предметной области, требования, метод, архитектуру, реализацию pipeline, evaluation corpus и экспериментальную оценку. | aligned |

## 4. Метод M = <E, N, S, C, P, G, R>

| Этап | Значение | Глава 1 | Глава 2 | Глава 3 | Статус |
|---|---|---|---|---|---|
| `E` | extraction текста из документа | Упомянут как часть целевого метода | Описан в 2.2 и 2.5 | Не оценивается отдельно; ограничение extraction/OCR указано | aligned |
| `N` | normalization текста | Упомянут как часть целевого метода | Описан в 2.2 и 2.5 | Не оценивается отдельно; влияет на downstream | aligned |
| `S` | structural chunking | Обоснован через специфику структуры документов | Подробно описан в 2.2 и 2.5 | Оценивается в 3.4 | aligned |
| `C` | comparison / сравнение редакций | Обоснован как задача выявления изменений | Описан в 2.2 и 2.6 | Оценивается в 3.5 | aligned |
| `P` | prioritization / significance | Обоснован как оценка значимости | Описан в 2.2 и 2.7 | Оценивается в 3.6 | aligned |
| `G` | generation of summary and quiz | Упомянут как summary + quiz generation | Описан в 2.8 и 2.9 | Оценивается в 3.7 и 3.8 | aligned |
| `R` | result fixation | Упомянут как result/reporting | Описан в 2.10 | Присутствует в end-to-end scenario, но не является отдельной NLP-метрикой | aligned with limitation |

## 5. Терминологическая проверка

| Терминологическая зона | Итоговое правило | Статус |
|---|---|---|
| comparison / diff | Этап метода — comparison / сравнение редакций; diff — технический результат или baseline | checked |
| significance / importance | В тексте использовать «significance / значимость»; `importance` оставлять только при привязке к артефактам | checked |
| summary / выжимка | Использовать `summary-layer` / «человеко-читаемая выжимка» | checked |
| quiz / тест | Использовать «контрольно-обучающие материалы» и `generated quiz`; подчёркивать approval | checked |
| LLM | Optional enhancement/fallback, не ядро метода | checked |
| local-first | Локальная воспроизводимая архитектура MVP | checked |

## 6. Рисунки и таблицы

| Глава | Материалы | Статус | Комментарий |
|---|---|---|---|
| Глава 1 | Таблица 1.1, Таблица 1.2 | included | Нумерация может быть сохранена или обновлена при финальной сборке |
| Глава 1 | Рисунки 1.1–1.3 | placeholders | Требуется ручная подготовка, если научный руководитель сочтёт нужным |
| Глава 2 | Таблица 2.1 | included | Таблица этапов метода уже в тексте |
| Глава 2 | Рисунки 2.1–2.5 | placeholders | Mermaid/ERD нужно отрендерить и вставить при финальной вёрстке |
| Глава 2 | Таблицы 2.2–2.3 | optional placeholders | Можно добавить для связи архитектуры и ограничений MVP |
| Глава 3 | Таблицы 3.1–3.9 | included / placeholders by source | Требуется финальная нумерация после общей сборки |
| Глава 3 | Рисунки 3.1–3.5 | placeholders | PNG есть в `experiments/final_visuals/figures/`, нужно вставить вручную в финальный DOCX/PDF |

## 7. Осторожность научных утверждений

| Проверка | Статус | Комментарий |
|---|---|---|
| Нет утверждения, что система заменяет эксперта | pass | В главах явно указано, что экспертная проверка остаётся за человеком |
| Нет утверждения, что метод универсален для всех нормативных документов | pass | Выводы ограничены MVP и evaluation corpus |
| Нет утверждения, что LLM гарантирует качество анализа | pass | LLM описывается как optional enhancement/fallback |
| Нет утверждения, что quiz generation всегда создаёт корректные вопросы | pass | Approval workflow указан как обязательный quality gate |
| Метрики главы 3 не интерпретируются как промышленный benchmark | pass | Указаны synthetic corpus, key-change annotation и threats to validity |

## 8. Библиографические placeholders

| Категория | Статус |
|---|---|
| Электронный документооборот / DMS | required |
| Document comparison / diff algorithms | required |
| Legal NLP / document intelligence | required |
| LLM reliability / hallucinations | required |
| Human-in-the-loop systems | required |
| Compliance learning / employee training | required |
| Evaluation methodology for NLP/document systems | required |

## 9. Финальная нумерация

- [ ] Проверить сквозную нумерацию рисунков и таблиц после объединения глав.
- [ ] Заменить placeholders `[источник: ...]` на реальные ссылки по ГОСТ.
- [ ] Проверить, нужно ли переносить крупные таблицы главы 3 в приложение.
- [ ] Проверить, что подписи рисунков соответствуют требованиям кафедры.
- [ ] Проверить, что Mermaid/PNG/ERD корректно отображаются в финальной сборке.
