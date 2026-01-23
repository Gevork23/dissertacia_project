# ERD — Entity Relationship Diagram (MVP)

Ниже — логическая схема данных для MVP. Она спроектирована так, чтобы:
- хранить документы и их версии (локальные файлы)
- хранить чанки (структурные фрагменты текста)
- хранить результаты векторной индексации (через metadata + внешний Qdrant)
- хранить тесты, вопросы, попытки, ответы и статистику

---

## 1) Users

### `User` (Django auth)
Используем стандартного пользователя Django (`django.contrib.auth`).

**Поля (стандарт):**
- id (PK)
- username
- email (optional)
- password hash
- is_staff / is_superuser

**Роли (MVP):**
- Admin: `is_staff=True` (или группа `admin`)
- Employee: обычный пользователь

> Позже можно добавить отдельную таблицу профиля (Department/Position), но в MVP не обязательно.

---

## 2) Documents & Versions

### `Document`
Один “логический” документ, например:
- “ФЗ №152 О персональных данных”
- “Регламент обработки обращений граждан”
- “Положение о …”

**Поля:**
- id (PK)
- title (str, required)
- description (text, optional)
- created_at (datetime)
- updated_at (datetime)

**Связи:**
- Document 1—M DocumentVersion

---

### `DocumentVersion`
Конкретная версия документа (файл + извлечённый текст).

**Поля:**
- id (PK)
- document_id (FK → Document)
- version_number (int) — 1,2,3… (можно автосчитать)
- source_filename (str) — оригинальное имя файла
- file_path (file) — путь к загруженному файлу (media)
- extracted_text (long text) — полный текст после парсинга
- normalized_text (long text, optional) — нормализованный текст (для diff)
- content_hash (str, optional) — hash нормализованного текста (быстро понимать, одинаковые ли версии)
- created_at (datetime)

**Индексы:**
- (document_id, version_number) unique
- content_hash index (опционально)

**Связи:**
- DocumentVersion 1—M Chunk
- DocumentVersion 1—M VersionDiff (опционально, если храним diff как сущность)

---

## 3) Chunks (text blocks)

### `Chunk`
Фрагмент текста (структурный блок), который:
- индексируется в Qdrant
- используется для RAG/цитат
- используется для diff “по блокам”

**Поля:**
- id (PK)
- version_id (FK → DocumentVersion)
- chunk_index (int) — порядковый номер в версии
- section_path (str, optional) — “Раздел 2 > Статья 5 > Пункт 5.1”
- heading (str, optional) — заголовок блока
- text (long text, required)
- text_hash (str, optional) — hash текста чанка (для diff)
- token_count (int, optional) — для контроля размера
- created_at (datetime)

**Индексы:**
- (version_id, chunk_index)
- text_hash (опционально)

**Связи:**
- Chunk M—M Question (через QuestionSource, чтобы указывать источники вопроса)
- Chunk связан с Qdrant по id/metadata:
  - qdrant_point_id (optional) — если хотим хранить id точки
  - иначе достаточно chunk_id в metadata при апсёрте в Qdrant

---

## 4) Version Diff (изменения между версиями)

В MVP можно НЕ хранить diff в базе, а считать “на лету”.
Но для удобства UI и диссертации лучше хранить результат сравнения.

### `VersionComparison` (рекомендовано)
Сравнение двух версий одного документа.

**Поля:**
- id (PK)
- document_id (FK → Document)
- from_version_id (FK → DocumentVersion)
- to_version_id (FK → DocumentVersion)
- created_by (FK → User, optional)
- created_at (datetime)

**Связи:**
- VersionComparison 1—M VersionChangeItem

---

### `VersionChangeItem`
Один элемент изменения (по чанкам/блокам).

**Поля:**
- id (PK)
- comparison_id (FK → VersionComparison)
- change_type (enum) — `added | removed | modified`
- from_chunk_id (FK → Chunk, nullable)
- to_chunk_id (FK → Chunk, nullable)
- change_summary (text, optional) — краткое описание (может делать LLM)
- diff_text (text, optional) — “сырой” diff (опционально)

---

## 5) Tests & Questions

### `Test`
Тест, сгенерированный обычно по конкретному сравнению версий (или по документу).

**Поля:**
- id (PK)
- document_id (FK → Document)
- comparison_id (FK → VersionComparison, nullable) — чаще всего привязан к изменениям
- title (str)
- description (text, optional)
- status (enum) — `draft | published | archived`
- created_by (FK → User)
- created_at (datetime)

**Связи:**
- Test 1—M Question
- Test 1—M Attempt

---

### `Question`
Вопрос теста.

**Поля:**
- id (PK)
- test_id (FK → Test)
- question_type (enum) — `single_choice | true_false` (позже: multi/short)
- prompt (text) — текст вопроса
- explanation (text, optional) — пояснение/разбор (желательно для обучения)
- difficulty (int, optional 1..5)
- created_at (datetime)

**Связи:**
- Question 1—M Choice (для single_choice)
- Question M—M Chunk через QuestionSource (источники)

---

### `Choice`
Варианты ответа (для single_choice).

**Поля:**
- id (PK)
- question_id (FK → Question)
- text (str/text)
- is_correct (bool)
- order (int)

---

### `QuestionSource` (junction table)
Связка вопроса с источниками (чанками), чтобы показывать “на основании чего”.

**Поля:**
- id (PK)
- question_id (FK → Question)
- chunk_id (FK → Chunk)
- quote (text, optional) — прямой фрагмент/цитата
- relevance (float, optional) — если хотим сохранять ранжирование

---

## 6) Attempts & Answers

### `Attempt`
Попытка прохождения теста пользователем.

**Поля:**
- id (PK)
- test_id (FK → Test)
- user_id (FK → User)
- started_at (datetime)
- finished_at (datetime, nullable)
- score (float, nullable)
- max_score (float, nullable)
- status (enum) — `in_progress | finished`

**Индексы:**
- (test_id, user_id, started_at)

**Связи:**
- Attempt 1—M Answer

---

### `Answer`
Ответ пользователя на конкретный вопрос в попытке.

**Поля:**
- id (PK)
- attempt_id (FK → Attempt)
- question_id (FK → Question)
- selected_choice_id (FK → Choice, nullable) — для single_choice
- boolean_answer (bool, nullable) — для true_false
- is_correct (bool, nullable)
- answered_at (datetime)

---

## Notes: Qdrant integration (важно)
Векторная БД хранит embeddings и metadata.
**Минимальный metadata для точки Qdrant:**
- document_id
- version_id
- chunk_id
- section_path
- heading
- chunk_index

ID точки в Qdrant можно:
- либо делать равным `chunk_id` (удобно)
- либо хранить отдельный `qdrant_point_id`

---

## MVP minimum table set (если режем до минимума)
Если надо прям совсем быстро:
- Document
- DocumentVersion
- Chunk
- Test
- Question
- Choice
- Attempt
- Answer
(+ User стандартный)

А VersionComparison / VersionChangeItem / QuestionSource можно добавить во 2-й итерации.
