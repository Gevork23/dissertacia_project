# AI_ARCHITECTURE

## 1. Назначение документа

Этот документ фиксирует целевую архитектуру AI-слоя проекта магистерской диссертации.

Проект развивается не как обычный backend для документов, а как **интеллектуальная система анализа изменений нормативно-правовых актов (НПА)**, ориентированная на:

- анализ версий документов;
- интерпретацию изменений;
- извлечение доменных сущностей;
- классификацию изменений;
- оценку значимости изменений;
- генерацию обучающих материалов;
- AI/RAG-поиск по изменениям.

Главная задача этого документа — убрать архитектурную неоднозначность и зафиксировать, **какие слои системы существуют, за что каждый отвечает, какие модули rule-based, какие AI-based, и где именно интегрируются LLM/NLP-компоненты**.

---

## 2. Архитектурный принцип

Архитектура проекта строится как **pipeline интеллектуального анализа НПА**, в котором AI-модули не являются декоративной надстройкой, а встроены в основной пользовательский сценарий.

Система состоит из следующих логических слоёв:

1. **document/version layer**
2. **diff layer**
3. **retrieval layer**
4. **AI analysis layer**
5. **quiz/assessment layer**

---

## 3. Высокоуровневая схема

```text
[Загрузка документа/версии]
          |
          v
[Document / DocumentVersion]
          |
          v
[Извлечение текста -> нормализация -> chunking]
          |
          +---------------------> [Chunk index / Retrieval index]
          |
          v
[Diff между версиями]
          |
          v
[Изменённые фрагменты / change candidates]
          |
          v
[AI Analysis Layer]
  - entity extraction
  - change type classification
  - importance assessment
  - AI summary
          |
          +---------------------> [AI/RAG поиск по изменениям]
          |
          v
[Quiz / Assessment Layer]
  - quiz generation
  - quiz quality control
  - attempts
  - analytics
4. Слои системы
4.1. Document / Version Layer
Назначение

Слой отвечает за жизненный цикл документов и их версий.

Основные обязанности

загрузка документа;

загрузка новой версии документа;

хранение исходного файла;

извлечение текста;

нормализация текста;

разбиение текста на структурные фрагменты (chunks);

сохранение структурного представления версии.

Основные сущности

Document

DocumentVersion

Chunk

Характер реализации

Преимущественно rule-based / deterministic

Этот слой не должен зависеть от LLM.
Он должен быть воспроизводимым, тестируемым и стабильным.

Что относится к этому слою в текущем проекте

модели документов и версий;

извлечение текста;

нормализация текста;

структурный chunking.

Что важно архитектурно

Document/version layer — это фундамент всей системы.
AI не должен заменять этот слой.
AI работает поверх подготовленных текстовых и структурных данных.

4.2. Diff Layer
Назначение

Слой отвечает за сравнение двух версий документа и формирование структурированного diff.

Основные обязанности

сопоставление chunk'ов между версиями;

определение:

unchanged;

added;

removed;

modified;

moved;

формирование технического diff;

подготовка change candidates для AI-анализа.

Вход

from_version

to_version

их chunks

Выход

Структурированное представление изменений:

summary;

список добавленных фрагментов;

список удалённых фрагментов;

список изменённых фрагментов;

список перемещённых фрагментов;

text diff.

Характер реализации

Rule-based / heuristic-based

Diff layer должен быть объяснимым и детерминированным.
Он не должен зависеть от LLM, потому что является базовым инженерным механизмом сравнения.

Роль в AI-архитектуре

Diff layer не является AI-слоем, но именно он поставляет входные данные для AI analysis layer.

AI не сравнивает документы “с нуля” вместо diff.
AI анализирует уже найденные изменения.

4.3. Retrieval Layer
Назначение

Слой отвечает за поиск по документам, версиям, chunks и в дальнейшем — по изменениям.

Основные обязанности

индексация chunk'ов;

хранение эмбеддингов;

semantic search;

lexical + semantic retrieval;

фильтрация по документу, версии, режиму latest_only;

подготовка контекста для AI/RAG-ответов.

Основные типы retrieval
4.3.1. Chunk retrieval

Поиск по текстовым фрагментам документов.

4.3.2. Change retrieval

Поиск не просто по chunks, а по уже вычисленным изменениям:

что изменилось в сроках;

какие документы добавились;

что изменилось в обязанностях;

какие основания отказа были изменены.

4.3.3. Hybrid retrieval

Комбинация:

lexical matching;

vector similarity;

metadata filtering.

Характер реализации

Hybrid: rule-based + AI-based

Rule-based часть:

фильтрация;

метаданные;

lexical bonus;

ограничение домена поиска.

AI-based часть:

эмбеддинги;

semantic similarity;

RAG-контекст.

Важное архитектурное правило

Retrieval layer не должен напрямую “выдумывать” выводы.
Он только находит релевантный контекст.
Интерпретация принадлежит AI analysis layer или RAG answer layer.

4.4. AI Analysis Layer
Назначение

Это центральный интеллектуальный слой проекта.

Именно он превращает технический diff в прикладной анализ изменений НПА.

Подмодули слоя
4.4.1. Entity Extraction

Извлечение доменных сущностей из изменённых фрагментов.

Минимальные целевые сущности:

service

required_document

deadline

obligation

condition

refusal_reason

applicant_category

authority_unit

4.4.2. Change Type Classification

Классификация типа изменения.

Минимальные классы:

deadline_change

required_document_change

obligation_change

service_procedure_change

refusal_reason_change

structural_change

editorial_change

4.4.3. Importance Assessment

Оценка значимости изменения.

Минимальные классы:

critical

important

informational

editorial

4.4.4. AI Summary

Генерация интерпретируемой сводки по изменению.

Минимальный ожидаемый результат:

что изменилось;

кого касается;

практическое значение;

что должен запомнить сотрудник.

4.4.5. RAG Answering over Changes

Ответы на прикладные вопросы по изменениям на основе retrieval + AI generation.

Примеры вопросов:

Что изменилось в сроках?

Какие новые документы теперь требуются?

Что изменилось в обязанностях сотрудника?

Какие основания отказа были добавлены или изменены?

4.4.6. Режимы работы AI-анализа

AI analysis layer должен поддерживать 3 режима:

rules_only

Используются только rule-based / heuristic методы.

Применение:

baseline;

отладка;

воспроизводимые эксперименты;

fallback без LLM.

hybrid

Сначала выполняются rule-based методы, затем AI дополняет или уточняет результат.

Применение:

основной практический режим;

баланс точности, стоимости и объяснимости.

llm_enhanced

AI играет ведущую роль в интерпретации, но не заменяет document/version и diff слои.

Применение:

расширенный demo;

сравнение качества;

исследовательские эксперименты.

Характер реализации подмодулей
Entity extraction

baseline: rule-based

advanced: LLM/NLP

целевой режим: hybrid

Change type classification

baseline: rule-based / weak supervision

advanced: LLM / NLP classifier

целевой режим: hybrid

Importance assessment

baseline: rule-based scoring

advanced: LLM-based assessment

целевой режим: hybrid

Summary

baseline: template / rule-based summary

advanced: LLM summary

целевой режим: hybrid или llm_enhanced

RAG answering

retrieval: hybrid

answer generation: LLM-based

citations/sources: обязательны

4.5. Quiz / Assessment Layer
Назначение

Слой отвечает за генерацию обучающих материалов и оценку усвоения изменений.

Основные обязанности

генерация вопросов по изменениям;

генерация explanation;

фильтрация слабых вопросов;

сохранение quiz;

прохождение quiz;

сохранение попыток;

аналитика результатов.

Подмодули
4.5.1. Quiz Generation

Вход:

diff;

entities;

change_type;

importance;

summary.

Выход:

набор вопросов;

ответы;

explanations;

метаданные покрытия.

4.5.2. Quiz Quality Control

Фильтрует:

бессмысленные вопросы;

дубли;

вопросы по чисто редакционным правкам;

вопросы без практической ценности.

4.5.3. Quiz Attempts

попытки;

scoring;

история;

аналитика ошибок.

Характер реализации

Hybrid

Rule-based часть:

шаблонные вопросы;

проверка структуры;

оценка покрытия;

фильтрация редакционных изменений.

AI-based часть:

генерация качественных вопросов;

explanation;

переформулировка;

адаптация сложности.

5. Что является rule-based, а что AI-based
Модуль	Тип
Загрузка документа	rule-based
Хранение версий	rule-based
Извлечение текста	rule-based
Нормализация текста	rule-based
Chunking	rule-based
Сравнение версий / diff	rule-based / heuristic
Индексация chunk'ов	rule-based
Векторные эмбеддинги для retrieval	AI-based
Semantic search	AI-based
Lexical scoring / metadata filtering	rule-based
Baseline entity extraction	rule-based
LLM/NLP entity extraction	AI-based
Baseline change classification	rule-based
LLM-based change classification	AI-based
Baseline importance scoring	rule-based
LLM-based importance assessment	AI-based
Brief summary по шаблону	rule-based
AI summary	AI-based
Базовая генерация quiz по diff	rule-based
LLM quiz generation	AI-based
Quiz quality control	hybrid
Quiz scoring / attempts	rule-based
RAG answer generation	AI-based
6. Точки интеграции LLM и NLP-моделей

LLM/NLP интегрируются не во все части системы, а только в те точки, где действительно нужна интеллектуальная интерпретация.

Точка 1. Entity extraction over changed chunks

Вход:

изменённый фрагмент;

heading;

section_path;

тип операции diff.

Выход:

список сущностей с типом;

значение;

span / source_text;

confidence;

extraction_mode.

Точка 2. Change type classification

Вход:

old_text;

new_text;

diff metadata;

extracted entities.

Выход:

change_type;

confidence;

explanation.

Точка 3. Importance assessment

Вход:

diff fragment;

entities;

change_type.

Выход:

importance;

rationale;

confidence.

Точка 4. AI summary

Вход:

old_text;

new_text;

diff;

entities;

change_type;

importance.

Выход:

short_summary;

practical_impact;

employee_recommendation.

Точка 5. Quiz generation

Вход:

summary;

entities;

change_type;

importance;

source fragment.

Выход:

questions;

answers;

explanations;

difficulty / importance tags.

Точка 6. RAG answer generation

Вход:

user_query;

retrieved chunks / changes;

metadata.

Выход:

grounded answer;

sources;

optional concise explanation.

7. Границы ответственности LLM

LLM не должен:

хранить документы;

определять версии;

заменять diff engine;

быть единственным источником истины;

отвечать без источников в retrieval/RAG-сценариях;

подменять детерминированные инженерные функции.

LLM должен:

интерпретировать уже найденные изменения;

извлекать доменные сущности;

классифицировать смысл изменений;

генерировать summary и quiz;

помогать отвечать на прикладные вопросы по найденным данным.

8. Целевой pipeline обработки изменений
8.1. Pipeline сравнения версий

Загружается версия документа.

Извлекается текст.

Текст нормализуется.

Выполняется chunking.

Chunk'и сохраняются в БД.

Chunk'и индексируются в retrieval layer.

Для пары версий строится diff.

Diff формирует список changed fragments.

8.2. Pipeline AI-анализа изменений

Берутся changed fragments из diff layer.

Для каждого changed fragment выполняется entity extraction.

Затем определяется change type.

Затем определяется importance.

Затем строится summary.

Результаты сохраняются как артефакты анализа.

8.3. Pipeline quiz generation

Берутся результаты AI-анализа.

Выбираются значимые изменения.

Генерируются вопросы.

Выполняется quality control.

Quiz сохраняется.

Пользователь проходит quiz.

Attempt и score сохраняются.

8.4. Pipeline RAG over changes

Пользователь задаёт вопрос.

Retrieval layer ищет релевантные chunks и/или changes.

Формируется контекст.

LLM строит grounded answer.

Ответ возвращается со ссылкой на источники.

9. Оркестрация режимов

Для всех AI-задач должен существовать единый orchestration layer.

Поддерживаемые режимы
RULES_ONLY

Используются только:

regex;

словари;

шаблоны;

scoring rules.

HYBRID

Порядок:

baseline result;

AI enrichment;

conflict resolution;

final merged result.

LLM_ENHANCED

Порядок:

deterministic preprocessing;

AI interpretation;

post-validation;

structured output.

Архитектурное правило

Режим выбирается централизованно, а не отдельно внутри каждого endpoint.
Это нужно для:

единообразия;

экспериментов baseline vs hybrid vs llm;

воспроизводимости.

10. Предлагаемое логическое разбиение модулей в коде

Чтобы не ломать проект радикальным рефакторингом, архитектуру фиксируем логически, сохраняя текущую основу.

Вариант целевой структуры
backend/
  documents/
    models.py
    api.py
    text_extractors.py
    text_processing.py

    services/
      versioning_service.py
      diff_service.py
      retrieval_service.py

    ai/
      orchestrator.py
      entity_extraction.py
      change_classification.py
      importance_assessment.py
      summary_generation.py
      quiz_generation.py
      rag_answering.py

    prompts/
      entity_extraction.txt
      change_classification.txt
      importance_assessment.txt
      summary_generation.txt
      quiz_generation.txt

    repositories/
      analysis_repository.py
      quiz_repository.py

Если без новых папок, допустим и более мягкий вариант:

documents/
  diff.py
  qdrant_service.py
  ai_orchestrator.py
  ai_entities.py
  ai_change_types.py
  ai_importance.py
  ai_summary.py
  ai_quiz.py
  ai_rag.py
11. Что считается архитектурно правильным состоянием проекта после фиксации этого документа

Система должна пониматься так:

document/version layer готовит данные;

diff layer находит изменения;

retrieval layer ищет релевантный контекст;

AI analysis layer интерпретирует изменения;

quiz/assessment layer превращает анализ в обучающий контур.

То есть проект развивается по формуле:

версии документов -> diff -> AI-анализ изменений -> обучение и поиск по изменениям

12. Что нельзя делать дальше

Чтобы снова не уйти в сторону, дальше нельзя развивать проект как:

просто CRUD документов;

просто поиск по chunk'ам без анализа изменений;

просто генератор quiz без доменного AI-анализа;

просто чат с LLM без document/version и diff базы;

просто summary без entity/change/importance pipeline.

Любая следующая разработка должна усиливать именно эту архитектуру.

13. Следствие для следующих этапов разработки

После фиксации этой архитектуры дальнейшие шаги идут в таком порядке:

demo-корпус под НПА/МФЦ;

target schema сущностей;

baseline entity extraction;

LLM-based entity extraction;

change type classification;

importance assessment;

AI summary;

AI quiz generation;

AI/RAG over changes;

orchestration layer;

сохранение AI-анализа в БД;

UI интеллектуального анализа.

14. Итоговая формула AI-слоя

AI-слой проекта — это не один “чат с LLM”, а набор согласованных интеллектуальных модулей, встроенных в pipeline анализа НПА:

retrieval-aware,

diff-aware,

domain-aware,

explainable,

пригодный для baseline / hybrid / llm comparison.

Именно такая архитектура соответствует теме магистерской диссертации и создаёт основу для дальнейшей реализации исследовательской части.


---