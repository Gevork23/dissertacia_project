# Annotation Studio

## Назначение

Annotation Studio добавляет в проект `dissertacia_project` экспертный human-in-the-loop слой, предназначенный для накопления gold annotations поверх уже materialized результатов интеллектуального pipeline.

Фаза не изменяет core algorithms и не пересчитывает pipeline. Она добавляет отдельный исследовательский контур, в котором эксперт может проверить и скорректировать:

- semantic type изменения;
- significance label;
- флаг `requires_manual_review`;
- качество summary highlight;
- качество quiz question;
- экспертные комментарии.

## Поддерживаемые типы экспертной разметки

### 1. GoldChangeAnnotation

Связана с `VersionChangeItem` и позволяет сохранить:

- исправленный semantic type;
- исправленный significance label;
- исправленный `requires_manual_review`;
- relevance;
- false positive marker;
- комментарий эксперта.

### 2. GoldSummaryAnnotation

Связана с `Summary` и highlight-уровнем внутри `Summary.highlights`. Используется для оценки качества краткой выжимки:

- `good`
- `partially_correct`
- `unsupported`
- `missing_key_point`
- `overemphasized_noise`

Также допускает сохранение исправленного текста и комментария.

### 3. GoldQuizAnnotation

Связана с `Question` и предназначена для оценки качества quiz generation:

- `good`
- `partially_correct`
- `incorrect`
- `irrelevant`
- `ambiguous`
- `unsupported`

Дополнительно сохраняются:

- corrected question text;
- corrected explanation;
- `should_keep`;
- комментарий.

## Добавленные модели

В рамках фазы добавлены:

- `GoldChangeAnnotation`
- `GoldSummaryAnnotation`
- `GoldQuizAnnotation`

Эти модели не заменяют существующую moderation-модель и не ломают текущий workflow. Они дополняют систему как research-grade слой накопления эталонной разметки.

## Связь с Traceability View и Research Dashboard

Annotation Studio логически продолжает предыдущие две фазы:

- Research Dashboard показывает итоговые исследовательские артефакты и метрики;
- Traceability View показывает explainable chain от change item до summary, quiz и attempts;
- Annotation Studio позволяет эксперту зафиксировать оценку качества каждого участка этой цепочки.

Таким образом, проект получает не только визуализацию результатов, но и контур накопления проверенной экспертной разметки.

## Экспорт annotations

Поддерживаются два export endpoint:

- `/demo/annotations/export.json`
- `/demo/annotations/export.csv`

JSON содержит три массива:

- `change_annotations`
- `summary_annotations`
- `quiz_annotations`

CSV экспортирует единый flat-поток записей с полем `annotation_type` и колонками:

- `annotation_type`
- `object_id`
- `comparison_id`
- `document_id`
- `annotator`
- `field`
- `value`
- `comment`
- `created_at`
- `updated_at`

Такой формат подходит для дальнейшего анализа, подготовки regression/gold corpora и последующего ML-эксперимента.

## Почему эта фаза не меняет core algorithms

Annotation Studio работает только поверх уже сохранённых сущностей:

- `VersionComparison`
- `VersionChangeItem`
- `Summary`
- `GeneratedQuiz`
- `Question`
- `QuizAttempt`

Ни extraction, ни chunking, ни diff, ни significance, ни summary generation, ни quiz generation не были изменены.

## Ограничения

- качество аннотации summary зависит от того, был ли `source_change_item_id` materialized в `Summary.highlights`;
- качество аннотации quiz зависит от наличия `Question.source_change_item`;
- текущая реализация хранит одно актуальное annotation на пользователя и объект, а не полную историю revisions;
- Annotation Studio не пересчитывает downstream artifacts после сохранения annotation;
- экспорт не является полноценным audit log.

## Следующие логические фазы

Annotation Studio подготавливает проект к следующим фазам:

- Real-world Regression Suite
- ML significance experiment
- Audit Log
- Export Reports
