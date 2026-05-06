# Evaluation Corpus Annotation Guidelines

## 1. Назначение разметки

Evaluation corpus предназначен для будущего измерения качества компонентов гибридного метода `M = <E, N, S, C, P, G, R>`, а не для демонстрации интерфейса. Разметка задаёт ручной эталон для следующих задач:

- `S` — structural chunking;
- `C` — diff/comparison;
- `P` — significance classification;
- `G` — summary generation и quiz generation.

Каждая пара документов содержит две версии синтетического регламентного текста и файл `annotation.json`, в котором вручную указано, какие изменения нужно считать целевыми, какие фрагменты должны быть выделены как chunks, какие изменения должны попадать в summary и какие темы допустимы для quiz.

## 2. Отличие evaluation corpus от demo corpus

`data/demo_corpus/` создан для устойчивого показа MVP pipeline комиссии. Он короткий, понятный и ориентирован на демонстрационный сценарий.

`data/evaluation_corpus/` создан для измерений. Он включает больше пар, более разнообразные случаи, смешанные изменения, отрицательные примеры, структурный перенос и weakly structured fallback case. Evaluation corpus может быть менее “красивым”, потому что его задача — не скрывать пограничные ситуации, а сделать их измеримыми.

Demo metadata не считается экспертной разметкой. Evaluation annotation является ручным эталоном для будущих Фаз 14–18.

## 3. Общая структура annotation.json

Минимальная структура, используемая в этом корпусе:

```json
{
  "annotation_version": "1.0",
  "pair_id": "pair_01_deadline_change",
  "title": "Изменение срока рассмотрения заявления",
  "document_type": "synthetic_internal_regulation",
  "purpose": "Evaluation case ...",
  "old_file": "old.txt",
  "new_file": "new.txt",
  "format": "txt",
  "language": "ru",
  "synthetic": true,
  "contains_personal_data": false,
  "expected_changes": [],
  "expected_significance": [],
  "editorial_changes": [],
  "expected_chunks": [],
  "expected_summary_topics": [],
  "expected_summary": {
    "must_mention": [],
    "must_not_mention": []
  },
  "expected_quiz_topics": [],
  "expected_quiz": {
    "must_cover_topics": [],
    "must_not_cover_topics": [],
    "expected_question_count_min": 0,
    "expected_question_count_max": 0
  },
  "evaluation_tags": [],
  "known_difficulties": []
}
```

Поля `expected_changes`, `expected_significance`, `editorial_changes`, `expected_chunks`, `expected_summary` и `expected_quiz` являются основными для будущих метрик. Остальные поля помогают воспроизводимости и интерпретации результатов.

## 4. Разметка expected_changes

`expected_changes` фиксирует ручной эталон изменений между `old.txt` и `new.txt`.

Для каждого изменения указываются:

- `id` — стабильный идентификатор изменения внутри пары;
- `type` — `added`, `removed`, `modified`, `moved`;
- `fragment` — человекочитаемый путь к фрагменту;
- `old_text` и `new_text` — минимальные текстовые фрагменты до и после изменения;
- `importance` — ожидаемая категория значимости;
- `semantic_type` — нормализованный тип для significance-layer;
- `change_type` — доменный тип изменения;
- `description` — краткое объяснение;
- `expected_summary_topic` — тема, которую должен упомянуть summary;
- `expected_quiz_topic` — тема, которую должен покрыть quiz, если вопрос ожидается.

Для `added` допускается пустой `old_text`. Для `removed` допускается пустой `new_text`. Для `moved` текст может совпадать, но должен быть указан перенос структурного пути.

## 5. Разметка editorial_changes

`editorial_changes` выделяет изменения без практического влияния:

- орфография и пунктуация;
- стилистическая замена без изменения обязанности, срока, процедуры или основания отказа;
- структурный перенос без изменения текста, если текущий baseline не должен строить quiz по этому факту.

Редакционные изменения могут одновременно присутствовать в `expected_changes` с `importance = editorial`, чтобы diff evaluation мог учитывать факт их обнаружения, а significance/summary/quiz evaluation — факт их низкого приоритета.

## 6. Разметка expected_chunks

`expected_chunks` задаёт ручные ожидания для structural chunking. В текущем проекте chunks обычно соответствуют пунктам и подпунктам, а разделы/статьи чаще используются как structural context (`section_path`, `heading`), а не как самостоятельные chunks.

Для каждого chunk указываются:

- `id`;
- `version` — `old`, `new` или будущая интерпретация;
- `fragment`;
- `expected_type` — `point`, `subpoint`, `fallback_block` и т.п.;
- `expected_heading`, если он важен;
- `expected_boundary_text` — текст, который должен попадать в границы chunk;
- `is_key_chunk` — влияет ли chunk на основной сценарий пары.

Для weakly structured documents ожидаются `fallback_block`, а не структурные пункты.

## 7. Разметка importance

В корпусе используются категории, реально зафиксированные в проекте после significance-фазы:

- `critical` — сроки, обязательные документы, основания отказа, обязанности, ответственность;
- `important` — существенные процедурные изменения;
- `informational` — справочные дополнения без прямой обязанности или условия;
- `editorial` — редакционные и структурные изменения без практического влияния;
- `not_evaluated` — резервная категория текущего pipeline, в ручной разметке целевых изменений не используется.

Категории `medium` и `minor` в текущем коде не являются штатными labels. Для небольших справочных изменений применяется `informational`, для редакционных — `editorial`.

## 8. Разметка expected_summary_topics

`expected_summary_topics` и `expected_summary.must_mention` задают темы, которые summary должен явно отразить. Формулировки не требуют дословного совпадения, но требуют смыслового покрытия.

`expected_summary.must_not_mention` задаёт темы, которые не должны быть представлены как содержательные изменения. Это важно для отрицательных и смешанных кейсов: summary не должен раздувать пунктуацию или синонимическую замену до уровня meaningful change.

## 9. Разметка expected_quiz_topics

`expected_quiz.must_cover_topics` задаёт темы, по которым ожидается хотя бы один корректный вопрос. Например:

- новый срок рассмотрения;
- новая обязанность сотрудника;
- добавленный документ;
- новое основание отказа;
- новый порядок подачи;
- ответственность за нарушение срока.

`expected_quiz.must_not_cover_topics` задаёт темы, по которым вопрос не должен создаваться. Для purely editorial и structural reorder cases `expected_question_count_max = 0`.

## 10. Known difficulties

`known_difficulties` используется для честной фиксации ограничений baseline:

- синонимические редакционные замены могут быть переоценены rule-based significance;
- добавление подпункта может выглядеть как изменение родительского пункта;
- structural reorder в текущем `diff.py` может считаться unchanged, потому что exact-text relocation не материализуется как moved;
- fallback chunks менее точны, чем структурные пункты.

Эти сложности не являются ошибками корпуса. Они нужны, чтобы будущие метрики не интерпретировались без контекста.

## 11. Как annotation будет использоваться в Фазах 14–18

| Фаза | Использование annotation |
|---|---|
| Phase 14 — chunking evaluation | Сравнение фактических chunks с `expected_chunks`, проверка границ key chunks и fallback behavior. |
| Phase 15 — diff/comparison evaluation | Сравнение найденных `added/removed/modified/moved` с `expected_changes`. |
| Phase 16 — significance evaluation | Сравнение `significance_label` и semantic type с `importance` и `semantic_type`. |
| Phase 17 — summary evaluation | Проверка `must_mention` и `must_not_mention` в generated summary. |
| Phase 18 — quiz generation evaluation | Проверка тем вопросов, количества вопросов и отсутствия вопросов по editorial/no-quiz controls. |

## 12. Ограничения ручной разметки

Разметка является экспертной для целей магистерского эксперимента, но не является юридическим заключением. Документы синтетические и не воспроизводят реальные правовые акты. Часть expected behavior описывает conceptual gold standard, а часть — текущие ограничения MVP baseline; это явно фиксируется в `known_difficulties` и специальных полях вроде `current_baseline_expected_behavior`.

Ручная разметка не заменяет автоматическую JSON Schema. Для защиты от грубых ошибок добавлен простой валидатор `scripts/validate_evaluation_corpus.py`.

## 13. Вывод

Annotation schema делает evaluation corpus пригодным для честной оценки structural chunking, comparison, significance, summary и quiz generation. Корпус отделён от demo corpus и содержит как сильные базовые сценарии, так и отрицательные/пограничные случаи, необходимые для главы 3 диссертации.
