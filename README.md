# ДГТУ — интеллектуальная система анализа нормативно-правовых документов

## О проекте

Проект разрабатывается как магистерская работа по направлению 09.04.02 «Информационные системы и технологии» и как прикладной инструмент для локального анализа изменений в нормативных и внутренних регламентных документах.

Базовая формулировка проекта:

**Интеллектуальная система анализа нормативно-правовых документов, обеспечивающая выявление значимых изменений, генерацию кратких разъяснений и формирование тестовых материалов для проверки знаний сотрудников.**

Ключевая идея проекта — не общий чат по законам и не универсальный юридический ассистент, а **прикладной конвейер работы с версиями одного документа**:

**документ → версии → изменения → выжимка → генерация теста → утверждение → прохождение → отчёт**

## Текстовые стадии документа

Для `DocumentVersion` теперь важно различать несколько представлений текста:

- `file` — исходный бинарный артефакт версии документа;
- `extracted_text` — извлечённый формат-зависимый текст после TXT / DOCX / PDF extraction;
- `normalized_text` — детерминированное и воспроизводимое представление для chunking, diff и последующей аналитики.

В текущем контуре `normalized_text` формируется единым materialization-stage:

**file -> extraction -> normalization -> chunks -> diff -> significance -> summary -> quiz**

Для PDF текущий MVP делает только безопасную предобработку без OCR:

- сохраняет page boundaries на стадии extraction;
- убирает повторяющиеся header / footer строки при безопасном совпадении между страницами;
- убирает standalone page numbers и machine-like stamp markers;
- склеивает переносы слов и часть line-wrap артефактов;
- не пытается агрессивно перестраивать юридическую структуру документа.

## Structural chunks: что считается единицей анализа

После Фазы 7 `normalized_text` materialize-ится не в плоские блоки, а в **структурные фрагменты** (`Chunk`) с сохранением порядка и привязки к `DocumentVersion`.

В MVP поддерживаются:

- `title` — заголовок документа перед основной структурой;
- `preamble` — вводные блоки до первой статьи / главы / раздела;
- `section` / `chapter` — контекст верхнего уровня и body-блоки, если текст расположен непосредственно под ними;
- `article` — тело статьи, если внутри нет более мелкой нумерации;
- `point` — пункты вида `1.` / `2.` / `Пункт 3`;
- `subpoint` — подпункты вида `1.1.` / `1)` / `а)` / `подпункт ...`;
- `paragraph` — явно размеченные абзацы;
- `fallback_block` — честная деградация для слабо структурированных документов.

Для каждого чанка сохраняются:

- `fragment_type`;
- `structure_level`;
- `raw_label`;
- `canonical_label`;
- `path_key`;
- `heading`;
- `section_path`;
- `text` и `text_hash`.

`path_key` используется как машинный anchor для дальнейшего сопоставления редакций, а `heading` / `section_path` остаются человекочитаемыми полями для API, demo и отчётности.

## Comparison layer: базовый version diff поверх structural chunks

После Фазы 8 compare-контур работает по следующим правилам:

- primary comparison unit — `Chunk`;
- primary matching strategy — `path_key`, затем `canonical_label + fragment_type`, затем точный `section_path`-anchor;
- exact-text fragments с устойчивым anchor считаются `unchanged`, даже если их `chunk_index` сместился из-за вставки нового пункта в середину документа;
- `modified` строится сначала по устойчивым anchor, а затем по ограниченному fallback-matching с similarity и близостью позиции;
- `added` / `removed` materialize-ятся только после исчерпания безопасных match-сценариев;
- `moved` в текущем MVP не используется как основной diff-результат: exact-text renumbering/reordering трактуется как `unchanged`, чтобы не путать структурный сдвиг с содержательным изменением;
- если chunk layer отсутствует хотя бы у одной версии, compare честно деградирует в `document_text` fallback вместо ложного `identical`.

Materialized `VersionComparison` теперь хранит не только статус пары версий, но и:

- `comparison_unit`;
- `matching_strategy`;
- `identical`;
- агрегированные счётчики `added / removed / modified / moved / unchanged`.

`VersionChangeItem` дополнен снимками `old_text` / `new_text`, поэтому materialized diff остаётся объяснимым даже в fallback-сценарии без chunk-ссылок.

## Significance layer: baseline-классификация значимости изменений

После Фазы 9 materialized diff дополняется отдельным explainable significance-слоем.

Для каждого `VersionChangeItem` теперь материализуются:

- `semantic_type` — содержательный тип изменения (`deadline`, `document`, `procedure`, `editorial`, `unclassified` и др.);
- `significance_label` — baseline-уровень значимости (`critical`, `important`, `informational`, `editorial`);
- `significance_score` — rule-based confidence / priority score в диапазоне `0.0..1.0`;
- `significance_reason` и `significance_rules` — explainability-слой для demo, summary и quiz;
- `requires_manual_review` — честный флаг для неоднозначных случаев, где baseline-эвристик недостаточно.

Текущий MVP intentionally использует **deterministic rule-based baseline**, а не обязательный LLM/ML decision layer. Это делает классификацию воспроизводимой, проверяемой тестами и удобной для объяснения комиссии.

Краткая выжимка и генерация квиза теперь работают не по первым diff-элементам подряд, а по **prioritized change items**: сначала `critical` / `important`, затем `informational`, а редакционные изменения используются как fallback.

Summary layer в текущем MVP реализован как materialized human-readable слой поверх `VersionComparison`:

- `Summary.text` хранит общий narrative/overview по наиболее значимым изменениям;
- `Summary.highlights` хранит структурированные пункты brief, а не просто текстовые строки;
- каждый пункт brief содержит `type`, `title`, `concise_explanation`, `semantic_type`, `significance_label`, `requires_manual_review`;
- в materialized summary дополнительно сохраняется `source_change_item_id`, что позволяет прозрачно связать пункт выжимки с `VersionChangeItem` и использовать этот bridge в следующих фазах.

## Что реально есть в текущем состоянии репозитория

В репозитории уже реализованы:

- Django backend и DRF API;
- модели документов, версий, чанков, квизов и попыток;
- загрузка версий документов;
- извлечение текста из TXT, DOCX и PDF с текстовым слоем;
- структурное разбиение текста на фрагменты;
- сравнение двух версий документа;
- baseline-классификация и приоритизация значимости изменений;
- краткая выжимка по изменениям;
- генерация квиза по diff;
- approval workflow для квиза;
- прохождение квиза сотрудником;
- отчёт по результату попытки;
- demo UI на Django templates;
- demo corpus и команда `load_demo_pairs`;
- backend-тесты.

## Важные ограничения текущей версии

Ниже важно писать и говорить о проекте честно:

- PDF поддерживается **без OCR**; корректно работают PDF с извлекаемым текстом;
- demo UI предназначен прежде всего для демонстрационного сценария, а не для полнофункциональной продуктовой эксплуатации;
- семантический поиск и Qdrant — **опциональный слой**, а не опора MVP;
- авторизация и развитая ролевая модель пока не являются центральной частью ранней версии проекта.

## Архитектурный фокус

Главный режим проекта:

**сравнение новой редакции документа с предыдущей редакцией того же документа**

Это означает, что ядро системы должно обеспечивать:

- хранение документов и нескольких редакций;
- извлечение и нормализацию текста;
- структурное разбиение документа;
- детерминированное сравнение редакций;
- формирование объяснимой выжимки;
- генерацию проверочного материала по изменениям;
- фиксацию результатов прохождения.

## Что входит в текущий demo-ready MVP

В текущий demo-ready контур входят:

- загрузка документа и новой версии через backend;
- парсинг TXT / DOCX / PDF с текстовым слоем;
- построение структурных чанков после загрузки;
- compare / brief / quiz API;
- persistent significance layer поверх materialized diff;
- сохранение квиза;
- утверждение квиза ответственным лицом;
- прохождение квиза сотрудником;
- просмотр попыток и отчёта;
- demo-сценарий на подготовленном наборе документов;
- локальный запуск на одном ПК.

## Что не нужно выдавать за уже завершённую часть MVP

Пока не стоит формулировать проект так, будто уже полностью готовы:

- OCR для сканированных PDF;
- развитая auth / roles система;
- универсальный поиск по большому корпусу документов;
- сложная внешняя интеграция;
- production-grade развёртывание.

## Структура репозитория

- `backend/` — Django backend и основной runtime-контур
- `docs/` — материалы для защиты и демонстрации
- `data/` — датасеты и ручные sample-артефакты
- `tools/` — offline-утилиты подготовки и оценки данных
- `infra/` — шаблоны переменных окружения
- `scripts/` — инженерные сценарии проверки и smoke-прогона

### Карта backend

Главная предметная зона находится в `backend/documents/` и после нормализации Фазы 2 разделена по слоям:

- `models.py`, `admin.py` — ORM и административный слой;
- `api/` — DRF serializers, HTTP endpoints и viewsets;
- `demo/` — demo UI на Django templates и deterministic demo corpus;
- `domain/` — сравнение версий, change enrichment, significance-aware quiz/summary logic;
- `services/` — ingestion, significance/importance analysis, optional search/Qdrant, evaluation services;
- `tests/` — тесты app-модуля, сгруппированные по сценариям.

Такое разложение позволяет отдельно объяснять комиссии:

- где находится доменная логика сравнения редакций;
- где находятся интеграционные и служебные сервисы;
- где API-слой;
- где demo-представление;
- где лежат тесты и вспомогательные sample-материалы.

## Документы проекта

- `PROJECT_SCOPE.md` — реальные границы MVP и текущего scope
- `ARCHITECTURE.md` — архитектурные решения и ограничения
- `ROADMAP.md` — функциональные фазы проекта и текущий этап стабилизации
- `TASKS.md` — фактический статус фаз и задач
- `ERD.md` — модель данных
- `docs/notes.md` — журнал решений
- `docs/demo-script.md` — сценарий показа

## Быстрый старт: локально без Docker

1. Установите зависимости:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

2. Выполните миграции:

```bash
python manage.py migrate
```

3. Запустите backend:

```bash
python manage.py runserver
```

4. Базовые проверки:

```bash
python manage.py check
cd ..
bash ./scripts/test.sh
bash ./scripts/lint.sh
```

## Быстрый старт: Docker Compose

1. Подготовьте переменные окружения:

```bash
cp infra/.env.example infra/.env
```

2. Поднимите backend и Postgres:

```bash
docker compose up --build
```

3. Загрузите демонстрационный набор:

```bash
docker compose exec backend python manage.py load_demo_pairs
```

4. Откройте приложение:

```text
http://localhost:8000/
```

## Опциональный поиск с Qdrant

Qdrant не обязателен для базового demo-сценария. Если нужен поиск, запускайте профиль `search`:

```bash
docker compose --profile search up --build
```

И включайте в `infra/.env`:

```env
QDRANT_ENABLED=1
DB_ENGINE=postgres
```

## Принцип развития проекта

Если новая функция:

- не усиливает сценарий сравнения редакций;
- не повышает устойчивость demo;
- не улучшает объяснимость результата;
- не помогает защите магистерской работы,

то она не должна становиться приоритетом текущего контура.
