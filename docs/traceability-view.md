# Traceability View

## Назначение

Traceability View предназначен для демонстрации объяснимой цепочки преобразований внутри магистерского проекта `dissertacia_project`. Страница показывает, как конкретное изменение между версиями документа проходит через уже существующие слои системы и превращается в обзорное описание, тестовый вопрос и, при наличии, результат прохождения пользователем.

Основная цель фазы — усилить объяснимость, проверяемость и демонстрационную убедительность проекта без изменения алгоритмического ядра.

## Отображаемая цепочка

Traceability View визуализирует следующую последовательность:

`DocumentVersion -> Chunk -> VersionChangeItem -> Summary highlight -> Quiz question -> Answer choice -> Quiz attempt result`

Фактически страница показывает:

- пару сравниваемых версий документа;
- materialized change items для `VersionComparison`;
- semantic type и significance label изменения;
- текстовое объяснение значимости, если оно сохранено;
- связь с `Summary.highlights` через `source_change_item_id`;
- связь с `Question.source_change_item`;
- варианты ответов и правильный ответ;
- результаты попыток, если для вопроса существуют связанные `Answer` и `QuizAttempt`.

## Участвующие сущности

В текущей архитектуре в трассировке участвуют:

- `Document`
- `DocumentVersion`
- `Chunk`
- `VersionComparison`
- `VersionChangeItem`
- `Summary`
- `GeneratedQuiz`
- `Question`
- `Choice`
- `QuizAttempt`
- `Answer`

## Полные и частичные связи

### Полные связи

Наиболее надёжно в текущем проекте строятся следующие связи:

- `VersionComparison -> VersionChangeItem`
- `VersionChangeItem -> old_chunk / new_chunk`
- `GeneratedQuiz -> Question -> Choice`
- `Question -> source_change_item`
- `Answer -> Question -> QuizAttempt`

### Частичные или отсутствующие связи

Некоторые участки цепочки могут быть неполными:

- не у каждого `VersionChangeItem` обязательно есть связанный summary highlight;
- не каждое изменение попадает в quiz generation;
- не по каждому вопросу существуют attempt results;
- source chunk links могут отсутствовать в fallback-сценариях, если materialized change item был создан без chunk reference.

В таких случаях интерфейс сознательно показывает `missing` или `partial`, а не скрывает неполноту.

## Почему это важно для explainability

Traceability View важен по следующим причинам:

- позволяет показать комиссии не только итоговые артефакты, но и путь их происхождения;
- упрощает верификацию корректности quiz generation;
- демонстрирует, что downstream-артефакты опираются на конкретные изменения в нормативном тексте;
- поддерживает научную честность: пропущенные связи отображаются явно.

## Что фаза не делает

Данная фаза не изменяет:

- алгоритмы extraction, normalization, chunking, diff, significance, summary и quiz generation;
- существующие модели данных и миграции;
- experiment artifacts;
- исследовательские результаты.

Traceability View реализован как read-only слой поверх уже сохранённых сущностей.

## Связь с Research Dashboard

Research Dashboard показывает уже рассчитанные исследовательские метрики и артефакты на уровне метода и экспериментов. Traceability View работает на другом уровне: он объясняет происхождение конкретного прикладного результата внутри demo-сценария.

Таким образом:

- Research Dashboard отвечает на вопрос «какие результаты получены по методу в целом»;
- Traceability View отвечает на вопрос «как конкретный вопрос и результат были получены из конкретного изменения документа».

## Ограничения

- качество трассировки ограничено уже сохранёнными связями;
- если некоторый bridge не был materialized на предыдущих этапах, страница не пытается искусственно его восстановить;
- текущая версия не добавляет audit log и не формирует экспортируемый отчёт по трассе;
- страница не пересчитывает pipeline и не запускает эксперименты во время HTTP request.

## Следующие логические фазы

Traceability View подготавливает проект к следующим этапам развития:

- Annotation Studio
- Audit Log
- Export Reports
- ML significance experiment
