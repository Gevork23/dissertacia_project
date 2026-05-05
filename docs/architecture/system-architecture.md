# System Architecture

## 1. Назначение документа

Документ формализует архитектуру разработанной информационной системы после Фазы 6. Его цель — показать, что проект реализован не как набор несвязанных функций, а как слоистая локальная интеллектуальная информационная система для работы с версиями нормативно-правовых и внутренних регламентных документов.

Документ предназначен для использования в подразделе диссертации **2.2. Архитектура разработанной информационной системы**. Он связывает фактическую структуру Django-проекта, модели данных, сервисы, pipeline обработки и формализованный гибридный метод:

```text
M = <E, N, S, C, P, G, R>
```

где `E` — extraction, `N` — normalization, `S` — structural segmentation, `C` — comparison, `P` — prioritization/significance, `G` — generation of control-learning materials, `R` — result fixation.

Документ не вводит новые функции, модели, миграции или экспериментальные контуры. Он описывает уже реализованный MVP.

## 2. Контекст системы

Система предназначена для локальной обработки документов, в которых существуют несколько редакций одного и того же регламентного или нормативно-правового текста. Ключевой пользовательский сценарий:

```text
document upload
→ document versioning
→ text extraction
→ normalization
→ structural chunking
→ version comparison
→ significance classification
→ summary
→ quiz generation
→ quiz approval workflow
→ employee attempt
→ result/reporting
```

MVP-формулировка системы:

```text
версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат
```

Система является **version-first**, а не chat-first. Основной объект обработки — `DocumentVersion`; основная аналитическая операция — сравнение двух версий одного `Document`; основной прикладной результат — утверждённый контрольный тест и зафиксированный результат его прохождения сотрудником.

## 3. Архитектурные цели

Архитектура системы преследует следующие цели:

1. **Воспроизводимость обработки.** Каждый ключевой этап pipeline оставляет материализованный артефакт в базе данных или в файловом хранилище.
2. **Трассируемость результата.** Итоговый тест и результат попытки можно связать с конкретными версиями документа, сравнением, изменениями и summary.
3. **Слоистое разделение ответственности.** Presentation, application/service, domain, persistence, optional AI и infrastructure имеют разные обязанности.
4. **Local-first runtime.** Система должна запускаться локально без обязательной зависимости от внешнего LLM, RAG, облака или enterprise-инфраструктуры.
5. **Deterministic/hybrid-first подход.** Базовый pipeline построен на детерминированной обработке и explainable rule-based baseline. LLM и semantic search являются опциональными усилителями, а не ядром MVP.
6. **Human-in-the-loop контроль.** Сгенерированный quiz не становится доступным сотрудникам до прохождения review/approval workflow ответственным лицом.
7. **Соответствие научному методу.** Реализация должна быть сопоставима с методом `M = <E, N, S, C, P, G, R>` и пригодна для объяснения комиссии.

## 4. Общая архитектура

Система реализована как Django backend с DRF API, demo-интерфейсом на Django templates, сервисным слоем, доменными алгоритмами обработки текста и ORM-моделями. Фактическая структура проекта:

```text
backend/
  config/                 Django settings, URL routing, ASGI/WSGI
  core/                   health endpoint, middleware, logging, exception handling
  documents/
    api/                  DRF serializers, viewsets, endpoints, API urls
    demo/                 demo views, demo urls, demo corpus helpers
    domain/               extraction, normalization, chunking, diff, summary, quiz logic
    services/             ingestion, versioning, workflows, quiz lifecycle, attempts, reporting
    management/commands/  utility commands for demo, chunks, entity analysis
    templates/demo/       Django template UI
    tests/                regression tests
    models.py             persistence model of the document-analysis pipeline
scripts/                  lint/test/smoke/helper scripts
infra/                    environment examples
Dockerfile/docker-compose local reproducible runtime
```

Общий поток управления:

1. Пользователь работает через demo UI или API.
2. Presentation layer принимает HTTP-запрос и выполняет минимальную валидацию/сериализацию.
3. Application layer вызывает один из service-entrypoints.
4. Domain layer выполняет обработку текста, diff, significance, summary и quiz generation.
5. Persistence layer сохраняет исходные версии, промежуточные артефакты и результаты.
6. Optional AI layer при включении может улучшать feedback/reporting или entity extraction, но при выключении система продолжает работать через deterministic fallback.
7. Infrastructure layer обеспечивает локальный запуск, Docker Compose, настройки окружения и проверки.

Основная архитектурная схема вынесена в `docs/architecture/diagrams/system-overview.mmd`.

## 5. Слои системы

### 5.1 Presentation Layer

Presentation layer реализован двумя интерфейсами:

- demo UI на Django templates;
- DRF API endpoints/viewsets.

Фактические файлы:

- `backend/documents/demo/views.py`;
- `backend/documents/demo/urls.py`;
- `backend/documents/templates/demo/base.html`;
- `backend/documents/templates/demo/dashboard.html`;
- `backend/documents/templates/demo/document_detail.html`;
- `backend/documents/templates/demo/compare.html`;
- `backend/documents/templates/demo/quizzes.html`;
- `backend/documents/templates/demo/quiz_detail.html`;
- `backend/documents/templates/demo/take_quiz.html`;
- `backend/documents/templates/demo/attempt_detail.html`;
- `backend/documents/templates/demo/report.html`;
- `backend/documents/api/viewsets.py`;
- `backend/documents/api/endpoints.py`;
- `backend/documents/api/serializers.py`;
- `backend/documents/api/urls.py`;
- `backend/config/urls.py`.

Presentation layer отвечает за:

- загрузку и просмотр документов/версий;
- выбор пары версий для сравнения;
- отображение diff, summary и quiz;
- отправку quiz на review;
- approve/reject quiz;
- старт и submit попытки сотрудника;
- отображение результата и отчёта.

Presentation layer **не должен** содержать бизнес-правила сравнения, scoring, lifecycle quiz или reporting. Эти правила вынесены в service layer. Такой подход важен, потому что demo UI и API должны использовать один и тот же source of truth: иначе один и тот же сценарий мог бы по-разному работать через HTML-страницы и через API.

Отдельный frontend не входит в MVP. Django templates достаточны для демонстрации полного локального цикла комиссии и не увеличивают product scope.

### 5.2 Application Layer

Application layer представлен service layer и use-case orchestration. Он координирует доменную обработку, транзакции и материализацию артефактов.

Фактические файлы:

- `backend/documents/services/ingestion.py`;
- `backend/documents/services/versioning.py`;
- `backend/documents/services/workflows.py`;
- `backend/documents/services/quiz_workflow.py`;
- `backend/documents/services/quiz_attempts.py`;
- `backend/documents/services/result_reporting.py`;
- `backend/documents/services/importance.py`;
- `backend/documents/services/analysis.py`;
- `backend/documents/services/search.py`;
- `backend/documents/services/exceptions.py`.

После Фазы 3 границы service layer зафиксированы следующим образом:

| Use case | Source of truth | Роль |
|---|---|---|
| High-level comparison / summary / quiz materialization | `services/workflows.py` | Координация diff, significance enrichment, summary, quiz и materialized ORM rows |
| Quiz lifecycle | `services/quiz_workflow.py` | `draft → pending_review → approved/rejected → superseded`, проверка доступности quiz |
| Attempt execution | `services/quiz_attempts.py` | Start attempt, submit answers, scoring, сохранение `Answer`, финализация `QuizAttempt` |
| Result/reporting payload | `services/result_reporting.py` | Result metrics, frequent errors, manager summary, deterministic/optional LLM feedback |
| Upload/versioning | `services/ingestion.py`, `services/versioning.py` | Создание версий, extraction, normalization, chunk rebuild, duplicate guard |

Application layer вызывает domain layer, но сам не должен превращаться в место альтернативных реализаций алгоритмов. Compatibility wrappers в `workflows.py` сохранены только для обратной совместимости и делегируют в целевые сервисы.

### 5.3 Domain Layer

Domain layer содержит алгоритмы и правила предметной обработки документов. Он реализует вычислительную часть метода `M`.

Фактические файлы:

- `backend/documents/domain/text_extractors.py` — extraction из TXT/DOCX/PDF с текстовым слоем;
- `backend/documents/domain/text_processing.py` — normalization, PDF-safe cleanup, structural chunking;
- `backend/documents/domain/diff.py` — chunk-based comparison и fallback на document text;
- `backend/documents/domain/change_classification.py` — semantic change type baseline;
- `backend/documents/domain/change_enrichment.py` — significance labels, scores, reasons, manual review flags;
- `backend/documents/domain/diff_summary.py` — brief/summary по приоритетным изменениям;
- `backend/documents/domain/diff_quiz.py` — generation of control-learning quiz materials;
- `backend/documents/domain/entity_extraction.py` и `entity_schema.py` — rule-based entity extraction;
- `backend/documents/domain/llm_entity_extraction.py` — optional LLM entity extractor.

Доменная логика в текущем MVP является преимущественно deterministic/rule-based:

- extraction поддерживает TXT, DOCX и PDF с извлекаемым текстом;
- normalization не выполняет агрессивный semantic rewrite;
- chunking строится по русскоязычным структурным маркерам и fallback-блокам;
- comparison использует structural chunks, anchors, similarity и document-text fallback;
- significance classification строится на rule-based признаках, `semantic_type`, `significance_label`, `significance_score`, `significance_reason`, `significance_rules` и `requires_manual_review`;
- summary и quiz generation опираются на materialized highlights и приоритетные изменения;
- scoring попытки выполняется по материализованным вопросам и вариантам ответа.

Ограничение: domain layer не является полноценной правовой экспертной системой и не заменяет юридическую экспертизу. Он решает задачу воспроизводимого анализа изменений между версиями конкретного документа.

### 5.4 Persistence Layer

Persistence layer реализован через Django ORM, миграции, SQLite/PostgreSQL и файловое хранилище media.

Фактические файлы:

- `backend/documents/models.py`;
- `backend/documents/migrations/*.py`;
- `backend/db.sqlite3` для локального dev/runtime;
- `backend/media/documents/...` для загруженных файлов версий;
- настройки `DATABASES`, `MEDIA_ROOT`, `MEDIA_URL` в `backend/config/settings.py`.

Ключевые модели:

- `Document`;
- `DocumentVersion`;
- `Chunk`;
- `ChunkAnalysis`;
- `VersionComparison`;
- `VersionChangeItem`;
- `Summary`;
- `Employee`;
- `GeneratedQuiz`;
- `Question`;
- `Choice`;
- `QuizAttempt`;
- `Answer`.

Persistence layer материализует не только финальные данные, но и промежуточные артефакты: extracted/normalized text, chunks, comparison, change items, significance fields, summary, quiz, attempt answers, score snapshot и reporting cache. Это принципиально важно для диссертации: система не является одноразовым black-box вызовом, а сохраняет проверяемую цепочку обработки.

SQLite используется как достаточный local-first вариант. PostgreSQL поддержан через `DB_ENGINE=postgres` и Docker Compose, но не является обязательным для локального MVP.

### 5.5 Optional AI Layer

Optional AI layer присутствует, но не является обязательным ядром.

Фактические компоненты:

- `backend/documents/services/llm_result_enhancer.py`;
- LLM hooks в `backend/documents/services/result_reporting.py`;
- `backend/documents/domain/llm_entity_extraction.py`;
- optional entity analysis mode в `backend/documents/services/analysis.py`;
- optional semantic search/Qdrant в `backend/documents/services/search.py`;
- `QDRANT_ENABLED`, `ENTITY_LLM_*`, `RESULT_LLM_*` в `backend/config/settings.py` и `infra/.env.example`;
- Qdrant service в `docker-compose.yml` под profile `search`.

Политика optional AI:

- `RESULT_LLM_ENABLED=False` — штатный deterministic режим, а не ошибка;
- LLM feedback/reporting enhancement не меняет score и не пересчитывает attempt;
- при сбое включённого LLM система возвращается к deterministic fallback;
- Qdrant/semantic search не входит в core pipeline `версия → результат`;
- embeddings не являются обязательным условием chunking, comparison, summary или quiz generation.

### 5.6 Infrastructure Layer

Infrastructure layer обеспечивает воспроизводимость локального запуска, проверок и демонстрации.

Фактические файлы:

- `backend/Dockerfile`;
- `docker-compose.yml`;
- `backend/entrypoint.sh`;
- `backend/config/settings.py`;
- `infra/.env.example`;
- `backend/requirements.txt`;
- `backend/requirements-dev.txt`;
- `backend/requirements-ml.txt`;
- `scripts/test.sh`;
- `scripts/lint.sh`;
- `scripts/demo_smoke.sh`;
- `scripts/search_ru.sh`;
- `pyproject.toml`;
- `setup.cfg`.

Локальный runtime:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

Docker runtime:

```bash
cp infra/.env.example infra/.env
docker compose up --build
```

Cloud-first deployment, Kubernetes, production-grade IAM/RBAC, high availability и enterprise monitoring не входят в MVP.

## 6. Компоненты системы

| Компонент | Реализация | Основные файлы | Назначение |
|---|---|---|---|
| Django configuration | `config` app | `backend/config/settings.py`, `backend/config/urls.py`, `asgi.py`, `wsgi.py` | Настройки runtime, URL routing, database/media/static/DRF/logging |
| Core service endpoints | `core` app | `backend/core/views.py`, `backend/core/urls.py`, `middleware.py`, `exceptions.py`, `logging.py` | Health endpoint, request logging, exception handling |
| Documents domain app | `documents` app | `backend/documents/*` | Главная предметная область: документы, версии, сравнение, quiz, attempts, reports |
| Demo UI | Django templates/views | `documents/demo/views.py`, `documents/templates/demo/*` | Демонстрация полного сценария через браузер |
| DRF API | API layer | `documents/api/*` | Программный доступ к documents, versions, compare, quiz, attempts, reports |
| Ingestion/versioning services | Application layer | `services/ingestion.py`, `services/versioning.py` | Создание версий, extraction, normalization, chunks, duplicate guard |
| Workflow service | Application layer | `services/workflows.py` | Materialize comparison, summary, quiz, questions, choices |
| Quiz lifecycle service | Application layer | `services/quiz_workflow.py` | Review/approval/rejection/supersede and attempt availability |
| Attempt service | Application layer | `services/quiz_attempts.py` | Start/submit/scoring and answer persistence |
| Result reporting service | Application layer | `services/result_reporting.py` | Attempt result payload, quiz report, frequent errors, optional feedback |
| Text/domain algorithms | Domain layer | `domain/text_extractors.py`, `text_processing.py`, `diff.py`, `change_enrichment.py`, `diff_summary.py`, `diff_quiz.py` | Реализация вычислительных этапов метода `M` |
| ORM model | Persistence layer | `documents/models.py`, migrations | Materialized artifacts and data integrity constraints |
| Optional AI/Search | Optional layer | `llm_result_enhancer.py`, `llm_entity_extraction.py`, `search.py` | Optional feedback/entity/search enhancement with fallback |
| Infrastructure | Runtime layer | Docker, scripts, requirements, settings | Local reproducibility, checks, smoke, dependency management |

## 7. Поток данных

Полный поток данных в MVP:

1. **Исходный файл** загружается пользователем как новая версия документа.
2. `ingestion.py` валидирует формат и защищает от дублей.
3. `text_extractors.py` извлекает текст из TXT/DOCX/PDF.
4. `text_processing.py` нормализует текст и формирует `content_hash`.
5. `rebuild_version_chunks` materialize-ит структурные `Chunk` rows.
6. `workflows.py` вызывает `diff.py` для сравнения двух версий.
7. `change_enrichment.py` добавляет semantic/significance слой.
8. `VersionComparison` и `VersionChangeItem` сохраняют diff и significance snapshot.
9. `diff_summary.py` строит `Summary.text` и `Summary.highlights`.
10. `diff_quiz.py` строит quiz payload, после чего `GeneratedQuiz`, `Question`, `Choice` сохраняются в БД.
11. `quiz_workflow.py` переводит quiz через review/approval lifecycle.
12. `quiz_attempts.py` создаёт `QuizAttempt`, сохраняет `Answer` rows, score и result snapshot.
13. `result_reporting.py` строит result/reporting payload по сохранённым данным.

Pipeline diagram вынесен в `docs/architecture/diagrams/pipeline.mmd`.

## 8. Связь архитектуры с гибридным методом M = <E, N, S, C, P, G, R>

| Этап метода | Архитектурный слой | Реальные компоненты | Материализованные данные |
|---|---|---|---|
| `E` — Extraction | Domain + Application | `domain/text_extractors.py`, `services/ingestion.py` | `DocumentVersion.extracted_text`, `file`, `source_filename`, `content_type` |
| `N` — Normalization | Domain + Application | `domain/text_processing.py`, `materialize_document_text`, `services/ingestion.py` | `DocumentVersion.normalized_text`, `DocumentVersion.content_hash` |
| `S` — Structural segmentation | Domain + Persistence | `chunk_by_structure_ru`, `rebuild_version_chunks`, model `Chunk` | `Chunk.fragment_type`, `path_key`, `section_path`, `heading`, `text`, `text_hash` |
| `C` — Comparison | Domain + Application + Persistence | `domain/diff.py`, `services/workflows.py`, models `VersionComparison`, `VersionChangeItem` | `VersionComparison`, counts, `VersionChangeItem.old_text/new_text`, `old_chunk/new_chunk`, `similarity`, `match_reason` |
| `P` — Prioritization/significance | Domain + Application + Persistence | `domain/change_enrichment.py`, `domain/change_classification.py`, `services/importance.py`, `materialize_comparison` | `semantic_type`, `extracted_entities`, `significance_label`, `significance_score`, `significance_reason`, `significance_rules`, `requires_manual_review` |
| `G` — Generation | Domain + Application + Persistence | `domain/diff_summary.py`, `domain/diff_quiz.py`, `services/workflows.py`, `services/quiz_workflow.py` | `Summary.text`, `Summary.highlights`, `GeneratedQuiz.payload`, `Question`, `Choice`, quiz status fields |
| `R` — Result fixation | Application + Persistence | `services/quiz_attempts.py`, `services/result_reporting.py`, models `QuizAttempt`, `Answer` | `QuizAttempt.answers`, `score`, `total_questions`, `answered_questions`, `correct_answers`, `score_percent`, timestamps, `Answer`, feedback/reporting cache |

Архитектура тем самым является программной реализацией метода `M`: каждый этап метода имеет слой, компонент и materialized artifact.

## 9. Основной пользовательский сценарий

Основной sequence-сценарий вынесен в `docs/architecture/diagrams/full-scenario-sequence.mmd` и включает следующие действия:

1. Responsible person загружает первую версию документа.
2. Responsible person загружает новую версию того же документа.
3. Система извлекает и нормализует текст обеих версий.
4. Система строит structural chunks.
5. Responsible person выбирает пару версий для сравнения.
6. Система materialize-ит comparison и change items.
7. Система оценивает significance каждого изменения.
8. Система формирует summary/highlights.
9. Система генерирует draft quiz.
10. Responsible person отправляет quiz на review и утверждает его.
11. Employee начинает attempt только по approved quiz.
12. Employee отправляет ответы.
13. Система фиксирует score, answers, timestamps и строит result/reporting payload.

## 10. Materialized artifacts и воспроизводимость

Архитектура построена вокруг материализованных промежуточных результатов.

| Артефакт | Где хранится | Зачем нужен |
|---|---|---|
| Uploaded file | `DocumentVersion.file`, `backend/media/documents/...` | Повторяемый источник исходного текста |
| Extracted text | `DocumentVersion.extracted_text` | Проверка результата extraction без повторного чтения файла |
| Normalized text | `DocumentVersion.normalized_text` | Стабильный вход для chunking/diff |
| Content hash | `DocumentVersion.content_hash` | Duplicate guard и reproducibility marker |
| Structural chunks | `Chunk` | Единицы сравнения и explainable anchors |
| Optional chunk analysis | `ChunkAnalysis` | Rule/LLM entity extraction snapshots |
| Comparison | `VersionComparison` | Зафиксированная пара версий, strategy, status, counters |
| Change items | `VersionChangeItem` | Materialized diff + significance layer |
| Summary | `Summary.text`, `Summary.highlights` | Human-readable bridge from diff to quiz |
| Quiz | `GeneratedQuiz`, `Question`, `Choice` | Materialized learning/control materials |
| Quiz workflow state | `GeneratedQuiz.status`, approval/rejection/supersede fields | Human-in-the-loop control |
| Attempt | `QuizAttempt` | Lifecycle прохождения и score snapshot |
| Answers | `Answer`, `QuizAttempt.answers` | Нормализованные ответы и JSON snapshot |
| Result/reporting | `QuizAttempt` metrics, `llm_feedback*`, `GeneratedQuiz.llm_*` fields | Итоговый result payload и cached feedback/reporting |

За счёт этих артефактов можно восстановить путь данных от файла версии до результата попытки. Это снижает риск black-box поведения и повышает доказательность системы для диссертации.

## 11. Runtime / deployment view

### 11.1 Local runtime

Базовый режим разработки и демонстрации — локальный Django backend:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

По умолчанию `DB_ENGINE=sqlite`, база находится в `backend/db.sqlite3`, media-файлы — в `backend/media/`.

### 11.2 Docker Compose runtime

Docker Compose поднимает backend и PostgreSQL. Qdrant присутствует только в profile `search`.

```bash
cp infra/.env.example infra/.env
docker compose up --build
```

`docker-compose.yml` задаёт:

- `db` на `postgres:16-alpine`;
- `backend` из `backend/Dockerfile`;
- `qdrant` как optional service с `profiles: ["search"]`;
- volumes для Postgres, media и logs;
- healthchecks для backend и database.

### 11.3 Environment configuration

Основные параметры вынесены в `infra/.env.example`:

- `DB_ENGINE=sqlite` для local-first;
- Postgres settings для Docker;
- `QDRANT_ENABLED=0` по умолчанию;
- `RESULT_LLM_ENABLED=False` по умолчанию;
- `RESULT_PASS_THRESHOLD_PERCENT=70`.

### 11.4 Проверки

Проект содержит инженерные проверки:

- `python backend/manage.py check`;
- `python backend/manage.py makemigrations --check --dry-run`;
- `python backend/manage.py test`;
- `bash scripts/test.sh`;
- `bash scripts/lint.sh`;
- `bash scripts/demo_smoke.sh`.

`scripts/demo_smoke.sh` требует работающий dev-сервер на `http://127.0.0.1:8000` или переданный URL.

## 12. Ограничения архитектуры

Ограничения фиксируются явно:

- система local-first и demo-ready, а не cloud-first enterprise deployment;
- поддерживаются TXT, DOCX и PDF с текстовым слоем; OCR для сканов не реализован;
- сравнение выполняется между двумя версиями одного `Document`, а не по всей внешней законодательной базе;
- significance layer — deterministic rule-based baseline, возможны false positives/false negatives;
- quiz generation ориентирован на materialized summary/highlights и single-choice baseline;
- human approval обязателен: employee attempt недоступен до `GeneratedQuiz.status=approved`;
- роли в MVP сценарные, полноценный production auth/RBAC не реализован;
- demo UI на Django templates не является production SPA/frontend;
- result/reporting не является enterprise BI;
- LLM optional и не влияет на score snapshot;
- semantic search/Qdrant optional и не является core для pipeline `версия → результат`;
- система не заменяет правовые системы и юридическую экспертизу.

## 13. Формулировка для диссертации

Архитектура разработанной информационной системы построена по слоистому принципу и включает слой представления, прикладной слой сервисов, доменный слой обработки документов, слой хранения данных, опциональный AI-слой и инфраструктурный слой. Такое разделение обеспечивает воспроизводимость обработки, материализацию промежуточных результатов и возможность проследить полный путь данных от загрузки редакций документа до формирования результата прохождения теста.

Прикладной слой координирует полный пользовательский сценарий: загрузку версий, анализ изменений, формирование выжимки, генерацию контрольного теста, утверждение теста, прохождение сотрудником и построение результата. Доменный слой реализует этапы гибридного метода `M = <E, N, S, C, P, G, R>`, а слой хранения фиксирует проверяемые артефакты каждого этапа: извлечённый и нормализованный текст, структурные фрагменты, сравнение, классифицированные изменения, summary, quiz, попытку и результат.

Опциональный AI-слой используется только как усиление человекочитаемых комментариев, entity extraction или поиска и не является обязательной основой системы. При отключённом LLM система работает в штатном deterministic fallback режиме, что соответствует local-first характеру MVP и требованиям воспроизводимости.

## 14. Architecture-аудит Фазы 7

| Архитектурный слой | Реализация в проекте | Основные файлы | Роль |
|---|---|---|---|
| Presentation | Django templates, demo views, DRF API | `documents/demo/views.py`, `documents/templates/demo/*`, `documents/api/*`, `config/urls.py` | Пользовательский и программный вход в сценарии upload/compare/summary/quiz/attempt/report |
| Application | Service layer and workflows | `services/ingestion.py`, `versioning.py`, `workflows.py`, `quiz_workflow.py`, `quiz_attempts.py`, `result_reporting.py` | Оркестрация use cases, транзакции, materialization, lifecycle, scoring, reporting |
| Domain | Text/diff/significance/summary/quiz algorithms | `domain/text_extractors.py`, `text_processing.py`, `diff.py`, `change_enrichment.py`, `change_classification.py`, `diff_summary.py`, `diff_quiz.py` | Реализация вычислительных этапов метода `M` |
| Persistence | Django ORM, migrations, SQLite/PostgreSQL, media | `documents/models.py`, `documents/migrations/*`, `backend/db.sqlite3`, `backend/media/*`, `settings.py` | Хранение исходных и промежуточных артефактов, ограничений целостности и результата |
| Optional AI | LLM feedback/entity enhancement, optional Qdrant search | `services/llm_result_enhancer.py`, `services/result_reporting.py`, `domain/llm_entity_extraction.py`, `services/search.py`, `docker-compose.yml` | Необязательное улучшение feedback/entity/search без замены core pipeline |
| Infrastructure | Runtime, scripts, dependencies, settings | `backend/Dockerfile`, `docker-compose.yml`, `infra/.env.example`, `scripts/*`, `requirements*.txt`, `pyproject.toml`, `setup.cfg` | Локальный запуск, Docker, проверки, reproducibility |

Проверенные документы Фаз 1–6:

- `PROJECT_SCOPE.md` — найден;
- `ROADMAP.md` — найден;
- `TASKS.md` — найден;
- `docs/scope/mvp-freeze.md` — найден;
- `docs/research/hybrid-method.md` — найден;
- `docs/audit/repository-cleanup.md` — найден;
- `docs/architecture/service-boundaries.md` — найден;
- `docs/architecture/llm-fallback-modes.md` — найден;
- `docs/audit/current-state-audit.md` — не найден в архиве; аудит продолжен по фактическому коду и остальным документам.

## 15. Согласованность с Фазами 1–6

Архитектура согласована со следующими решениями:

- MVP freeze: core pipeline остаётся `версия → анализ изменений → выжимка → тест → утверждение → прохождение → результат`.
- Hybrid method: pipeline отображён на `M = <E, N, S, C, P, G, R>` без добавления новых методов.
- Service boundaries: `workflows.py`, `quiz_workflow.py`, `quiz_attempts.py`, `result_reporting.py` описаны как разные application responsibilities.
- LLM fallback modes: `RESULT_LLM_ENABLED=False` описан как штатный deterministic режим.
- Out-of-scope: OCR, RAG-chat, LangGraph, production RBAC, BI, cloud-first deployment и большая LMS не включены в core architecture.

## 16. Вывод

После Фазы 7 архитектура системы формализована как layered local-first Django information system. Система реализует полный traceable pipeline от версии документа до результата тестирования, сохраняет materialized artifacts каждого этапа и программно реализует гибридный метод `M = <E, N, S, C, P, G, R>`.

Следующая фаза должна быть посвящена **Фазе 8 — формализации алгоритма структурного разбиения**, а не расширению product scope.
