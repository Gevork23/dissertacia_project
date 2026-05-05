# MVP Freeze

## 1. Цель документа

Документ фиксирует границы MVP после завершения технической стабилизации Фаз 1–4 и самой Фазы 5. Его задача — остановить scope creep, отделить реализованный core MVP от optional enhancements и future work, а также дать устойчивую формулировку проекта для научной упаковки и защиты.

## 2. Почему MVP нужно заморозить

Проект уже содержит полный локальный pipeline работы с версиями документа. Без явной заморозки он может расползаться в сторону OCR, RAG-чата, LangGraph, enterprise BI, LMS, внешних legal integrations и production auth/RBAC. Эти направления потенциально полезны, но они меняют масштаб задачи и мешают защищать уже реализованную систему как завершённый, воспроизводимый и научно объяснимый MVP.

Заморозка нужна, чтобы:

- проект не обещал больше, чем реально реализовано;
- комиссия видела завершённый локальный цикл, а не бесконечный backlog;
- ROADMAP и TASKS показывали переход к научной формализации, экспериментам и защите;
- optional/future work не смешивались с core MVP;
- можно было уверенно отвечать на вопрос «почему нет X?».

## 3. Состояние проекта после Фаз 1–4

По архиву после Фазы 4 обнаружены следующие документы и области:

- `PROJECT_SCOPE.md` — существовал, но требовал более жёсткого разделения core / optional / future work;
- `ROADMAP.md` — существовал, но выглядел как функциональная дорожная карта продолжающейся разработки;
- `TASKS.md` — существовал, но смешивал завершённый MVP, частичные продуктовые статусы и будущие доработки;
- `README.md` — в целом уже фиксировал version-first подход и ограничения;
- `ARCHITECTURE.md` — в целом уже фиксировал local-first, deterministic/hybrid-first и out-of-scope ограничения;
- `docs/architecture/service-boundaries.md` — фиксировал нормализацию service layer после Фазы 3;
- `docs/architecture/llm-fallback-modes.md` — фиксировал deterministic fallback как штатный режим после Фазы 4;
- `docs/audit/repository-cleanup.md` — фиксировал cleanup после Фазы 2;
- `docs/audit/current-state-audit.md` — в архиве не найден.

Кодовая база содержит Django backend, DRF API, demo UI, service/domain layers, тесты и smoke-скрипт. Фактическая реализация соответствует core pipeline MVP.

### 3.1. Scope-аудит фактической реализации

| Компонент | Реализован | Статус MVP | Где находится | Комментарий |
|---|---|---|---|---|
| Document upload | yes | in MVP | `api/viewsets.py`, `services/ingestion.py`, `services/versioning.py` | Достаточно для локальной загрузки документа и новых версий. |
| Versioning | yes | in MVP | `Document`, `DocumentVersion`, `services/versioning.py` | Поддерживает последовательность редакций одного документа и `current_version`. |
| Extraction | yes | in MVP | `domain/text_extractors.py` | TXT/DOCX/PDF с текстовым слоем; сканы без текстового слоя не поддерживаются. |
| Normalization | yes | in MVP | `domain/text_processing.py` | Безопасная нормализация для downstream chunking/diff. |
| Structural chunking | yes | in MVP | `Chunk`, `chunk_by_structure_ru`, `services/ingestion.py` | Rule-based structural chunks с fallback-блоками. |
| Version comparison | yes | in MVP | `domain/diff.py`, `VersionComparison`, `VersionChangeItem` | Chunk-based diff с document-text fallback. |
| Significance classification | yes | in MVP | `domain/change_enrichment.py`, `services/importance.py` | Explainable deterministic baseline. |
| Summary / brief | yes | in MVP | `domain/diff_summary.py`, `Summary` | Приоритетная выжимка по `VersionChangeItem`. |
| Quiz generation | yes | in MVP | `domain/diff_quiz.py`, `GeneratedQuiz`, `Question`, `Choice` | Summary-aware single-choice runtime contour. |
| Quiz approval workflow | yes | in MVP | `services/quiz_workflow.py` | `draft`, `pending_review`, `approved`, `rejected`, `superseded`. |
| Employee attempt | yes | in MVP | `services/quiz_attempts.py`, `QuizAttempt`, `Answer` | Start/submit lifecycle, score snapshot. |
| Result/reporting | yes | in MVP | `services/result_reporting.py`, API/demo views | Deterministic reporting, optional LLM enhancement. |
| Demo UI | yes | in MVP | `documents/demo/views.py`, `templates/demo/*` | Достаточно для защиты полного сценария, не production frontend. |
| API | yes | in MVP | `documents/api/*`, `config/urls.py` | Покрывает documents, versions, compare, quiz, attempts, reports. |
| Tests | yes | in MVP | `documents/tests/*`, `scripts/test.sh` | Покрывают основные backend-сценарии. |
| Smoke | yes | in MVP | `scripts/demo_smoke.sh` | Проверяет health, demo dashboard, create document, upload, text payload. |
| LLM result enhancement | partial | optional enhancement | `services/result_reporting.py`, `services/llm_result_enhancer.py` | Не обязателен; disabled mode является штатным fallback. |
| Semantic search / Qdrant | partial | optional enhancement | `services/search.py`, `docker-compose.yml` | Не входит в основной pipeline; может использоваться отдельно. |
| OCR | no | out of scope | — | Future work для сканированных PDF. |
| Full RAG-chat | no | out of scope | — | Не нужен для version-first MVP. |
| LangGraph / agents | no | out of scope | — | Не нужен для deterministic workflow MVP. |
| Auth/RBAC | no | future work | — | В MVP роли сценарные, не production-grade. |
| Enterprise BI / LMS | no | out of scope | — | Result/reporting и knowledge-check достаточны для MVP. |
| Consultant+ integration | no | future work | — | Внешняя интеграция требует отдельного product/legal scope. |

## 4. MVP statement

В рамках MVP реализован полный локальный цикл:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

Это главный защищаемый scope. Всё, что не усиливает этот цикл напрямую, является optional enhancement, limitation или future work.

## 5. Что входит в MVP

| Компонент | Назначение | Статус | Где реализован |
|---|---|---|---|
| Document upload | Загрузка документа и версий | in MVP | `backend/documents/api/viewsets.py`, `services/ingestion.py`, `services/versioning.py` |
| Versioning | Хранение версий одного документа и текущей версии | in MVP | `Document`, `DocumentVersion`, `services/versioning.py` |
| Extraction | Получение текста из TXT/DOCX/PDF с текстовым слоем | in MVP | `domain/text_extractors.py` |
| Normalization | Подготовка текста для chunking и diff | in MVP | `domain/text_processing.py` |
| Structural chunks | Структурные единицы анализа редакций | in MVP | `Chunk`, `chunk_by_structure_ru`, `rebuild_version_chunks` |
| Version comparison | Сравнение двух редакций и materialized diff | in MVP | `domain/diff.py`, `VersionComparison`, `VersionChangeItem`, `services/workflows.py` |
| Significance | Rule-based классификация и приоритизация изменений | in MVP | `domain/change_enrichment.py`, `services/importance.py` |
| Summary | Краткая выжимка по приоритетным изменениям | in MVP | `domain/diff_summary.py`, `Summary` |
| Quiz generation | Генерация проверочного теста по highlights | in MVP | `domain/diff_quiz.py`, `GeneratedQuiz`, `Question`, `Choice` |
| Quiz workflow | Review/approval lifecycle теста | in MVP | `services/quiz_workflow.py`, wrappers в `services/workflows.py` |
| Attempt | Прохождение утверждённого теста сотрудником | in MVP | `services/quiz_attempts.py`, `QuizAttempt`, `Answer` |
| Result/reporting | Score, результат попытки, report payload | in MVP | `services/result_reporting.py`, API/demo endpoints |
| Demo UI | Демонстрация полного сценария на одном ПК | in MVP | `backend/documents/demo/views.py`, `templates/demo/*` |
| API | Программный контур работы с документами, compare, quiz, attempts, reports | in MVP | `backend/documents/api/*` |
| Tests | Регрессионная проверка ключевой бизнес-логики | in MVP | `backend/documents/tests/*`, `scripts/test.sh` |
| Smoke | Быстрая проверка локальной работоспособности | in MVP | `scripts/demo_smoke.sh` |

## 6. Что не входит в MVP

| Компонент | Почему вне scope | Как объяснять | Возможное future work |
|---|---|---|---|
| OCR | Исследовательская задача связана с текстовым слоем и структурными изменениями, а не с распознаванием изображений | PDF без текстового слоя — честное ограничение MVP | Добавить OCR pipeline после защиты |
| Full RAG-chat | MVP version-first, а не chat-first | Система отвечает на вопрос «что изменилось между версиями», а не ведёт свободный юридический диалог | RAG по корпусу документов |
| LangGraph / agents | Агентная оркестрация не нужна для локального deterministic pipeline | Текущий workflow уже воспроизводим и объясним без multi-agent runtime | Agent workflow для сложных сценариев |
| Консультант+ integration | Требует внешних API/лицензий и меняет масштаб продукта | MVP анализирует загруженные документы локально | Внешние legal integrations |
| Auth/RBAC | Роли в MVP сценарные, а не production-grade | Approval/attempt ограничения уже показывают workflow без сложной IAM | Production user management |
| Enterprise BI | Не относится к научному ядру | Result/reporting достаточно для демонстрации результатов | Advanced analytics/dashboard |
| Большая LMS | Проект не заменяет корпоративную платформу обучения | Knowledge-check по изменениям достаточен для MVP | LMS-интеграция |
| Все ФЗ России | Это задача мониторинга и большого корпуса | MVP работает с конкретными документами и их версиями | Corpus/external monitoring |
| External legal monitoring | Требует отдельного источника данных и расписаний | Upload/versioning покрывает входной канал MVP | Мониторинг внешних источников |
| Training custom LLM | Требует корпуса, вычислений и отдельной методологии | Explainable rule-based/hybrid baseline достаточен для защиты | Исследовательское ML-направление |
| Cloud/distributed deployment | MVP local-first и demo-ready | Локальный запуск лучше отвечает требованиям воспроизводимости | Production deployment |

## 7. Core pipeline

Core pipeline фиксируется так:

1. Оператор создаёт `Document` и загружает `DocumentVersion`.
2. Система извлекает текст в `extracted_text`.
3. Текст нормализуется в `normalized_text`.
4. Версия материализуется в `Chunk`.
5. Две версии одного документа сравниваются в `VersionComparison`.
6. Изменения сохраняются как `VersionChangeItem`.
7. Rule-based significance layer присваивает типы, уровни значимости, причины и manual-review flags.
8. `Summary` формирует выжимку по приоритетным изменениям.
9. `GeneratedQuiz` строится по `Summary.highlights`.
10. Quiz проходит review/approval workflow.
11. Сотрудник проходит утверждённый quiz.
12. `QuizAttempt` и `Answer` фиксируют результат.
13. Reporting layer возвращает результат попытки и отчёт.

## 8. Optional enhancement policy

Optional enhancement можно использовать только если он:

- не ломает deterministic baseline;
- имеет безопасный fallback;
- не становится обязательной внешней зависимостью demo;
- не меняет защищаемый MVP statement;
- не требует новых моделей БД, больших API-изменений или product scope expansion в Фазе 5.

## 9. LLM policy

LLM — optional enhancement. Deterministic fallback является штатным режимом.

`RESULT_LLM_ENABLED=False` не считается ошибкой. В этом режиме result/reporting формируются локально и воспроизводимо. При включённом LLM enhancement failure не должен ломать user workflow: система возвращается к deterministic fallback и логирует ситуацию как fallback включённого enhancement.

Фаза 5 не добавляет новых LLM-провайдеров, RAG, LangGraph, retry/circuit breaker или agent architecture.

## 10. Demo-ready boundary

Demo-ready boundary означает, что можно показать один цельный локальный сценарий:

- открыть demo UI;
- выбрать документ и версии;
- сравнить редакции;
- увидеть изменения и brief;
- сгенерировать quiz;
- отправить quiz на review;
- утвердить quiz;
- пройти quiz от имени сотрудника;
- увидеть result/report.

Demo UI не обязан быть production frontend. Его задача — стабильно показать core pipeline.

## 11. Research boundary

Научная граница проекта проходит по методам:

- структурное представление документа;
- сравнение редакций;
- классификация значимости изменений;
- explainable summary;
- generation of knowledge-check quiz по изменениям;
- воспроизводимая оценка результатов в следующих фазах.

OCR, RAG, LangGraph, external integrations и production RBAC не входят в исследовательское ядро текущего MVP.

## 12. Engineering boundary

Фаза 5 является документационно-инженерной заморозкой scope. В ней не создаются:

- новые Django apps;
- новые модели и миграции;
- новые product modules;
- demo corpus или evaluation corpus;
- экспериментальные метрики;
- крупные API changes;
- новая архитектура UI.

Допустимы только минимальные документационные изменения, которые устраняют scope creep и синхронизируют PROJECT_SCOPE, ROADMAP, TASKS и mvp-freeze.

## 13. Future work

После защиты или отдельного product/research decision возможны:

- OCR;
- RAG-chat;
- LangGraph/multi-agent orchestration;
- Консультант+ / external legal integrations;
- external legal monitoring;
- production auth/RBAC;
- enterprise BI/dashboard;
- LMS integration;
- distributed/cloud-first deployment;
- custom model training/fine-tuning.

## 14. Риски scope creep

| Риск | Почему опасен | Решение Фазы 5 |
|---|---|---|
| Добавить OCR «для полноты» | Уводит в computer vision/document recognition | Зафиксировать как future work |
| Добавить RAG-chat | Меняет продукт с version comparison на chat assistant | Зафиксировать chat как out of scope |
| Сделать LangGraph-first architecture | Усложняет систему без необходимости для MVP | Оставить deterministic workflow |
| Развить BI/dashboard | Переключает фокус с метода на enterprise reporting | Оставить basic reporting |
| Сделать production auth/RBAC | Требует отдельного security scope | Оставить сценарные роли |
| Создать evaluation corpus в Фазе 5 | Смешивает scope freeze и эксперименты | Перенести в experiment block |
| Переписать UI/API | Риск регрессий перед научной упаковкой | Не менять без критической необходимости |

## 15. Что больше не добавляем до защиты

До завершения научной упаковки и защиты не добавляем:

- OCR;
- RAG-chat;
- LangGraph-first workflow;
- external legal integrations;
- auth/RBAC;
- enterprise BI;
- LMS;
- новые модели БД и миграции;
- крупные API rewrites;
- production frontend;
- demo/evaluation corpus в рамках scope freeze;
- обучение собственной модели.

## 16. Итоговая формулировка MVP

В рамках MVP реализован полный локальный цикл:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

MVP является завершённым в инженерных границах, достаточным для перехода к Фазе 6 — формализации гибридного метода. Дальнейшие этапы должны заниматься научной упаковкой, экспериментами, главами и защитой, а не бесконечным расширением продукта.
