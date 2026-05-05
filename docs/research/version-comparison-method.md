# Version Comparison Method

## 1. Назначение документа

Документ формализует этап `C — Comparison` гибридного метода `M = <E, N, S, C, P, G, R>`: алгоритм сопоставления двух редакций нормативного или внутреннего регламентного документа.

Цель Фазы 9 — описать уже реализованный comparison/diff слой как научно и инженерно значимый компонент системы, а не как простой вызов построчного сравнения текста. Формализация опирается на фактическое состояние проекта после Фазы 8: Django-модели, domain-services, workflow-services, API/demo endpoints, тесты и документы Фаз 1–8.

Документ пригоден как основа для подраздела диссертации `2.6. Сравнение редакций и выявление изменений` или для близкого подраздела главы 2 о методе сопоставления редакций нормативно-правового документа.

## 2. Контекст задачи

Проект реализует локальную интеллектуальную систему для работы с нормативно-правовыми и внутренними регламентными документами. MVP pipeline зафиксирован как:

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

Comparison находится после extraction, normalization и structural chunking. Это принципиально: система сравнивает не исходные файлы и не произвольные строки, а материализованные структурные фрагменты `Chunk`, полученные на этапе `S`.

Фактические документы Фаз 1–8, найденные в архиве и использованные для сверки:

| Документ | Статус | Роль для Фазы 9 |
|---|---|---|
| `PROJECT_SCOPE.md` | найден | Фиксирует MVP scope, version-first pipeline, out-of-scope ограничения. |
| `ROADMAP.md` | найден | Относит version comparison method к research packaging, а diff evaluation — к будущей Фазе 15. |
| `TASKS.md` | найден | Фиксирует Фазу 9 как `version comparison method`, а Фазу 15 как `diff evaluation`. |
| `docs/scope/mvp-freeze.md` | найден | Фиксирует core pipeline: `VersionComparison` и `VersionChangeItem` как MVP-артефакты. |
| `docs/research/hybrid-method.md` | найден | Определяет `C — comparison` как этап метода `M`. |
| `docs/research/structural-chunking-method.md` | найден | Формализует вход comparison: ordered structural chunks с `path_key`, `section_path`, `heading`, `text_hash`. |
| `docs/architecture/system-architecture.md` | найден | Описывает layered local-first Django architecture и связь `C` с Domain/Application/Persistence layers. |
| `docs/architecture/erd.md` | найден | Описывает `VersionComparison`, `VersionChangeItem`, связи с `Chunk`, `Summary`, `GeneratedQuiz`, `Question`. |
| `docs/architecture/service-boundaries.md` | найден | Фиксирует, что `workflows.py` координирует diff payload, materialization comparison/summary/quiz. |
| `docs/architecture/llm-fallback-modes.md` | найден | Подтверждает, что LLM не является обязательным ядром MVP; comparison не зависит от LLM. |

## 3. Роль comparison в гибридном методе

Гибридный метод проекта задан как:

```text
M = <E, N, S, C, P, G, R>
```

где:

- `E` — extraction текста из входного файла;
- `N` — normalization извлечённого текста;
- `S` — structural segmentation / chunking;
- `C` — comparison двух редакций;
- `P` — prioritization / significance classification;
- `G` — generation summary и quiz;
- `R` — result fixation и reporting.

Этап `C` получает результат этапа `S`:

```text
S(old_version.normalized_text) → old_version_chunks
S(new_version.normalized_text) → new_version_chunks
C(old_version_chunks, new_version_chunks) → comparison_result, change_items
```

Далее результат `C` становится входом для `P`:

```text
C(changes) → P(significance_label, significance_score, significance_reason, manual_review_flag)
```

Именно comparison задаёт backbone downstream pipeline. Без набора найденных изменений невозможно корректно:

- классифицировать значимость изменений;
- построить краткую выжимку по изменениям;
- сгенерировать проверочный quiz;
- связать вопрос quiz с конкретным `VersionChangeItem`;
- объяснить пользователю, какой фрагмент документа стал причиной вопроса.

## 4. Почему простого text diff недостаточно

Plain text diff сравнивает последовательность строк. Для нормативных документов это создаёт несколько проблем:

1. **Чувствительность к форматированию.** Переносы строк, PDF page breaks, колонтитулы и технические артефакты могут выглядеть как изменения, хотя правовая формулировка не изменилась.
2. **Потеря структурного контекста.** Строка сама по себе не сообщает, относится ли изменение к статье, пункту, подпункту или преамбуле.
3. **Шум при вставках.** Вставка нового пункта может сдвинуть последующие строки и породить каскад ложных изменений.
4. **Слабая пригодность для downstream.** Significance и quiz generation должны работать с содержательными фрагментами, а не с техническими строками unified diff.

Paragraph diff лучше plain text diff, но всё ещё недостаточен: абзац не всегда соответствует нормативной единице. Внутренний регламент может содержать `Раздел → Глава → Статья → Пункт → Подпункт`, и простая абзацная сегментация не даёт устойчивого `path_key` для сопоставления редакций.

В проекте реализован structural chunk diff: сначала документ переводится в ordered structural chunks, затем сравниваются chunks с учётом их structural anchors, порядка и текстовых хэшей.

## 5. Входные и выходные данные

### 5.1 Вход

Основной вход comparison layer:

```text
from_version: DocumentVersion
  └── from_chunks: list[Chunk]

to_version: DocumentVersion
  └── to_chunks: list[Chunk]
```

Фактические поля `Chunk`, используемые или сериализуемые comparison layer:

| Поле | Роль в comparison |
|---|---|
| `id` | Связь materialized change item с конкретным old/new chunk. |
| `chunk_index` | Порядок фрагмента; используется для сортировки, `same_index` и index proximity. |
| `fragment_type` | Тип структурного фрагмента; участвует в anchor key и scoring. |
| `structure_level` | Сериализуется как структурная метаинформация; напрямую в matching score не участвует. |
| `raw_label` | Сериализуется; используется downstream для отображения. |
| `canonical_label` | Anchor для exact hash pairing и modified pairing. |
| `path_key` | Наиболее сильный structural anchor для сопоставления изменённых chunks. |
| `section_path` | Человекочитаемый структурный путь; anchor и fallback-признак. |
| `heading` | Заголовок/контекст; участвует в section path anchor и fallback matching. |
| `text` | Текст фрагмента; используется для similarity и snapshots. |
| `text_hash` | SHA-256 текста chunk; используется для exact unchanged detection. |

Если у одной из версий отсутствуют chunks, алгоритм переходит к fallback-режиму сравнения текста документа целиком:

```text
from_text = from_version.normalized_text or from_version.extracted_text or ""
to_text = to_version.normalized_text or to_version.extracted_text or ""
```

### 5.2 Выход

Непосредственный output `build_version_diff` / `build_comparison_payload` — diff payload:

```text
{
  from_version,
  to_version,
  comparison_meta,
  identical,
  summary,
  added,
  removed,
  modified,
  moved,
  text_diff
}
```

При materialization через `materialize_comparison` output сохраняется в БД:

- `VersionComparison` — сравнение пары версий;
- `VersionChangeItem` — материализованные изменения;
- `Summary` — краткая выжимка по результатам comparison;
- при создании quiz — `GeneratedQuiz`, `Question`, `Choice` со ссылками на `VersionChangeItem`.

Карта research-аудита comparison layer:

| Аспект | Реализация в проекте | Комментарий |
|---|---|---|
| Input | `from_version`, `to_version`, их `Chunk` rows | Основной режим — structural chunks. |
| Fallback input | `normalized_text` / `extracted_text` | Используется, если chunks отсутствуют хотя бы у одной версии. |
| Output payload | `added`, `removed`, `modified`, `moved`, `summary`, `text_diff` | Runtime/API output. |
| Materialized output | `VersionComparison`, `VersionChangeItem`, `Summary` | Создаётся в workflow при сохранении quiz/materialization. |
| Matching keys | `text_hash`, `path_key`, `canonical_label`, `section_path`, `heading`, `fragment_type`, `chunk_index`, text similarity | Сочетание exact hash и structural/text heuristics. |
| Statuses | `added`, `removed`, `modified`, `moved`; `unchanged` как счётчик | `moved` есть в модели/schema, но текущий core algorithm фактически не создаёт moved items. |
| Similarity | `SequenceMatcher(...).ratio()` для modified/document fallback | Не embedding similarity. |
| Confidence | Отдельного confidence для matching нет | Есть downstream `significance_score`, но это не confidence сопоставления chunks. |
| Downstream usage | significance, summary, quiz, demo UI, API | Comparison является центральным backbone pipeline. |

## 6. Выбор сравниваемых версий

Фактическое правило выбора пары версий реализовано в `validate_version_pair` и дополнительно проверяется в API/demo:

1. `from_version` и `to_version` должны принадлежать одному `Document`.
2. Версии должны быть различными.
3. `from_version.version_number < to_version.version_number`.
4. `to_version` должна быть более новой редакцией относительно `from_version`.

Важно: алгоритм не ограничивает comparison только соседними версиями. API принимает явные идентификаторы `from_version` и `to_version`; любая пара версий одного документа допустима, если целевая версия новее исходной. Demo document detail предлагает последнюю пару версий как удобный сценарий, но comparison page и API работают с выбранными пользователем version ids.

Проверки на уровне БД:

- `VersionComparison` содержит `UniqueConstraint(from_version, to_version)`;
- `VersionComparison` содержит check constraint, запрещающий сравнение версии самой с собой;
- `VersionComparison.clean()` запрещает разные документы и обратный порядок версий;
- `VersionChangeItem.clean()` проверяет, что `old_chunk` принадлежит `from_version`, а `new_chunk` — `to_version` соответствующего comparison.

При перестроении chunks версии `rebuild_version_chunks` инвалидирует materialized comparisons, связанные с этой версией. Это предотвращает использование устаревших `VersionComparison` и `VersionChangeItem`, построенных на старой chunk-разметке.

## 7. Используемые признаки сопоставления

### 7.1 Structural chunks

`Chunk` является основной единицей сравнения. Алгоритм загружает chunks обеих версий в порядке `chunk_index`:

```text
from_chunks = list(from_version.chunks.order_by("chunk_index"))
to_chunks = list(to_version.chunks.order_by("chunk_index"))
```

Если оба набора chunks присутствуют, используется strategy:

```text
comparison_unit = "chunk"
matching_strategy = "structural_chunks_v2"
```

Если chunks отсутствуют хотя бы у одной стороны, используется:

```text
comparison_unit = "document_text"
matching_strategy = "document_text_fallback_v1"
```

### 7.2 `path_key` / structural path

`path_key` — strongest structural anchor для сопоставления изменённых chunks. Он строится на этапе structural chunking из иерархии нормативных маркеров, например:

```text
section:i/chapter:1/article:5/point:2/subpoint:а
```

В matching он используется двумя способами:

1. В exact hash pairing: chunks с одинаковым `text_hash` сначала пытаются сопоставиться по ключу `fragment_type|path_key`.
2. В modified pairing: unmatched chunks с одинаковым `path_key` считаются соответствующими фрагментами, даже если их текст изменился.

Если `path_key` совпадает, match reason равен `path_key`.

### 7.3 `label` / `type` / `order`

Если `path_key` отсутствует или не дал пару, используются более слабые anchors:

- `canonical_label` вместе с `fragment_type`;
- `section_path` вместе с `heading` и `fragment_type`;
- `heading` вместе с `fragment_type` и порогом similarity;
- `fragment_type` как небольшой additive factor в score;
- `chunk_index` для exact hash `same_index` и index proximity в fallback scoring.

Порядок используется не как единственный критерий, а как стабилизатор:

- группы одинаковых anchor keys сортируются по `chunk_index` и попарно zip-ятся;
- exact same-index pairing помогает определить unchanged chunks с одинаковым text hash;
- proximity bonus добавляется при расстоянии индексов `0`, `1` или `≤ 3`.

### 7.4 `text_hash` / normalized text

`text_hash` — SHA-256 хэш текста chunk, сформированный на этапе `S`. В comparison он используется для exact detection:

```text
if old_chunk.text_hash == new_chunk.text_hash:
    chunk text is identical
```

Алгоритм группирует old/new chunks по `text_hash` и сопоставляет только группы с одинаковым hash. Такие пары не материализуются как `VersionChangeItem`; они увеличивают `unchanged_count`.

`normalized_text` версии используется на двух уровнях:

1. как исходный текст для structural chunking;
2. как fallback input для document-level comparison и `text_diff`.

### 7.5 similarity / confidence, если поддерживается

В проекте есть `similarity`, но это не semantic similarity и не confidence.

Фактическая реализация:

```text
similarity = SequenceMatcher(None, old_chunk.text, new_chunk.text).ratio()
```

Она используется:

- в `score_chunk_match` для fallback matching modified chunks;
- в payload и `VersionChangeItem.similarity` для `modified` items;
- в document-text fallback для synthetic whole-document modified item;
- downstream в summary/quiz как explainable metadata, если поле доступно.

Пороговые значения:

| Константа | Значение | Роль |
|---|---:|---|
| `SECTION_PATH_SIMILARITY_THRESHOLD` | `0.55` | Допускает match по `section_path` при умеренной похожести текста. |
| `TEXT_SIMILARITY_THRESHOLD` | `0.82` | Допускает match по `heading` и `fragment_type`. |
| `HIGH_TEXT_SIMILARITY_THRESHOLD` | `0.97` | Допускает high-text-similarity fallback при близких индексах. |

Отдельного поля `confidence` для качества сопоставления chunks нет. `significance_score` относится к этапу `P`, а не к matching confidence на этапе `C`.

## 8. Общая логика алгоритма

Фактическая логика `build_version_diff`:

1. Проверить пару версий через `validate_version_pair`.
2. Загрузить chunks обеих версий по `chunk_index`.
3. Если chunks отсутствуют хотя бы у одной версии, выполнить document-text fallback.
4. Сопоставить chunks с одинаковым `text_hash` как unchanged:
   - сначала по `path_key`;
   - затем по `canonical_label`;
   - затем по `section_path`;
   - затем по `same_index`;
   - затем ограниченно по remaining exact-text cases.
5. Среди оставшихся chunks сопоставить modified pairs по primary anchors:
   - `path_key`;
   - `canonical_label`;
   - `section_path`.
6. Для оставшихся chunks построить fallback candidates по similarity, heading, fragment type и index proximity.
7. Жадно выбрать лучшие one-to-one modified matches.
8. Всё, что осталось только в old side, классифицировать как `removed`.
9. Всё, что осталось только в new side, классифицировать как `added`.
10. Построить full-version `text_diff` через `difflib.unified_diff` для совместимости и визуальной диагностики.
11. Вернуть payload со summary counters, `comparison_meta`, change groups и `by_type`.

Текущий MVP intentionally conservative относительно moved detection: exact-text reorder/renumbering не создаёт noisy `moved`, а учитывается как `unchanged`.

## 9. Matching chunks

Matching выполняется по убыванию силы признаков.

### 9.1 Strongest match: exact hash + structural anchor

Первый этап — `pair_by_exact_hash`.

Алгоритм группирует chunks обеих версий по `text_hash`. Для каждого общего hash он пытается сопоставить chunks по anchors:

```text
path_key → canonical_label → section_path → same_index
```

Для `path_key` anchor key имеет вид:

```text
fragment_type|path_key
```

Для `canonical_label`:

```text
fragment_type|canonical_label
```

Для `section_path`:

```text
fragment_type|heading|section_path
```

Если в группе несколько кандидатов, old/new группы сортируются по `chunk_index`, после чего применяется `zip`. Это делает matching воспроизводимым.

### 9.2 Exact hash without strong anchors

Если после anchor matching остались chunks с одинаковым `text_hash`:

- если у них нет primary anchors, пары zip-ятся и считаются unchanged;
- если осталась ровно одна old и одна new запись, они тоже считаются unchanged.

Комментарий в коде явно фиксирует MVP-решение: exact-text renumbering/reordering считается unchanged, чтобы не создавать шумные `moved` signals при вставке нового пункта и сдвиге нумерации существующих положений.

### 9.3 Modified by primary anchor

После exact hash pairing остаются chunks с отличающимся текстом. Алгоритм `pair_modified_by_primary_anchor` сопоставляет их по:

```text
path_key → canonical_label → section_path
```

Каждая такая пара материализуется как `modified`, потому что exact hash уже не совпал, а structural anchor показывает, что это один и тот же нормативный фрагмент в новой редакции.

### 9.4 Fallback modified matching

Если primary anchors не дали пару, используется `score_chunk_match`:

```text
base_score = text_similarity(old.text, new.text)
           + index_proximity_bonus
           + fragment_type_bonus
           + structural_anchor_bonus
           + heading_bonus
```

Bonuses:

| Признак | Bonus |
|---|---:|
| same `fragment_type` | `+0.05` |
| same `path_key` | `+0.45` |
| same `canonical_label` | `+0.30` |
| same `section_path` | `+0.20` |
| same `heading` | `+0.10` |
| index distance `0` | `+0.10` |
| index distance `1` | `+0.07` |
| index distance `≤ 3` | `+0.03` |

Fallback reasons:

| `match_reason` | Условие |
|---|---|
| `path_key` | Совпал `path_key`. |
| `canonical_label` | Совпал `canonical_label` и `fragment_type`. |
| `section_path` | Совпал `section_path`, similarity `≥ 0.55`. |
| `heading` | Совпал `heading`, same `fragment_type`, similarity `≥ 0.82`. |
| `high_text_similarity` | Same `fragment_type`, similarity `≥ 0.97`, distance by `chunk_index ≤ 2`. |

Кандидаты сортируются по:

```text
score desc,
similarity desc,
index distance asc
```

После этого применяется greedy one-to-one selection: chunk, уже использованный в одной паре, не может участвовать во второй. Это предотвращает хаотичное many-to-many matching.

## 10. Определение типов изменений

В текущем проекте различаются runtime groups/statuses:

- `added`;
- `removed`;
- `modified`;
- `moved`;
- `unchanged` как счётчик, а не materialized change item.

Фактическая модель `VersionChangeItem.ChangeType` содержит:

```text
added
removed
modified
moved
```

Отдельного `VersionChangeItem` со статусом `unchanged` нет. Unchanged chunks учитываются в `VersionComparison.unchanged_count` и `diff_payload.summary.unchanged`, но не сохраняются как отдельные строки изменений.

### 10.1 `added`

`added` определяется после всех этапов matching: если chunk присутствует в `to_version`, но не был сопоставлен ни exact hash, ни modified matching, он считается добавленным.

Output содержит сериализованный new chunk и `change_classification`.

### 10.2 `removed`

`removed` определяется симметрично: если chunk присутствует в `from_version`, но не был сопоставлен, он считается удалённым.

Output содержит сериализованный old chunk и `change_classification`.

### 10.3 `modified`

`modified` определяется, если old/new chunks сопоставлены по structural/text matching, но их `text_hash` не совпал.

Output содержит:

- `from_chunk`;
- `to_chunk`;
- `similarity`;
- `match_reason`;
- `change_classification`.

### 10.4 `moved`

`moved` присутствует в модели, serializer, summary counters и workflow mapping, но фактический core algorithm в текущем MVP не создаёт moved items. В `pair_by_exact_hash` список `moved` инициализируется и возвращается, однако exact-text reorder/renumbering увеличивает `unchanged_count`, а не `moved_count`.

Следовательно, `moved` является schema-supported / reserved status, но не реализован как активный детектор перемещений в `build_version_diff` на текущей фазе.

### 10.5 `unchanged`

`unchanged` определяется для chunks с одинаковым `text_hash`, которые успешно сопоставлены на exact stage. Такие фрагменты не материализуются как `VersionChangeItem`, потому что не являются изменениями. Они учитываются только в summary counters.

## 11. Таблица типов изменений

| Тип изменения | Описание | Условие определения | Пример | Downstream значение |
|---|---|---|---|---|
| `added` | Фрагмент появился в новой версии | New chunk остался unmatched после exact hash, primary-anchor и fallback matching | Добавлен новый пункт о подаче документов в электронной форме | Может быть значимым; передаётся в significance, summary и quiz. |
| `removed` | Фрагмент исчез из новой версии | Old chunk остался unmatched после всех этапов matching | Удалено требование о нотариально заверенной копии | Часто важно; может привести к critical/important significance. |
| `modified` | Фрагмент сопоставлен, но текст изменился | Chunks сопоставлены по `path_key`, `canonical_label`, `section_path`, `heading` или high text similarity, но `text_hash` различается | Срок изменён с 10 до 7 рабочих дней | Ключевой input для significance; сохраняет old/new text и similarity. |
| `moved` | Фрагмент перенесён | На уровне модели/schema поддержан, но текущий algorithm не emits moved items | Не применяется как активный статус в Фазе 9 | Не следует описывать как реализованную функцию; reserved/future refinement. |
| `unchanged` | Фрагмент не изменился | Совпадает `text_hash`, пара найдена exact hash matching | Текст пункта совпадает в обеих редакциях | Не материализуется как change item; учитывается в counters и снижает шум. |

Подробная таблица с признаками и ограничениями:

| Status | Условие | Используемые признаки | Пример | Ограничения |
|---|---|---|---|---|
| `added` | `new_chunk` не имеет соответствия в old side | Остаток после `text_hash`, anchors, similarity matching | Добавлен новый пункт | Может быть ложным added при нестабильном chunking. |
| `removed` | `old_chunk` не имеет соответствия в new side | Остаток после matching | Удалён пункт | Может быть ложным removed при глубокой переформулировке или изменении структуры. |
| `modified` | Есть matched old/new pair, но тексты различаются | `path_key`, `canonical_label`, `section_path`, `heading`, `fragment_type`, `chunk_index`, `SequenceMatcher` | Изменён срок оказания услуги | Rule-based matching может ошибаться при сильной перефразировке. |
| `moved` | Зарезервировано в модели/schema | В текущем `build_version_diff` active detector отсутствует | — | Не материализуется фактическим алгоритмом MVP. |
| `unchanged` | Тексты chunks идентичны по `text_hash` | `text_hash`, structural anchors, same index | Пункт без изменений | Не хранится как `VersionChangeItem`; доступен только как count. |

## 12. Confidence и качество matching

В comparison layer нет отдельной вероятностной confidence model. Реализованы только deterministic/rule-based признаки и lexical similarity.

Фактические поля:

| Поле | Где хранится | Что означает | Не означает |
|---|---|---|---|
| `similarity` | `modified` payload, `VersionChangeItem.similarity` | Lexical ratio `SequenceMatcher` между old/new text | Не semantic similarity, не embedding score, не юридическая уверенность. |
| `match_reason` | `modified` payload, `VersionChangeItem.match_reason` | Причина сопоставления: `path_key`, `canonical_label`, `section_path`, `heading`, `high_text_similarity`, `document_text_fallback` | Не explainable legal reason. |
| `significance_score` | `VersionChangeItem.significance_score` | Уверенность rule-based importance/significance classifier downstream | Не качество matching на этапе `C`. |

Качество matching в Фазе 9 не оценивается экспериментально. Документ только формализует алгоритм. Экспериментальная проверка запланирована на Фазу 15.

## 13. Materialization comparison results

### 13.1 `VersionComparison`

Модель `VersionComparison` фиксирует pair-level результат:

| Поле | Назначение |
|---|---|
| `document` | Документ, которому принадлежат обе версии. |
| `from_version` | Исходная версия. |
| `to_version` | Целевая версия. |
| `status` | `draft`, `completed`, `failed`; workflow устанавливает `completed` после materialization. |
| `comparison_unit` | `chunk` или `document_text`. |
| `matching_strategy` | `structural_chunks_v2` или `document_text_fallback_v1`. |
| `identical` | Нет materialized added/removed/modified/moved. |
| `added_count` | Количество added items. |
| `removed_count` | Количество removed items. |
| `modified_count` | Количество modified items. |
| `moved_count` | Количество moved items; сейчас обычно `0`. |
| `unchanged_count` | Количество exact matched unchanged chunks. |
| `created_at`, `updated_at` | Audit timestamps. |

Ограничения модели:

- уникальная пара `from_version + to_version`;
- разные версии;
- один документ;
- `to_version` новее `from_version`.

### 13.2 `VersionChangeItem`

Модель `VersionChangeItem` фиксирует item-level изменение:

| Поле | Назначение |
|---|---|
| `comparison` | Родительский `VersionComparison`. |
| `change_type` | `added`, `removed`, `modified`, `moved`. |
| `old_chunk` | Source chunk для removed/modified/moved; nullable. |
| `new_chunk` | Target chunk для added/modified/moved; nullable. |
| `old_text` | Snapshot old text; заполняется из chunk или fallback synthetic payload. |
| `new_text` | Snapshot new text. |
| `similarity` | Lexical similarity для modified/moved, если есть. |
| `match_reason` | Причина matching для modified/moved. |
| `semantic_type` | Downstream semantic type после enrichment. |
| `extracted_entities` | Downstream rule-based entities. |
| `significance_label` | Downstream significance label. |
| `significance_score` | Downstream significance score. |
| `significance_reason` | Explainable reason. |
| `significance_rules` | Triggered rules. |
| `requires_manual_review` | Flag для неоднозначных/важных случаев. |
| `sort_order` | Стабильный порядок отображения и связи с highlights. |
| `created_at` | Timestamp. |

`materialize_comparison` использует `update_or_create` для `VersionComparison`, удаляет старые `change_items` этой пары и создаёт актуальные items заново. Это предотвращает накопление дублей при повторной materialization той же пары.

## 14. Использование comparison в downstream pipeline

| Downstream слой | Как использует comparison | Почему это важно |
|---|---|---|
| Significance / prioritization | `enrich_compare_payload` и `enrich_change` классифицируют `added`, `removed`, `modified`, `moved` по semantic/significance rules | Отделяет потенциально важные изменения от редакционных и технических. |
| Summary | `build_brief_summary` выбирает приоритетные изменения и формирует `Summary.text` / `Summary.highlights` | Делает diff понятным человеку и сохраняет source references. |
| Quiz generation | `build_quiz_from_diff` → `build_brief_summary`; `build_quiz_from_summary` строит вопросы по highlights | Превращает изменения в контрольно-обучающие материалы. |
| Quiz materialization | `create_quiz_from_versions` создаёт `GeneratedQuiz`, `Question`, `Choice`; `Question.source_change_item` может ссылаться на `VersionChangeItem` | Позволяет объяснить, какое изменение породило вопрос. |
| Demo UI | `demo/views.py` строит compare context: diff, brief, quiz preview | Делает pipeline демонстрируемым в локальном UI. |
| API | `/api/compare/`, `/api/compare/brief/`, `/api/compare/quiz/`, `/api/compare/quiz/save/` | Даёт runtime comparison, summary, quiz preview и materialized quiz. |
| Reporting | Через quiz/attempt цепочку сохраняется результат прохождения по вопросам, связанным с comparison | Закрывает MVP цикл `версия → результат`. |

## 15. Псевдокод алгоритма

Псевдокод отражает фактическую реализацию `build_version_diff`.

```text
Input:
    from_version: DocumentVersion
    to_version: DocumentVersion

Output:
    diff_payload

Algorithm build_version_diff(from_version, to_version):
    validate_version_pair(from_version, to_version)

    old_chunks = chunks(from_version).order_by(chunk_index)
    new_chunks = chunks(to_version).order_by(chunk_index)

    if old_chunks is empty OR new_chunks is empty:
        return build_document_text_fallback_diff(from_version, to_version)

    matched_old = set()
    matched_new = set()
    moved = []
    unchanged_count = 0

    # 1. Exact hash pairing for unchanged chunks
    old_by_hash = group old_chunks by text_hash
    new_by_hash = group new_chunks by text_hash

    for each text_hash in intersection(old_by_hash, new_by_hash):
        old_group = sort(old_by_hash[text_hash], by chunk_index)
        new_group = sort(new_by_hash[text_hash], by chunk_index)

        for reason in [path_key, canonical_label, section_path]:
            pairs = pair_chunks_by_anchor(old_group, new_group, reason)
            mark pairs as matched
            unchanged_count += count(pairs)

        pairs = pair_chunks_by_anchor(old_group, new_group, same_index)
        mark pairs as matched
        unchanged_count += count(pairs)

        remaining_old = old_group not in matched_old
        remaining_new = new_group not in matched_new

        if remaining_old and remaining_new:
            if no primary anchors in remaining_old + remaining_new:
                for each pair in zip(remaining_old, remaining_new):
                    mark pair as matched
                    unchanged_count += 1
            else if count(remaining_old) == 1 and count(remaining_new) == 1:
                # MVP rule: exact-text renumbering/reordering is not reported as moved
                mark the only pair as matched
                unchanged_count += 1

    # 2. Modified by primary anchors
    unmatched_old = old_chunks not in matched_old
    unmatched_new = new_chunks not in matched_new

    modified = []
    for reason in [path_key, canonical_label, section_path]:
        pairs = pair_chunks_by_anchor(unmatched_old, unmatched_new, reason)
        for each (old_chunk, new_chunk) in pairs:
            modified.append({
                from_chunk: serialize(old_chunk),
                to_chunk: serialize(new_chunk),
                similarity: SequenceMatcher(old_chunk.text, new_chunk.text),
                match_reason: reason,
                change_classification: classify_modified_chunk_pair(...)
            })
            mark old_chunk and new_chunk as matched

    # 3. Fallback modified matching
    remaining_old = unmatched_old not matched above
    remaining_new = unmatched_new not matched above

    candidates = []
    for old_chunk in remaining_old:
        for new_chunk in remaining_new:
            score, reason = score_chunk_match(old_chunk, new_chunk)
            if score > 0 and reason is not None:
                candidates.append(score, old_chunk, new_chunk, similarity, reason)

    sort candidates by score desc, similarity desc, index_distance asc

    for candidate in candidates:
        if old_chunk and new_chunk are both unused:
            modified.append(make_modified_item(old_chunk, new_chunk, similarity, reason))
            mark both chunks as used

    # 4. Residual changes
    removed = []
    for old_chunk in remaining_old not used:
        removed.append(serialize(old_chunk) + classify_added_or_removed(operation=removed))

    added = []
    for new_chunk in remaining_new not used:
        added.append(serialize(new_chunk) + classify_added_or_removed(operation=added))

    text_diff = unified_diff(from_version.normalized_text, to_version.normalized_text)
    identical = added, removed, modified and moved are all empty

    return {
        from_version,
        to_version,
        comparison_meta: {
            comparison_unit: "chunk",
            matching_strategy: "structural_chunks_v2"
        },
        identical,
        summary: {
            added: count(added),
            removed: count(removed),
            modified: count(modified),
            moved: count(moved),
            unchanged: unchanged_count,
            by_type: summarize_change_types(...)
        },
        added,
        removed,
        modified,
        moved,
        text_diff
    }
```

Fallback pseudocode:

```text
Algorithm build_document_text_fallback_diff(from_version, to_version):
    from_text = from_version.normalized_text or from_version.extracted_text or ""
    to_text = to_version.normalized_text or to_version.extracted_text or ""

    if from_text == to_text:
        unchanged_count = 1 if from_text else 0
    else if from_text and to_text:
        create one synthetic modified item for whole document
        match_reason = "document_text_fallback"
        similarity = SequenceMatcher(from_text, to_text).ratio()
    else if to_text:
        create one synthetic added item
    else if from_text:
        create one synthetic removed item

    comparison_unit = "document_text"
    matching_strategy = "document_text_fallback_v1"
```

## 16. Примеры изменений

### Example 1 — Modified

Old:

```text
Пункт 1. Срок предоставления услуги составляет 10 рабочих дней.
```

New:

```text
Пункт 1. Срок предоставления услуги составляет 7 рабочих дней.
```

Result:

```text
status = modified
reason = matched structural anchor, text_hash differs
possible match_reason = path_key
similarity = lexical SequenceMatcher ratio
```

### Example 2 — Added

Old:

```text
Статья 2. Требования к заявителю.
```

New:

```text
Статья 2. Требования к заявителю.
Пункт 3. Заявитель вправе подать документы в электронной форме.
```

Result:

```text
status = added
reason = new chunk remains unmatched after all matching stages
```

### Example 3 — Removed

Old:

```text
Пункт 4. Требуется нотариально заверенная копия документа.
```

New:

```text
[пункт отсутствует]
```

Result:

```text
status = removed
reason = old chunk remains unmatched after all matching stages
```

### Example 4 — Unchanged / not materialized

Old:

```text
Заявитель предоставляет документ.
```

New:

```text
Заявитель предоставляет документ.
```

Result:

```text
status = unchanged_count increment
reason = text_hash is identical
materialization = no VersionChangeItem is created
```

### Example 5 — Document-text fallback

Old:

```text
Старая редакция документа целиком.
```

New:

```text
Новая редакция документа целиком.
```

If chunks are missing:

```text
comparison_unit = document_text
matching_strategy = document_text_fallback_v1
status = modified
match_reason = document_text_fallback
old_chunk.id = null
new_chunk.id = null
```

Moved example intentionally omitted: current `build_version_diff` does not actively materialize moved changes.

## 17. Baseline и улучшение относительно plain text diff

### Baseline 1 — plain text diff

Plain text diff сравнивает строки полного документа. Он полезен как диагностический fallback и поэтому сохраняется в `text_diff`, но не является core method comparison layer.

Недостатки:

- чувствительность к строкам и форматированию;
- отсутствие `path_key`;
- отсутствие связи с `Chunk`;
- слабая пригодность для significance и quiz.

### Baseline 2 — paragraph diff

Paragraph diff уменьшает строковой шум, но не знает нормативной структуры. Абзацы не гарантируют устойчивого соответствия статьям, пунктам и подпунктам.

### Current method — structural chunk diff

Фактическое improvement проекта:

| Улучшение | За счёт чего достигается |
|---|---|
| Снижение форматного шума | Safe normalization + structural chunking. |
| Устойчивое сопоставление нормативных единиц | `path_key`, `canonical_label`, `section_path`, `heading`. |
| Быстрое exact detection | `text_hash`. |
| Снижение шума при вставках/renumbering | Exact-text shifted chunks считаются unchanged. |
| Downstream traceability | `VersionChangeItem.old_chunk/new_chunk`, `old_text/new_text`, `sort_order`. |
| Explainability | `match_reason`, `similarity`, `change_classification`, significance fields. |

Экспериментальное доказательство improvement не выполняется в Фазе 9. Оно относится к Фазе 15.

## 18. Связь с архитектурой системы

Comparison пересекает три слоя архитектуры:

| Архитектурный слой | Файлы / модели | Роль |
|---|---|---|
| Domain layer | `backend/documents/domain/diff.py` | Реализация deterministic chunk-based comparison и document fallback. |
| Application layer | `backend/documents/services/workflows.py` | Валидация workflow, enrichment, materialization comparison/summary/quiz. |
| Persistence layer | `VersionComparison`, `VersionChangeItem`, `Summary` | Сохранение проверяемых артефактов comparison и downstream outputs. |
| Presentation/API layer | `backend/documents/api/endpoints.py`, `backend/documents/demo/views.py` | Выбор версий, отображение diff/brief/quiz preview, сохранение quiz. |

Согласование с Фазами 6–8:

- `C` соответствует `Comparison` в `docs/research/hybrid-method.md`.
- Comparison реально опирается на `S`, потому что использует материализованные `Chunk` rows.
- LLM не участвует в core comparison.
- Semantic embeddings не являются частью core comparison.
- `moved` не описывается как реализованный active detector.
- MVP scope не расширяется: документ описывает уже существующий algorithm и materialization.

## 19. Связь с будущей экспериментальной оценкой

Фаза 9 формализует метод. Фаза 15 должна оценить качество diff/comparison.

Будущие метрики:

| Метрика | Смысл |
|---|---|
| True positive changes | Реальные изменения, найденные алгоритмом. |
| False positive changes | Шумовые изменения, которых эксперт не считает изменениями. |
| False negative changes | Пропущенные изменения. |
| Precision | Доля найденных изменений, которые являются корректными. |
| Recall | Доля реальных изменений, найденных алгоритмом. |
| F1 | Баланс precision и recall. |
| Noise count | Количество технических/редакционно-шумовых элементов. |
| Expert clarity score | Насколько понятен diff человеку-эксперту. |
| Downstream usefulness | Насколько изменения пригодны для significance, summary и quiz. |

Сравниваемые подходы для Фазы 15:

```text
plain text diff
vs paragraph diff
vs structural chunk diff
```

Ожидаемая проверяемая гипотеза: structural chunk diff должен давать меньше шумовых изменений и более полезные change items для downstream pipeline, особенно при вставках, удалениях и локальных модификациях пунктов.

## 20. Ограничения метода

Ограничения фиксируются явно:

1. **Зависимость от normalization.** Ошибки extraction/normalization могут ухудшить chunking и comparison.
2. **Зависимость от chunking.** Если structural chunking нестабилен между версиями, modified может распасться на added + removed.
3. **PDF-ограничения.** Плохой текстовый слой PDF, колонтитулы, переносы и таблицы могут ухудшить распознавание структуры.
4. **Fallback chunks менее устойчивы.** `fallback_block` не имеет такой же смысловой стабильности, как `article`, `point`, `subpoint`.
5. **Rule-based matching.** Алгоритм может ошибаться при глубоких переформулировках или при изменении структуры без сохранения anchors.
6. **Moved detection ограничен.** Хотя schema содержит `moved`, текущий core algorithm не материализует moved items; exact-text reorder считается unchanged.
7. **Similarity lexical-only.** `SequenceMatcher` не является semantic similarity и не понимает юридическую эквивалентность формулировок.
8. **Нет matching confidence.** Отдельной модели confidence для сопоставления chunks нет.
9. **Не юридическая экспертиза.** Система помогает анализировать изменения, но не заменяет правовую оценку эксперта.
10. **Local-first MVP.** OCR, RAG, external legal integrations, embeddings и LLM-based comparison не входят в core MVP.

## 21. Формулировка для диссертации

В рамках разработанного гибридного метода предложен структурно-ориентированный алгоритм сопоставления редакций нормативного документа. Алгоритм использует материализованные структурные фрагменты документа, их иерархические ключи, нормализованные структурные метки, порядок следования и текстовые хэши для выявления добавленных, удалённых и изменённых фрагментов. В отличие от простого построчного сравнения, такой подход позволяет учитывать логическую структуру документа и формировать более пригодный для дальнейшей обработки набор изменений.

Фактическая реализация метода является deterministic/rule-based: сопоставление выполняется по `text_hash`, `path_key`, `canonical_label`, `section_path`, `heading`, `fragment_type`, `chunk_index` и lexical similarity на основе `SequenceMatcher`. Результат comparison материализуется в моделях `VersionComparison` и `VersionChangeItem`, после чего используется для rule-based оценки значимости, построения выжимки и генерации контрольно-обучающих материалов. В текущем MVP алгоритм не использует LLM, embeddings или семантическое сопоставление как обязательную часть core comparison.

С научной точки зрения этап `C` выступает центральным мостом между структурным анализом документа (`S`) и прикладной интеллектуальной обработкой изменений (`P`, `G`, `R`). Он переводит две редакции документа в воспроизводимый набор explainable change items, пригодных для дальнейшей классификации, интерпретации и проверки усвоения изменений сотрудниками.

## 22. Вывод

Фаза 9 формализует comparison/diff как отдельный методический слой проекта. Реализация не является простым plain text diff: full-text unified diff сохраняется только как дополнительный диагностический артефакт, а core comparison выполняется на уровне structural chunks.

Ключевой результат:

```text
old_version_chunks + new_version_chunks
→ deterministic structural matching
→ added / removed / modified / unchanged_count
→ materialized VersionComparison / VersionChangeItem
→ significance / summary / quiz / result pipeline
```

Метод остаётся честно ограниченным MVP baseline: он rule-based, lexical-only для similarity, без LLM и embeddings в core comparison, без активной materialization `moved`. Эти ограничения не снижают ценность Фазы 9: они задают воспроизводимую и проверяемую основу для будущей Фазы 15, где качество structural chunk diff будет оцениваться экспериментально относительно plain text diff и paragraph diff.
