# Service Layer Boundaries

## 1. Цель документа

Документ фиксирует границы application/service layer после Фазы 3: устранения архитектурных дублей в сервисном слое. Главная цель — сохранить один источник истины для каждого бизнес-сценария и сделать backend-архитектуру объяснимой для магистерского проекта.

## 2. Контекст

Проект реализует локальную интеллектуальную систему для работы с нормативно-правовыми и внутренними регламентными документами. Ключевая ценность системы — связанный сценарий:

`версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат`.

Фаза 3 не добавляет новые фичи, не меняет модели и миграции, не внедряет auth/RBAC, RAG, LangGraph или BI. Изменения ограничены нормализацией границ service layer.

## 3. Общий pipeline проекта

Основной pipeline остаётся таким:

1. загрузка или создание версии документа;
2. извлечение и нормализация текста;
3. структурное chunking-разбиение;
4. сравнение версий;
5. классификация значимости изменений;
6. построение summary;
7. генерация и материализация quiz;
8. lifecycle quiz: draft/review/approved/rejected/superseded;
9. попытка сотрудника: start/submit/scoring;
10. result/reporting payload.

## 4. Принцип одного источника истины

После Фазы 3 каждый критический сценарий имеет один основной service-entrypoint:

| Логика | Source of truth |
|---|---|
| High-level comparison/summary/quiz materialization | `documents/services/workflows.py` |
| Quiz lifecycle: submit for review, approve, reject, supersede | `documents/services/quiz_workflow.py` |
| Attempt execution: start, submit, scoring, answer persistence | `documents/services/quiz_attempts.py` |
| Result/reporting payload | `documents/services/result_reporting.py` |

Compatibility wrappers допустимы только как тонкие делегаты. Они не должны содержать альтернативную реализацию бизнес-правил.

## 5. Границы сервисов

### 5.1 `workflows.py`

Ответственность:

- построение diff payload для пары версий;
- материализация `VersionComparison`, `VersionChangeItem` и `Summary`;
- генерация и материализация `GeneratedQuiz`, `Question`, `Choice`;
- supersede старых quiz при создании нового quiz для той же пары версий через lifecycle-сервис;
- high-level orchestration document pipeline.

Не отвечает за:

- ручной approve/reject quiz;
- самостоятельные правила доступности quiz для попыток;
- start attempt;
- submit attempt;
- scoring;
- detailed result reporting.

Оставшиеся функции `submit_quiz_for_review`, `approve_generated_quiz`, `reject_generated_quiz`, `mark_quiz_superseded`, `start_quiz_attempt`, `submit_started_quiz_attempt`, `record_quiz_attempt` в `workflows.py` являются compatibility wrappers и делегируют в целевые сервисы.

### 5.2 `quiz_workflow.py`

Ответственность:

- quiz lifecycle: `draft → pending_review → approved/rejected → superseded`;
- валидация materialized quiz перед review/approval;
- проверка доступности quiz для employee attempt;
- единые сообщения блокировки для недоступных quiz;
- supersede старых quiz.

Не отвечает за:

- scoring attempt;
- сохранение ответов сотрудника;
- построение reporting payload;
- document comparison или quiz materialization.

### 5.3 `quiz_attempts.py`

Ответственность:

- нормализация имени участника;
- подготовка вопросов для формы прохождения;
- поддержка materialized question ids и legacy index-based payload;
- start attempt с переиспользованием активной in-progress attempt;
- submit started attempt;
- единая оценка ответов через `evaluate_quiz_answers`;
- сохранение `Answer` rows;
- финализация `QuizAttempt` snapshot: `answers`, `score`, `total_questions`, `answered_questions`, `correct_answers`, `score_percent`, `status`, timestamps;
- refresh reporting cache после submit.

Не отвечает за:

- approve/reject/supersede quiz;
- high-level document workflow;
- построение full reporting dashboard.

Функции `get_quiz_attempt_block_reason`, `ensure_quiz_attempt_allowed`, `quiz_has_materialized_questions` оставлены как тонкие compatibility wrappers к `quiz_workflow.py`, чтобы старые импорты не ломались.

### 5.4 `result_reporting.py`

Ответственность:

- построение payload результата завершённой попытки;
- вычисление представления метрик на основе уже сохранённого attempt snapshot;
- формирование quiz-level reporting payload;
- частотные ошибки по сохранённым ответам;
- deterministic rule-based feedback и LLM-enhancement cache.

Не отвечает за:

- submit attempt;
- повторный scoring ответов;
- изменение `QuizAttempt.score`, `correct_answers`, `score_percent`;
- lifecycle quiz.

## 6. Как API использует service layer

API endpoints остаются тонким слоем:

- `submit_quiz_review`, `approve_quiz`, `reject_quiz` вызывают `quiz_workflow.py`;
- `start_quiz_attempt_view`, `submit_quiz_attempt` вызывают `quiz_attempts.py`;
- `attempt_result`, `quiz_report` вызывают `result_reporting.py`;
- compare/save quiz endpoints используют `workflows.py` только для high-level pipeline.

API не реализует собственный scoring и не меняет lifecycle-поля quiz напрямую.

## 7. Как demo UI использует service layer

Demo views следуют тем же service-entrypoints, что и API:

- review/approve/reject quiz идут через `quiz_workflow.py`;
- start/submit attempt идут через `quiz_attempts.py`;
- attempt detail и quiz detail получают payload из `result_reporting.py`;
- compare/create quiz workflow остаётся в `workflows.py`.

Это устраняет риск, что demo UI и API будут считать score или менять quiz lifecycle разными способами.

## 8. Устранённые дубли

| Логика | Было | Стало |
|---|---|---|
| Start attempt | Реализация была в `quiz_attempts.py` и продублирована в `workflows.py` | Source of truth — `quiz_attempts.py`; `workflows.py` содержит только wrapper |
| Submit attempt / scoring | Реализация была в `quiz_attempts.py` и продублирована в `workflows.py`; версия в `workflows.py` не обновляла reporting cache | Source of truth — `quiz_attempts.py`; submit всегда финализирует attempt и refresh reporting cache |
| Quiz lifecycle | `submit/approve/reject/supersede` жили внутри `workflows.py`, хотя не являются high-level document pipeline | Source of truth — `quiz_workflow.py`; API/demo импортируют lifecycle оттуда |
| Attempt availability | Похожие проверки были размазаны между `workflows.py`, `quiz_attempts.py`, API pre-checks | Source of truth — `quiz_workflow.py`; старые функции делегируют |
| Result reporting | Reporting строился поверх `QuizAttempt`, но граница не была явно зафиксирована | Документировано и покрыто тестом: reporting читает attempt snapshot и не rescoring answers |

## 9. Compatibility wrappers

Compatibility wrappers оставлены в `workflows.py` и `quiz_attempts.py`, потому что старые тесты, импорты или внешние вызовы могли ссылаться на прежние имена. Правило для wrappers:

- wrapper не содержит бизнес-логики;
- wrapper сразу делегирует в целевой service;
- новая логика должна вызываться из целевого service напрямую.

## 10. Инварианты

- Нельзя начать или отправить attempt для quiz, который не approved или не содержит materialized questions.
- Один участник может иметь только одну active in-progress attempt на quiz.
- Completed attempt immutable на уровне модели; result reporting не должен изменять score snapshot.
- `score == correct_answers`.
- `correct_answers <= answered_questions <= total_questions`.
- API и demo должны использовать одинаковые service-entrypoints для lifecycle и attempt execution.
- `workflows.py` координирует pipeline, но не является scoring engine и не является manual review service.

## 11. Что не входит в эту фазу

- LLM fallback logging и политика подавления fallback-ошибок;
- MVP scope freeze;
- auth/RBAC;
- RAG/LangGraph;
- dashboard/BI;
- изменение моделей и миграций;
- перенос demo corpus;
- переписывание frontend или template layer.

## 12. Проверки после изменений

После Фазы 3 должны запускаться:

| Команда | Назначение |
|---|---|
| `python backend/manage.py check` | Django system check |
| `python backend/manage.py makemigrations --check --dry-run` | Проверка отсутствия незапланированных миграций |
| `python backend/manage.py test` | Базовый Django test command; в текущей структуре из root обнаруживает 0 tests |
| `bash scripts/test.sh` | Фактический запуск test suite из `backend/` |
| `bash scripts/lint.sh` | isort/black/flake8 |
| `bash scripts/demo_smoke.sh` | Smoke-проверка работающего сервера |
| `python backend/manage.py runserver` | Проверка старта dev-сервера |

## 13. Вывод

После Фазы 3 service layer разделён по application responsibilities. `workflows.py` больше не содержит самостоятельные реализации start/submit attempt и quiz lifecycle. Quiz lifecycle вынесен в `quiz_workflow.py`, attempt execution остаётся в `quiz_attempts.py`, а reporting строится поверх стабильного snapshot завершённой попытки. Это делает сервисный слой пригодным для описания в диссертации как application/service layer с принципом «один сценарий — один источник истины».
