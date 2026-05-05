# Project Scope

## 1. Краткое описание проекта

Проект — локальная интеллектуальная система для работы с нормативно-правовыми и внутренними регламентными документами. Система ориентирована не на общий юридический чат и не на замену внешних правовых систем, а на воспроизводимый прикладной pipeline анализа изменений между версиями одного документа и превращения этих изменений в обучающий контур для сотрудников.

Главный объект системы — `Document` и его `DocumentVersion`. Главный инженерный фокус — объяснимое сравнение редакций, выжимка значимых изменений, генерация проверочного квиза, утверждение квиза, прохождение сотрудником и получение результата.

## 2. MVP statement

В рамках MVP реализован полный локальный цикл:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

Эта формулировка является границей защищаемого MVP. До завершения научной упаковки проект не расширяется в сторону OCR-платформы, RAG-чата, LangGraph-first системы, enterprise BI, полноценной LMS или production-grade IAM/RBAC.

## 3. Core MVP scope

| Компонент | Где реализован | Статус | Роль в pipeline | Достаточно для MVP | Не расширяем сейчас |
|---|---|---|---|---|---|
| Document upload | `backend/documents/api/viewsets.py`, `backend/documents/services/ingestion.py`, `backend/documents/services/versioning.py`, `backend/documents/models.py` | in MVP | Создаёт документ и загружает исходные версии | Поддержаны локальные загрузки TXT/DOCX/PDF с текстовым слоем, валидация и duplicate guard | Не добавляем массовый импорт, внешние хранилища и сложные upload-процессы |
| Document versioning | `Document`, `DocumentVersion`, `current_version`, `version_number`, `services/versioning.py` | in MVP | Фиксирует последовательность редакций одного документа | Автонумерация версий, связь текущей версии с документом, защита от дублей | Не добавляем distributed version control и сложные ветки версий |
| Text extraction | `backend/documents/domain/text_extractors.py` | in MVP | Превращает файл версии в `extracted_text` | TXT, DOCX и PDF с извлекаемым текстовым слоем | OCR для сканов не входит |
| Normalization | `backend/documents/domain/text_processing.py` | in MVP | Готовит устойчивый текст для chunking, diff и аналитики | Безопасная нормализация без разрушения юридически значимой структуры | Не добавляем агрессивную семантическую перестройку текста |
| Structural chunks | `Chunk`, `chunk_by_structure_ru`, `rebuild_version_chunks`, `services/ingestion.py` | in MVP | Даёт структурные единицы сравнения редакций | Rule-based структурное разбиение с fallback-блоками | Не добавляем внешние embedding-модели как обязательный chunking |
| Version comparison | `backend/documents/domain/diff.py`, `services/workflows.py`, `VersionComparison`, `VersionChangeItem` | in MVP | Сравнивает две версии и материализует изменения | Chunk-based diff с document-text fallback и explainability-полями | Не расширяем в полноценный legal diff engine для всех форматов |
| Significance classification | `backend/documents/domain/change_enrichment.py`, `backend/documents/services/importance.py`, поля `semantic_type`, `significance_label`, `significance_score`, `requires_manual_review` | in MVP | Приоритизирует изменения для brief и quiz | Детерминированные rule-based признаки и объяснимые причины | Не обучаем собственную большую модель значимости |
| Summary / brief | `backend/documents/domain/diff_summary.py`, `Summary`, `materialize_comparison` | in MVP | Формирует краткую выжимку по приоритетным изменениям | Materialized `Summary.text` и `Summary.highlights` со ссылками на `VersionChangeItem` | Не делаем полный юридический отчёт или экспертное заключение |
| Quiz generation | `backend/documents/domain/diff_quiz.py`, `create_quiz_from_versions`, `GeneratedQuiz`, `Question`, `Choice` | in MVP | Превращает highlights в проверочный тест | Summary-aware single-choice генерация по значимым изменениям | Не расширяем до большой LMS и сложных типов обучения |
| Quiz workflow | `backend/documents/services/quiz_workflow.py`, compatibility wrappers в `services/workflows.py` | in MVP | Не даёт использовать тест без утверждения | `draft -> pending_review -> approved`, а также `rejected` и `superseded` | Не добавляем сложную ролевая маршрутизацию |
| Employee attempt | `backend/documents/services/quiz_attempts.py`, `QuizAttempt`, `Answer` | in MVP | Позволяет сотруднику пройти утверждённый quiz | Start/submit lifecycle, фиксация ответов и score snapshot | Не добавляем личные кабинеты и production user management |
| Result/reporting | `backend/documents/services/result_reporting.py`, API endpoints, demo templates | in MVP | Показывает результат попытки и агрегированный отчёт по quiz | Rule-based feedback, score, pass/fail, frequent errors, optional LLM enhancement | Не строим enterprise BI/dashboard |
| Demo UI | `backend/documents/demo/views.py`, `backend/documents/templates/demo/*` | in MVP | Показывает полный локальный сценарий комиссии | Django templates для dashboard, compare, quiz, attempt, report | Не переписываем в SPA и не делаем production UX |
| API | `backend/documents/api/*`, `backend/config/urls.py` | in MVP | Даёт программный доступ к основным операциям pipeline | DRF endpoints/viewsets для документов, версий, compare, quiz, attempts, reports | Не меняем крупно API-контракты до научной упаковки |
| Tests | `backend/documents/tests/*`, `scripts/test.sh` | in MVP | Подтверждают воспроизводимость бизнес-сценариев | Покрыты ingestion, normalization, chunking, diff, significance, quiz, workflow, attempts, reporting, demo | Не добавляем экспериментальные evaluation suites в Фазе 5 |
| Smoke | `scripts/demo_smoke.sh` | in MVP | Проверяет, что локальный demo-контур живой | Health, demo dashboard, create document, upload, text payload | Не превращаем smoke в полноценный E2E-фреймворк |

## 4. Optional enhancements

Optional enhancements усиливают качество результата, но не являются основанием работоспособности MVP.

| Enhancement | Где находится | Политика MVP |
|---|---|---|
| LLM result enhancement | `backend/documents/services/result_reporting.py`, `llm_result_enhancer.py`, `docs/architecture/llm-fallback-modes.md` | LLM является optional enhancement. `RESULT_LLM_ENABLED=False` — штатный deterministic fallback, а не ошибка. |
| Optional AI/entity enhancement | `backend/documents/domain/llm_entity_extraction.py`, `services/analysis.py` | Может дополнять rule-based extraction, но базовый контур анализа не зависит от внешнего API. |
| Semantic search / Qdrant | `backend/documents/services/search.py`, `docker-compose.yml` profile `search` | Опциональный поиск, не обязательный для сценария «версия → результат». |
| Docker Compose | `docker-compose.yml`, `backend/Dockerfile`, `infra/.env.example` | Помогает воспроизводимости, но локальный запуск Django остаётся достаточным для MVP. |
| Advanced reporting text | `result_reporting.py` | Дополняет человекочитаемый feedback, но score/result/report payload формируются детерминированно. |

## 5. Explicitly out of scope

| Компонент | Почему вне MVP | Почему не мешает защите | Куда отнести |
|---|---|---|---|
| Полноценный LangGraph / multi-agent | Исследовательский объект проекта — version-first pipeline, а не агентная оркестрация | Полный локальный цикл уже реализован без агентной платформы | future work / out of scope |
| Полноценный RAG-чат | MVP не является чат-ботом; ценность в анализе изменений между редакциями | Комиссии демонстрируется конкретный traceable pipeline, а не свободный диалог | future work |
| Интеграция с Консультант+ | Требует внешних договорённостей, API/лицензий и другого масштаба продукта | Система анализирует загруженные пользователем документы локально | future work / external integration |
| OCR | Задача MVP — анализ текстового слоя и структурных изменений | PDF без текстового слоя честно признаются ограничением | limitation / future work |
| Auth/RBAC | В MVP роли сценарные, а не production-grade | Для защиты достаточно показать lifecycle и запрет прохождения неутверждённого quiz | future work |
| Enterprise BI/dashboard | Не относится к научному ядру chunking/diff/significance/quiz | Result/reporting уже показывает необходимые итоги attempts | future work |
| Большая LMS | Проект проверяет усвоение изменений, а не заменяет корпоративное обучение | Single scenario knowledge-check достаточен для MVP | out of scope / future work |
| Обучение собственной большой модели | Требует отдельного корпуса, инфраструктуры и методологии | MVP основан на объяснимом deterministic/hybrid baseline | future work после экспериментов |
| Все ФЗ России | Проект не является мониторингом всей законодательной базы | Защищается локальный анализ версий конкретного документа | out of scope |
| Мониторинг внешних источников законодательства | Это отдельная интеграционная задача | Пользовательский upload уже покрывает входной канал MVP | future work |
| Distributed/cloud-first deployment | MVP local-first и demo-ready | Локальная воспроизводимость важнее production topology | out of scope |
| Production-grade user management | Требует отдельного security/product scope | Сценарные роли достаточны для демонстрации workflow | future work |

## 6. Future work

После защиты или после завершения научной упаковки могут рассматриваться:

- OCR для сканированных PDF;
- RAG-чат по корпусу документов;
- LangGraph/multi-agent orchestration для сложных workflow;
- интеграции с внешними правовыми системами;
- production auth/RBAC и личные кабинеты;
- расширенная BI-аналитика;
- LMS-интеграции;
- внешний мониторинг изменений законодательства;
- cloud/distributed deployment;
- обучение или дообучение специализированных моделей при наличии формального evaluation corpus.

Эти направления не входят в текущий MVP и не должны блокировать переход к Фазе 6.

## 7. Ограничения MVP

- Поддерживаются TXT, DOCX и PDF с извлекаемым текстовым слоем; OCR не поддерживается.
- Сравнение выполняется для двух версий одного `Document`, а не для произвольной базы законов.
- Significance classification является deterministic rule-based baseline с explainability и `requires_manual_review` для неоднозначных случаев.
- Quiz generation ориентирован на `single_choice` и summary-aware highlights.
- UI является demo-ready Django templates, а не production-grade frontend.
- Роли заданы сценарием workflow, а не полноценной auth/RBAC-моделью.
- LLM/semantic search/Qdrant являются optional, а не обязательным ядром.
- Docker помогает воспроизводимости, но основной local-first запуск остаётся допустимым.

## 8. Что больше не расширяем до завершения научной упаковки

До завершения фаз научной формализации, экспериментов и подготовки защиты не добавляем:

- новые продуктовые модули вне pipeline «версия → результат»;
- новые модели БД и миграции без критической необходимости;
- OCR, RAG-chat, LangGraph, внешние legal integrations;
- production auth/RBAC;
- enterprise dashboard/BI;
- большую LMS-логику;
- крупное переписывание API или demo UI;
- создание demo/evaluation corpus в рамках Фазы 5;
- экспериментальные оценки, которые относятся к будущим фазам.

## 9. Связь MVP с диссертацией

MVP достаточен для магистерской работы, потому что он реализует полный воспроизводимый цикл обработки версий нормативного или регламентного документа:

1. входной документ материализуется как версия;
2. текст извлекается и нормализуется;
3. документ разбивается на структурные фрагменты;
4. редакции сравниваются через explainable diff;
5. изменения классифицируются по значимости;
6. формируется выжимка по приоритетным изменениям;
7. генерируется проверочный тест;
8. тест проходит approval workflow;
9. сотрудник проходит попытку;
10. система фиксирует результат и отчёт.

Это даёт основу для дальнейших научных фаз: формализации гибридного метода, архитектуры, chunking, diff, significance, quiz generation и экспериментальной проверки качества.

## 10. Итог

MVP scope заморожен. Защищаемая система — локальный, version-first, deterministic/hybrid-first pipeline:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

Все функции, не усиливающие этот цикл напрямую, относятся к optional enhancements, limitations или future work и не расширяются до завершения научной упаковки.
