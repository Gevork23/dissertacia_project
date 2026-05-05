# Quiz Generation Method

## 1. Назначение документа

Документ формализует этап `G` гибридного метода `M = <E, N, S, C, P, G, R>` — генерацию контрольно-обучающих материалов по результатам анализа изменений нормативно-правовых и внутренних регламентных документов.

Цель документа — описать не абстрактный генератор вопросов, а фактически реализованный в проекте слой quiz generation после Фазы 10. Описание основано на текущем коде backend, доменных сервисах, ORM-моделях, API, demo UI, workflow и тестах.

Документ можно использовать как основу подраздела диссертации `2.9. Генерация контрольно-обучающих материалов`.

Фаза 11 не вводит новый алгоритм генерации, новые модели БД, миграции, LLM/RAG/embeddings и экспериментальную оценку. Она фиксирует научно-инженерную методику уже реализованного baseline-подхода.

## 2. Контекст задачи

Система предназначена для локальной работы с версиями нормативно-правовых и внутренних регламентных документов. MVP pipeline проекта имеет следующий вид:

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

После этапов сравнения и оценки значимости система получает набор структурированных изменений между двумя редакциями документа. Эти изменения могут иметь разную практическую ценность: от критичных правовых требований до редакционных исправлений, не влияющих на действия сотрудника.

Задача quiz generation состоит в том, чтобы преобразовать значимые изменения в проверяемые обучающие вопросы. Такой подход позволяет строить контроль знаний не по случайным фрагментам документа, а по тем изменениям, которые были выявлены, классифицированы и приоритизированы системой.

## 3. Роль quiz generation в гибридном методе

В гибридном методе проекта:

```text
M = <E, N, S, C, P, G, R>
```

этапы имеют следующий смысл:

| Этап | Смысл | Связь с quiz generation |
|---|---|---|
| `E` | извлечение текста из файла | обеспечивает текстовую основу документа |
| `N` | нормализация текста | снижает шум перед chunking/comparison |
| `S` | структурное разбиение | выделяет сопоставимые структурные фрагменты |
| `C` | сравнение редакций | формирует change items |
| `P` | оценка значимости изменений | определяет, какие изменения пригодны для summary/quiz |
| `G` | summary и quiz generation | формирует контрольно-обучающие материалы |
| `R` | фиксация результата прохождения | сохраняет attempts, answers, score и reporting |

Этап `G` расположен после `P`, потому что генерация вопросов должна опираться на приоритизированные изменения. В проекте это реализовано через связку:

```text
VersionComparison + VersionChangeItem
→ Summary.highlights
→ build_quiz_from_summary(...)
→ GeneratedQuiz + Question + Choice
→ human approval
→ QuizAttempt + Answer
```

Таким образом, quiz generation является методическим компонентом, который связывает аналитический diff-layer с обучающим контуром системы.

## 4. Почему генерация вопросов должна опираться на significance

Если генерировать вопросы по всем изменениям подряд, система будет создавать тестовые материалы по техническим и редакционным изменениям: изменению пунктуации, форматирования, переносу блоков, несущественным формулировкам. Для нормативных и регламентных документов это создаёт методический шум и снижает доверие к обучающему контуру.

В текущей реализации significance-layer выполняет роль фильтра качества входных данных для quiz generation:

1. `VersionChangeItem.significance_label` показывает практическую важность изменения.
2. `VersionChangeItem.semantic_type` указывает содержательный тип изменения: срок, документ, обязанность, процедура, основание отказа, условие, ответственность и т.д.
3. `VersionChangeItem.significance_reason` сохраняет объяснение, почему изменение признано значимым.
4. `Summary.highlights` получает enriched metadata по значимости и источнику изменения.
5. `diff_quiz.py` исключает `editorial` и `structure` как нерелевантные для quiz generation semantic types.

Это обеспечивает принцип:

```text
не каждое изменение становится вопросом;
вопрос создаётся только для изменения, которое выглядит содержательно значимым.
```

## 5. Входные и выходные данные

### 5.1 Вход

Фактический вход quiz generation в текущем backend — это не raw document и не LLM prompt, а summary payload с highlights, сформированный на основе materialized comparison.

| Input | Используется реально | Где | Роль |
|---|---:|---|---|
| `Summary.highlights` | yes | `backend/documents/domain/diff_quiz.py`, `build_quiz_from_summary()` | основной источник кандидатов для вопросов |
| `VersionComparison` | yes | `GeneratedQuiz.comparison`, `create_quiz_from_versions()` | связывает quiz с результатом сравнения версий |
| `VersionChangeItem` | yes | `Question.source_change_item`, `source_change_item_id` в payload | источник change metadata и source reference |
| `significance_label` | yes | highlight fields, `VersionChangeItem.significance_label` | фильтрация и приоритизация вопроса |
| `significance_reason` | yes | highlight fields, `Question.explanation` | объяснение полезности вопроса |
| `semantic_type` | yes | highlight fields | выбор question prompt template и distractor pool |
| `change_type` / diff operation | yes | highlight `type` / `VersionChangeItem.change_type` | выбор generic distractors и интерпретация изменения |
| `old_text` / `new_text` | partial | highlight `source`, `VersionChangeItem.old_text/new_text` | source context и fallback-answer при ограниченных данных |
| `similarity` | partial | highlight `source`, fallback selection | исключение слишком похожих modified changes в fallback |
| `match_reason` | partial | highlight `source` | source metadata для traceability |
| related chunks | partial / indirect | `VersionChangeItem.old_chunk/new_chunk` | связь с исходными структурными фрагментами через change item |
| LLM output | no | отсутствует в quiz generation | LLM не является обязательной основой генерации вопросов |

### 5.2 Выход

Выход quiz generation materialize в ORM, чтобы тест можно было проверять, утверждать и воспроизводить независимо от последующих изменений алгоритма.

| Output | Где хранится | Назначение | Ограничения |
|---|---|---|---|
| quiz metadata | `GeneratedQuiz` | связь с версиями, comparison, summary и lifecycle status | не содержит отдельную таблицу revision history quiz content |
| quiz payload | `GeneratedQuiz.payload` | JSON snapshot с вопросами, choices и source metadata | используется demo/API; требует синхронизации с materialized questions |
| questions count | `GeneratedQuiz.questions_count` | быстрый контроль непустого quiz | может расходиться только при ручном повреждении данных |
| question text | `Question.prompt` и payload `question` | текст вопроса для UI/API/attempt | текущий generator создаёт только single choice prompts |
| question type | `Question.question_type` | тип проверки | модель поддерживает больше типов, чем фактически генерируется |
| options | `Choice` rows и payload `choices` | варианты ответа | distractors baseline, ограниченная семантическая правдоподобность |
| correct answer | `Choice.is_correct`, `Question.correct_text_answer` | scoring и expected answer | для single choice scoring основан на correct choice |
| explanation | `Question.explanation`, payload `explanation` | пояснение, зачем проверяется изменение | формируется rule-based, не является юридическим заключением |
| source/reference | `Question.source_change_item`, payload `source` | трассировка вопроса к change item/source fragment | отдельного поля `source_reference` в модели нет |
| approval status | `GeneratedQuiz.status` | human-in-the-loop lifecycle | попытки доступны только для approved quiz |

## 6. Источники данных для генерации

Реализация quiz generation распределена по нескольким слоям.

| Слой | Файл | Роль |
|---|---|---|
| summary generation | `backend/documents/domain/diff_summary.py` | формирует `Summary.highlights` на основе prioritized changes |
| quiz payload generation | `backend/documents/domain/diff_quiz.py` | deterministic/template-based generation из highlights |
| workflow orchestration | `backend/documents/services/workflows.py` | `create_quiz_from_versions()` создаёт comparison, summary и materialized quiz |
| lifecycle approval | `backend/documents/services/quiz_workflow.py` | переводит quiz через `draft/pending_review/approved/rejected/superseded` |
| attempt lifecycle | `backend/documents/services/quiz_attempts.py` | создаёт attempts, оценивает answers, materialize Answer rows |
| reporting | `backend/documents/services/result_reporting.py` | строит attempt result и quiz report |
| API | `backend/documents/api/endpoints.py` | preview/save/review/attempt/report endpoints |
| demo UI | `backend/documents/demo/views.py`, templates | демонстрация preview, approval и прохождения теста |

Основная функция генерации — `build_quiz_from_summary()`. Она получает `summary_payload`, версии документа и флаг `identical`, выбирает подходящие highlights, строит вопросы, формирует варианты ответа и возвращает JSON payload. Сохранение payload в БД выполняется в `create_quiz_from_versions()`.

## 7. Типы вопросов

В модели `Question.QuestionType` объявлены четыре типа:

- `single_choice`;
- `multiple_choice`;
- `true_false`;
- `text`.

Однако фактический generator `backend/documents/domain/diff_quiz.py` в текущем MVP создаёт только `single_choice` вопросы. Это важно для диссертационного описания: поддержка типов на уровне модели шире, но реализованный baseline generation не использует true/false, multiple choice и short/open text.

`workflows.py` содержит compatibility mapping `QUESTION_TYPE_MAP`, включая mapping `open_text`/`text`, но текущий quiz payload generator не генерирует такие вопросы.

## 8. Таблица типов вопросов

| Question type | Реализован в модели | Генерируется автоматически | Purpose | Input signals | Output format | Scoring | Limitations |
|---|---:|---:|---|---|---|---|---|
| `single_choice` | yes | yes | проверка понимания конкретного значимого изменения | highlight + semantic type + significance + source metadata | вопрос + несколько choices + один correct choice | `Choice.is_correct` | distractors baseline; нужен однозначный answer |
| `multiple_choice` | yes | no | потенциальная проверка нескольких правильных утверждений | не используется generator | не формируется | не используется текущим generator | out of current MVP generation behavior |
| `true_false` | yes | no | потенциальная проверка факта изменения | не используется generator | не формируется | не используется текущим generator | не нужно описывать как реализованную генерацию |
| `text` | yes | no | потенциальный открытый ответ / compatibility | не используется generator | не формируется | есть поля `correct_text_answer`/`text_answer`, но generator не создаёт text questions | не является baseline quiz generation output |

Вывод: для Фазы 11 quiz generation следует описывать как deterministic generation of `single_choice` questions.

## 9. Связь “изменение → вопрос”

Вопрос формируется не из документа целиком, а из highlight, который связан с конкретным change item. Логическая цепочка выглядит так:

```text
VersionChangeItem
  change_type
  semantic_type
  significance_label
  significance_reason
  old_text / new_text
  old_chunk / new_chunk
      ↓
Summary.highlight
  title
  description
  concise_explanation
  source_change_item_id
  source_sort_order
      ↓
Quiz question payload
  question
  answer
  choices
  explanation
  source
      ↓
Question + Choice ORM records
```

На уровне модели связь вопроса с источником materialize через `Question.source_change_item`. Это позволяет downstream reporting показывать, по какому фрагменту/изменению сотрудник ошибся.

## 10. Таблица связи “изменение → вопрос”

Таблица ниже является методическим обобщением фактически реализованной логики `semantic_type → prompt template → answer/explanation`. Она не утверждает наличие отдельного declarative template-файла: правила реализованы в коде `diff_quiz.py` через dictionaries/functions.

| Change / semantic type | Significance | Question type | Question focus | Example | Why useful | Фактический статус |
|---|---|---|---|---|---|---|
| `deadline` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | новый или изменённый срок | Какое изменение по срокам должен учитывать сотрудник? | проверяет прикладное изменение срока | реализовано через `PROMPT_TEMPLATES[deadline]` |
| `document` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | изменение перечня документов | Какое изменение в перечне документов нужно учитывать? | проверяет требования к комплекту документов | реализовано |
| `obligation` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | новая/изменённая обязанность | Какое изменение в обязанностях отражено? | проверяет действие сотрудника | реализовано |
| `procedure` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | порядок действий | Как изменился порядок действий? | проверяет процедурный аспект | реализовано |
| `refusal` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | основания отказа | Какое изменение в основаниях отказа отражено? | важно для корректного применения регламента | реализовано |
| `condition` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | условия применения нормы | Какое изменение условий применения нормы отражено? | проверяет применимость требования | реализовано |
| `responsibility` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | ответственность | Какое изменение в положениях об ответственности отражено? | проверяет риск и ответственность | реализовано |
| `informational` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | справочная значимая информация | Какая новая справочная информация важна? | полезно для ориентирования сотрудника | реализовано |
| `unclassified` | `critical` / `important` / `informational` / `not_evaluated` | `single_choice` | общее значимое изменение | Какое значимое изменение отражено? | fallback для содержательного изменения без точного semantic type | реализовано |
| `editorial` | `editorial` | no question | — | вопрос не формируется | исключает шум от пунктуации/формулировок | исключается `NON_QUIZ_SEMANTIC_TYPES` |
| `structure` | usually non-quiz | no question | — | вопрос не формируется | исключает вопросы по переносам/структуре без содержательного эффекта | исключается `NON_QUIZ_SEMANTIC_TYPES` |

## 11. Шаблоны и правила генерации

В коде есть явные dictionaries, которые выполняют роль шаблонов baseline generation:

- `PROMPT_TEMPLATES` — шаблоны текста вопроса по `semantic_type`;
- `SEMANTIC_DISTRACTORS` — fallback distractors по semantic type;
- `GENERIC_DISTRACTORS` — fallback distractors по diff operation (`added`, `removed`, `modified`, `moved`);
- `QUIZ_PRIMARY_LABELS` — allowed significance labels для primary selection;
- `NON_QUIZ_SEMANTIC_TYPES` — semantic types, исключаемые из quiz generation;
- `MAX_QUESTIONS_PER_SEMANTIC_TYPE` — ограничение на однотипные вопросы.

| Template ID | Use case | Question pattern | Correct answer source | Distractor source | Фактическая реализация |
|---|---|---|---|---|---|
| `T_deadline` | срок | `Какое изменение по срокам должен учитывать сотрудник в разделе «{title}»?` | `concise_explanation` или `description` highlight | answer pool + `SEMANTIC_DISTRACTORS[deadline]` + generic | `PROMPT_TEMPLATES[deadline]` |
| `T_document` | перечень документов | `Какое изменение в перечне документов нужно учитывать в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_obligation` | обязанность | `Какое изменение в обязанностях отражено в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_procedure` | процедура | `Как изменился порядок действий в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_refusal` | основания отказа | `Какое изменение в основаниях отказа отражено в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_condition` | условия | `Какое изменение условий применения нормы отражено в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_responsibility` | ответственность | `Какое изменение в положениях об ответственности отражено в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_informational` | справочная информация | `Какая новая справочная информация важна в разделе «{title}»?` | `concise_explanation` / `description` | answer pool + semantic/generic distractors | реализовано |
| `T_unclassified` | общий fallback | `Какое значимое изменение отражено в разделе «{title}»?` | `concise_explanation` / `description` или fallback из old/new text | answer pool + generic distractors | реализовано |

### Правила отбора candidates

Фактический отбор в `diff_quiz.py` можно описать так:

1. Берутся highlights из `Summary.highlights`.
2. Исключаются highlights с semantic types `editorial` и `structure`.
3. В primary selection попадают highlights с labels из `QUIZ_PRIMARY_LABELS`.
4. Выполняется deduplication по semantic type, title и explanation/description.
5. Сначала берётся не более одного вопроса на semantic type.
6. Затем допускается второй проход, но не более `MAX_QUESTIONS_PER_SEMANTIC_TYPE`.
7. Итог ограничивается `max_questions`.
8. Если primary candidates отсутствуют, включается ограниченный fallback для содержательных `added`/`removed`/`modified` changes, но не для editorial-only changes.

### Правила исключения noise

Фактическая baseline-защита от шума:

- semantic types `editorial` и `structure` не являются quiz candidates;
- `moved` не используется как meaningful fallback;
- для `modified` fallback проверяет, что old/new text различаются;
- при наличии `similarity` слишком близкие changes не используются как fallback;
- если валидных вопросов нет, `create_quiz_from_versions()` не сохраняет пустой quiz, а выбрасывает `EmptyQuizError`.

## 12. Формирование вариантов ответа

Фактическая логика формирования options реализована в `_build_choices()`.

### Correct option

Правильный ответ формируется из:

1. `highlight.concise_explanation`, если оно доступно;
2. иначе из `highlight.description`;
3. иначе из fallback-answer, построенного по old/new text для ограниченных содержательных случаев.

Ответ нормализуется и ограничивается по длине. В materialized model он сохраняется в двух формах:

- как `Choice(text=..., is_correct=True)`;
- как `Question.correct_text_answer` для expected answer/reporting compatibility.

### Distractors

Неправильные варианты формируются последовательно:

1. из answer pool других вопросов того же quiz payload;
2. из `SEMANTIC_DISTRACTORS` для semantic type;
3. из `GENERIC_DISTRACTORS` для diff operation;
4. из generic fallback strings, если вариантов всё ещё мало.

Реализация выполняет deduplication, чтобы distractor не совпадал с правильным ответом. Порядок вариантов детерминированно ротируется по индексу вопроса, поэтому правильный вариант не всегда стоит первым, но генерация остаётся воспроизводимой.

### Ограничения distractors

Distractors являются baseline: они не гарантируют юридическую правдоподобность, не извлекаются через NLP-модель из соседних норм и не проходят semantic validation. Поэтому human approval обязателен.

## 13. Correct answer, explanation и source reference

### Correct answer

Для автоматически генерируемого `single_choice` вопроса правильность ответа определяется через `Choice.is_correct=True`. При прохождении attempt сервис сравнивает выбранный `Choice.id` с correct choice.

`Question.correct_text_answer` сохраняет текст правильного ответа и используется в result/reporting как expected answer.

### Explanation

`Question.explanation` формируется deterministic способом. В payload она строится как пояснение вида:

```text
Проверяет понимание изменения: ... Причина значимости: ...
```

Если `significance_reason` отсутствует, explanation остаётся более общей. Explanation полезен для review UI, attempt result и reporting, но он не является юридическим заключением и не заменяет проверку методистом/юристом.

### Source reference

Source/reference реализован в двух формах:

1. `Question.source_change_item` — FK на `VersionChangeItem`;
2. `GeneratedQuiz.payload.questions[].source` — JSON metadata, включая source texts и matching/significance context, когда они доступны.

Через `VersionChangeItem` вопрос связан с:

- `old_chunk` / `new_chunk`;
- `old_text` / `new_text`;
- `semantic_type`;
- `significance_label`;
- `significance_reason`;
- `sort_order`.

Отдельного поля `source_reference` в `Question` нет. Поэтому в диссертации корректно говорить не о standalone source reference field, а о traceability через `source_change_item` и payload source metadata.

## 14. Human-in-the-loop approval

В нормативной области generated quiz не должен автоматически становиться доступным сотруднику. Даже deterministic baseline может сформировать слабый или неоднозначный вопрос, если:

- diff выделил фрагмент слишком широко;
- significance reason оказался недостаточным;
- answer был сформирован слишком общо;
- distractor оказался спорным;
- юридическая формулировка требует контекста;
- изменение требует методической интерпретации.

Поэтому в проекте реализован human-in-the-loop workflow:

```text
draft
→ pending_review
→ approved
```

Также поддерживаются состояния:

- `rejected`;
- `superseded`;
- `archived`.

Attempt lifecycle блокирует прохождение quiz, если quiz не approved или если quiz пустой / не materialized. Это реализует quality gate между генерацией и использованием теста сотрудником.

| Status | Meaning | Attempt availability |
|---|---|---:|
| `draft` | quiz сохранён, но не отправлен на review | no |
| `pending_review` | ожидает проверки ответственным лицом | no |
| `approved` | утверждён ответственным лицом | yes |
| `rejected` | отклонён, требует исправления/перегенерации | no |
| `superseded` | заменён более новой генерацией | no |
| `archived` | выведен из активного использования | no |

## 15. Materialization generated quiz

Materialization — важное инженерное решение MVP. Система не оставляет quiz только как transient JSON preview, а сохраняет его в ORM:

```text
GeneratedQuiz
  ├─ Question
  │   ├─ Choice
  │   └─ source_change_item → VersionChangeItem
  └─ payload JSON snapshot
```

Materialization нужна для:

1. воспроизводимости: сотрудник проходит именно ту версию quiz, которая была утверждена;
2. approval workflow: ответственное лицо проверяет конкретные materialized questions;
3. scoring: attempt оценивается по сохранённым `Choice.is_correct`;
4. reporting: ошибки связываются с конкретными questions и source changes;
5. supersede lifecycle: новая генерация может заменить старую без смешивания результатов.

`create_quiz_from_versions()` также supersede existing active quizzes для той же пары версий, если создаётся новая версия quiz. Это предотвращает одновременное использование нескольких активных quiz по одному сравнению.

## 16. Использование quiz в downstream pipeline

| Downstream слой | Как использует generated quiz | Почему это важно |
|---|---|---|
| API preview | `compare_versions_quiz` возвращает transient quiz payload | позволяет посмотреть baseline quiz до сохранения |
| API save | `save_versions_quiz` вызывает `create_quiz_from_versions()` | создаёт materialized quiz/questions/choices |
| Quiz workflow | `submit_quiz_for_review`, `approve_generated_quiz`, `reject_generated_quiz` | human quality control |
| Demo UI | показывает preview, saved quiz, choices, correct answer для reviewer | демонстрирует прикладную ценность pipeline |
| Attempt | `start_quiz_attempt`, `submit_started_quiz_attempt` | сотрудник проходит только approved quiz |
| Scoring | `evaluate_quiz_answers()` проверяет selected choice | превращает quiz в измеримый контроль знаний |
| Result/reporting | `build_attempt_result`, `build_quiz_report` | фиксирует результат и frequent errors |
| Tests | regression coverage для preview/save/source/approval/attempt/reporting | защищает MVP pipeline от regression |

## 17. Псевдокод алгоритма

Псевдокод отражает фактическую реализацию, а не желаемый расширенный LLM/RAG pipeline.

```text
Input:
    from_version
    to_version
    max_questions

Algorithm create_quiz_from_versions:
    diff_payload = compare_versions(from_version, to_version)

    comparison, summary, change_items = materialize_comparison(
        from_version,
        to_version,
        diff_payload
    )

    quiz_payload = build_quiz_from_summary(
        summary_payload = {"highlights": summary.highlights},
        from_version_payload,
        to_version_payload,
        identical = comparison.identical,
        max_questions = max_questions
    )

    if quiz_payload.questions_count == 0:
        raise EmptyQuizError

    mark existing draft/pending_review/approved quizzes for the same version pair as superseded

    create GeneratedQuiz(
        comparison = comparison,
        summary = summary,
        from_version = from_version,
        to_version = to_version,
        payload = quiz_payload,
        status = draft,
        questions_count = quiz_payload.questions_count
    )

    for each question_payload in quiz_payload.questions:
        source_change_item = find VersionChangeItem by source_change_item_id

        question = create Question(
            quiz = GeneratedQuiz,
            source_change_item = source_change_item,
            order = question_index,
            question_type = single_choice,
            prompt = question_payload.question,
            explanation = question_payload.explanation,
            correct_text_answer = question_payload.answer
        )

        for each choice_payload in question_payload.choices:
            create Choice(
                question = question,
                order = choice_payload.choice_index,
                text = choice_payload.text,
                is_correct = choice_payload.is_correct
            )

    return GeneratedQuiz
```

```text
Algorithm build_quiz_from_summary:
    highlights = summary_payload.highlights

    primary_candidates = []
    for each highlight in highlights:
        if highlight.semantic_type in {editorial, structure}:
            continue
        if highlight.significance_label not in QUIZ_PRIMARY_LABELS:
            continue
        primary_candidates.append(highlight)

    if primary_candidates is empty:
        candidates = select limited meaningful fallback highlights
    else:
        candidates = primary_candidates

    candidates = deduplicate candidates by semantic_type, title and explanation
    candidates = limit semantic concentration
    candidates = truncate to max_questions

    for each candidate:
        prompt = PROMPT_TEMPLATES[candidate.semantic_type]
        answer = candidate.concise_explanation or candidate.description or fallback_answer
        explanation = build explanation from answer and significance_reason
        source = build source metadata from source_change_item_id, old_text, new_text, similarity, match_reason
        add question payload with question_type = single_choice

    for each question:
        choices = build correct choice + distractors
        rotate choices deterministically

    return quiz payload
```

## 18. Примеры вопросов

Примеры ниже демонстрируют методический принцип. Они соответствуют поддерживаемому типу `single_choice` и не утверждают наличие генерации true/false или multiple choice.

### Example 1 — deadline change

Change:

```text
Срок предоставления услуги изменён с 10 до 7 рабочих дней.
```

Question:

```text
Какое изменение по срокам должен учитывать сотрудник в разделе «Срок предоставления услуги»?
```

Options:

```text
A. Срок предоставления услуги изменён с 10 до 7 рабочих дней.
B. Изменение касается только редакционного уточнения формулировки.
C. Порядок действий не изменился.
```

Correct:

```text
A
```

Explanation:

```text
Проверяет понимание изменения: срок предоставления услуги изменён с 10 до 7 рабочих дней.
```

### Example 2 — obligation change

Change:

```text
Добавлена обязанность сотрудника уведомить заявителя о результате рассмотрения заявления.
```

Question:

```text
Какое изменение в обязанностях отражено в разделе «Информирование заявителя»?
```

Correct answer:

```text
Добавлена обязанность сотрудника уведомить заявителя о результате рассмотрения заявления.
```

### Example 3 — document list change

Change:

```text
В перечень документов добавлена копия паспорта.
```

Question:

```text
Какое изменение в перечне документов нужно учитывать в разделе «Необходимые документы»?
```

Correct answer:

```text
В перечень документов добавлена копия паспорта.
```

### Example 4 — procedure change

Change:

```text
Заявление теперь может подаваться через электронную форму.
```

Question:

```text
Как изменился порядок действий в разделе «Подача заявления»?
```

Correct answer:

```text
Добавлена возможность подачи заявления через электронную форму.
```

### Example 5 — refusal change

Change:

```text
Добавлено новое основание отказа: отсутствие согласия на обработку персональных данных.
```

Question:

```text
Какое изменение в основаниях отказа отражено в разделе «Основания отказа»?
```

Correct answer:

```text
Добавлено основание отказа при отсутствии согласия на обработку персональных данных.
```

### Example 6 — responsibility change

Change:

```text
Уточнена ответственность сотрудника за нарушение срока регистрации заявления.
```

Question:

```text
Какое изменение в положениях об ответственности отражено в разделе «Ответственность»?
```

Correct answer:

```text
Уточнена ответственность сотрудника за нарушение срока регистрации заявления.
```

### Example 7 — editorial change

Change:

```text
Исправлена пунктуация без изменения смысла нормы.
```

Quiz behavior:

```text
Вопрос не формируется, так как изменение относится к editorial/structure noise и не является quiz candidate.
```

## 19. Baseline nature of the method

Quiz generation в MVP является deterministic/rule-based/template-based baseline. Это означает:

1. генерация не зависит от внешней LLM;
2. результат воспроизводим при одинаковых входных highlights;
3. templates и distractors заданы в коде;
4. source traceability сохраняется через materialized change item;
5. качество зависит от качества comparison, significance и summary;
6. human approval остаётся обязательным.

Baseline-подход выбран сознательно, потому что MVP должен быть local-first, воспроизводимым и проверяемым. Он не претендует на автоматическую юридическую экспертизу вопроса.

## 20. Связь с архитектурой системы

Quiz generation согласован со слоистой архитектурой проекта:

| Архитектурный слой | Реализация | Роль |
|---|---|---|
| domain | `diff_quiz.py`, `diff_summary.py` | deterministic generation logic |
| service layer | `workflows.py`, `quiz_workflow.py`, `quiz_attempts.py` | orchestration, materialization, lifecycle |
| persistence | Django ORM models | `GeneratedQuiz`, `Question`, `Choice`, `QuizAttempt`, `Answer` |
| API | DRF endpoints/serializers | preview/save/approval/attempt/reporting |
| UI | demo views/templates | human review and employee attempt |
| reporting | `result_reporting.py` | score, frequent errors, optional LLM reporting enhancement |

LLM fallback modes не противоречат quiz generation: текущая LLM-related логика относится к reporting/feedback cache и не является обязательным quiz generator.

## 21. Связь с будущей экспериментальной оценкой

Фаза 11 описывает метод. Экспериментальная оценка качества quiz generation относится к будущей Фазе 18.

Будущие критерии оценки могут включать:

| Criterion | Meaning |
|---|---|
| связь вопроса с реальным изменением | вопрос должен соответствовать конкретному `VersionChangeItem` |
| юридическая корректность | вопрос не должен искажать норму |
| однозначный correct answer | у вопроса должен быть один корректный ответ |
| качество distractors | неправильные варианты не должны быть абсурдными или совпадать с correct answer |
| отсутствие editorial noise | вопросы не должны создаваться по чисто редакционным изменениям |
| source/reference correctness | вопрос должен ссылаться на корректный change item/source fragment |
| usefulness for employee | вопрос должен проверять прикладное знание сотрудника |
| coverage significant changes | доля важных изменений, покрытых вопросами |
| precision of generated questions | доля вопросов, признанных экспертами корректными |
| explanation quality | пояснение должно объяснять, почему изменение важно |
| expert score | экспертная оценка вопроса по шкале 1–5 |

Фаза 11 не создаёт evaluation corpus, не проводит эксперименты и не строит метрики качества. Она готовит методическую базу для будущей оценки.

## 22. Ограничения метода

Фактические ограничения текущего baseline:

1. Автоматически генерируется только `single_choice`.
2. `multiple_choice`, `true_false` и `text` существуют в model enum, но не используются текущим generator.
3. Distractors формируются rule-based из answer pool, semantic pools и generic pools; они не валидируются семантически.
4. Explanation является шаблонным и зависит от `significance_reason`.
5. Source reference реализован через FK `Question.source_change_item` и payload metadata, а не через отдельную модель источников.
6. Related chunks используются косвенно через `VersionChangeItem.old_chunk/new_chunk`; отдельного RAG retrieval на этапе quiz generation нет.
7. Если summary/significance слабые, вопрос тоже может быть слабым.
8. Сложные юридические конструкции могут требовать ручной редакции вопроса.
9. Baseline не заменяет методиста, юриста или ответственного владельца регламента.
10. Empty/editorial-only comparisons не создают saved quiz; это корректное поведение для снижения шума.
11. LLM-based quiz generation отсутствует и не должна описываться как реализованная функция.

## 23. Формулировка для диссертации

В рамках разработанного гибридного метода предложен способ автоматизированного формирования контрольно-обучающих материалов по значимым изменениям нормативно-правовых и регламентных документов. На вход данного этапа поступают результаты структурного сравнения редакций, оценка значимости изменений, краткая выжимка и связанные с изменениями фрагменты документа. На их основе deterministic rule-based baseline формирует вопросы типа single choice, варианты ответов, правильный ответ, пояснение и трассировку к исходному изменению. Сформированные тестовые материалы materialize в базе данных и проходят обязательное human-in-the-loop утверждение ответственным лицом перед использованием сотрудником. Такой подход позволяет связать контроль знаний не с произвольным содержанием документа, а с реально выявленными и приоритизированными изменениями, сохраняя воспроизводимость, проверяемость и возможность последующей оценки качества.

## 24. Вывод

Quiz generation в проекте является методическим этапом гибридного анализа изменений, а не случайной генерацией вопросов. Он получает на вход summary highlights, enriched significance metadata и source-linked change items; затем deterministic/template-based способом формирует materialized `GeneratedQuiz`, `Question` и `Choice` records; сохраняет correct answer, explanation и traceability к `VersionChangeItem`; передаёт результат в human approval workflow; после утверждения quiz используется в employee attempt и result/reporting lifecycle.

Для MVP это завершает локальный цикл:

```text
версия документа
→ анализ изменений
→ оценка значимости
→ выжимка
→ тест
→ утверждение
→ прохождение
→ результат
```

Следующим логическим шагом после Фазы 11 является Фаза 12 — подготовка demo corpus, не изменяющая формализованный здесь метод quiz generation.