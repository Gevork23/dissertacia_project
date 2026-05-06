# Structural Chunking Evaluation

## 1. Цель эксперимента

Цель Фазы 14 — провести воспроизводимую экспериментальную оценку этапа `S` — Structural Segmentation / Structural Chunking — на размеченном evaluation corpus после Фазы 13. Эксперимент проверяет, насколько текущий hybrid structural chunking корректно выделяет смысловые структурные фрагменты документа по сравнению с двумя baseline-подходами.

Оценка не затрагивает diff/comparison, significance classification, summary и quiz generation. Эти компоненты остаются вне scope Фазы 14.

## 2. Связь с гибридным методом

В гибридном методе проекта

`M = <E, N, S, C, P, G, R>`

оценивается только компонент `S`:

- `E` — extraction текста из документа;
- `N` — нормализация текста;
- `S` — структурное разбиение на ordered chunks;
- `C`, `P`, `G`, `R` — последующие этапы pipeline, не оцениваемые в этой фазе.

Практическая роль `S` состоит в том, чтобы перед сравнением редакций перейти от линейного текста к объяснимым structural chunks с `fragment_type`, `heading`, `section_path`, `canonical_label` и `path_key`. Для proposed method использована текущая production-функция `chunk_by_structure_ru`, а не переписанная экспериментальная версия алгоритма.

## 3. Evaluation corpus

Использован каталог `data/evaluation_corpus/`. Валидатор `scripts/validate_evaluation_corpus.py` проходит успешно: найдено 10 пар, 13 expected changes и 23 expected chunks.

Разметка `expected_chunks` содержит версию chunk: чаще `new`, но для `pair_05_editorial_change`, `pair_06_procedure_change` и `pair_08_reordered_structure` также есть `old`. Поэтому оценивались все версии документов, для которых в annotation реально присутствуют expected chunks. Всего оценено 13 документов: 10 `new` и 3 `old`.

Важно: `expected_chunks` в текущем corpus являются разметкой ключевых / целевых фрагментов, а не полной эталонной сегментацией всего документа. Поэтому precision в этом эксперименте является консервативной proxy-метрикой: все найденные методом blocks входят в `found_blocks`, включая валидные, но не размеченные chunks.

| Pair | Expected changes | Expected chunks | Chunk versions | Usable | Known difficulties |
| --- | --- | --- | --- | --- | --- |
| pair_01_deadline_change | 1 | 2 | new: 2 | yes |  |
| pair_02_added_obligation | 1 | 2 | new: 2 | yes |  |
| pair_03_document_list_change | 1 | 3 | new: 3 | yes | Добавление подпункта может быть обнаружено как изменение родительского пункта, если comparison работает на уровне более крупного chunk. |
| pair_04_refusal_ground_change | 1 | 2 | new: 2 | yes |  |
| pair_05_editorial_change | 1 | 2 | old: 1, new: 1 | yes | Pipeline может найти modified chunk, но significance и quiz должны трактовать изменение как editorial-only. |
| pair_06_procedure_change | 1 | 2 | old: 1, new: 1 | yes |  |
| pair_07_responsibility_change | 1 | 2 | new: 2 | yes |  |
| pair_08_reordered_structure | 1 | 2 | old: 1, new: 1 | yes | Moved detection отсутствует или ограничена в текущем MVP; annotation фиксирует conceptual gold standard и baseline limitation. |
| pair_09_mixed_significant_and_editorial | 4 | 3 | new: 3 | yes | Summary должен фокусироваться на critical changes, а quiz не должен строиться по редакционной замене. |
| pair_10_weakly_structured_document | 1 | 3 | new: 3 | yes | Документ специально не содержит явных markers Раздел/Статья/Пункт; expected_chunks должны оцениваться как fallback blocks.; Comparison может быть менее точным, потому что changed deadline находится внутри более крупного fallback-блока. |

## 4. Сравниваемые методы

| Method | Description | Role |
| --- | --- | --- |
| paragraph_baseline | Разделение нормализованного текста по пустым строкам / paragraph boundaries. | naive baseline |
| heading_article_baseline | Rule split по строкам «Раздел/Глава/Статья» и числовым пунктам; без lettered subpoints и без production fallback. | stronger structural baseline |
| hybrid_structural | Текущая реализация проекта: materialize_document_text + chunk_by_structure_ru; structural markers, path/path_key, fallback blocks. | proposed method |

### 4.1 Paragraph-based baseline

Наивный baseline делит нормализованный текст по пустым строкам. Он не распознаёт юридические маркеры, не строит `path_key` и не различает пункт, подпункт, статью или fallback-блок. На структурированных документах такой подход часто объединяет несколько пунктов одной статьи в один paragraph block.

### 4.2 Heading/article-based baseline

Более сильный baseline использует простые регулярные правила для строк `Раздел`, `Глава`, `Статья` и числовых пунктов вида `1.` / `1.1.`. Он намеренно не реализует весь production chunking: не распознаёт lettered subpoints вида `а)`, не строит иерархический `path_key` и при weak structure использует грубый document-level fallback.

### 4.3 Hybrid structural chunking

Основной метод проекта вызывает `materialize_document_text` и текущую production-функцию `chunk_by_structure_ru`. Метод распознаёт structural markers, сохраняет порядок chunks, формирует structural metadata и использует fallback blocks при отсутствии явной структуры. Production-алгоритм в Фазе 14 не изменялся.

## 5. Метрики

Для каждой пары, версии документа и метода считались:

- `expected_blocks` — число expected chunks в annotation для данной версии;
- `found_blocks` — число chunks/blocks, найденных методом во всём документе;
- `correct_boundaries` — число expected chunks, сопоставленных с найденными chunks по правилу matching;
- `precision = correct_boundaries / found_blocks`;
- `recall = correct_boundaries / expected_blocks`;
- `F1 = 2 * precision * recall / (precision + recall)`;
- `oversegmentation_ratio = found_blocks / expected_blocks`;
- `boundary_delta = found_blocks - expected_blocks`.

При нулевом знаменателе метрика безопасно принимает значение `0.0`.

## 6. Boundary matching rule

Expected chunk считается найденным корректно, если его `expected_boundary_text` после нормализации whitespace и регистра содержится в одном найденном chunk.

Дополнительное one-to-one ограничение: один found chunk может засчитать не более одного expected chunk. Если два expected chunks попали в один и тот же found chunk, первый засчитывается, а последующие маркируются как `merged`. Это важно для оценки boundary quality: крупный chunk, содержащий несколько ожидаемых смысловых фрагментов, не должен искусственно повышать recall без штрафа за undersegmentation.

Matching не требует совпадения `fragment_type`, потому что baseline methods не обязаны возвращать ту же типологию chunks, что и hybrid method. Основной критерий Фазы 14 — граница смыслового фрагмента через containment expected boundary text.

## 7. Результаты

| Pair | Version | Method | Expected blocks | Found blocks | Correct boundaries | Precision | Recall | F1 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pair_01_deadline_change | new | paragraph_baseline | 2 | 8 | 1 | 0.1250 | 0.5000 | 0.2000 | merged=chunk_002 |
| pair_01_deadline_change | new | heading_article_baseline | 2 | 17 | 2 | 0.1176 | 1.0000 | 0.2105 | ok |
| pair_01_deadline_change | new | hybrid_structural | 2 | 10 | 2 | 0.2000 | 1.0000 | 0.3333 | ok |
| pair_02_added_obligation | new | paragraph_baseline | 2 | 8 | 1 | 0.1250 | 0.5000 | 0.2000 | merged=chunk_002 |
| pair_02_added_obligation | new | heading_article_baseline | 2 | 18 | 2 | 0.1111 | 1.0000 | 0.2000 | ok |
| pair_02_added_obligation | new | hybrid_structural | 2 | 11 | 2 | 0.1818 | 1.0000 | 0.3077 | ok |
| pair_03_document_list_change | new | paragraph_baseline | 3 | 8 | 2 | 0.2500 | 0.6667 | 0.3636 | merged=chunk_002 |
| pair_03_document_list_change | new | heading_article_baseline | 3 | 16 | 2 | 0.1250 | 0.6667 | 0.2105 | merged=chunk_002 |
| pair_03_document_list_change | new | hybrid_structural | 3 | 13 | 3 | 0.2308 | 1.0000 | 0.3750 | ok |
| pair_04_refusal_ground_change | new | paragraph_baseline | 2 | 8 | 2 | 0.2500 | 1.0000 | 0.4000 | ok |
| pair_04_refusal_ground_change | new | heading_article_baseline | 2 | 17 | 2 | 0.1176 | 1.0000 | 0.2105 | ok |
| pair_04_refusal_ground_change | new | hybrid_structural | 2 | 10 | 2 | 0.2000 | 1.0000 | 0.3333 | ok |
| pair_05_editorial_change | old | paragraph_baseline | 1 | 8 | 1 | 0.1250 | 1.0000 | 0.2222 | ok |
| pair_05_editorial_change | old | heading_article_baseline | 1 | 17 | 1 | 0.0588 | 1.0000 | 0.1111 | ok |
| pair_05_editorial_change | old | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_05_editorial_change | new | paragraph_baseline | 1 | 8 | 1 | 0.1250 | 1.0000 | 0.2222 | ok |
| pair_05_editorial_change | new | heading_article_baseline | 1 | 17 | 1 | 0.0588 | 1.0000 | 0.1111 | ok |
| pair_05_editorial_change | new | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_06_procedure_change | old | paragraph_baseline | 1 | 8 | 1 | 0.1250 | 1.0000 | 0.2222 | ok |
| pair_06_procedure_change | old | heading_article_baseline | 1 | 17 | 1 | 0.0588 | 1.0000 | 0.1111 | ok |
| pair_06_procedure_change | old | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_06_procedure_change | new | paragraph_baseline | 1 | 8 | 1 | 0.1250 | 1.0000 | 0.2222 | ok |
| pair_06_procedure_change | new | heading_article_baseline | 1 | 17 | 1 | 0.0588 | 1.0000 | 0.1111 | ok |
| pair_06_procedure_change | new | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_07_responsibility_change | new | paragraph_baseline | 2 | 8 | 1 | 0.1250 | 0.5000 | 0.2000 | merged=chunk_002 |
| pair_07_responsibility_change | new | heading_article_baseline | 2 | 17 | 2 | 0.1176 | 1.0000 | 0.2105 | ok |
| pair_07_responsibility_change | new | hybrid_structural | 2 | 10 | 2 | 0.2000 | 1.0000 | 0.3333 | ok |
| pair_08_reordered_structure | old | paragraph_baseline | 1 | 9 | 1 | 0.1111 | 1.0000 | 0.2000 | ok |
| pair_08_reordered_structure | old | heading_article_baseline | 1 | 18 | 1 | 0.0556 | 1.0000 | 0.1053 | ok |
| pair_08_reordered_structure | old | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_08_reordered_structure | new | paragraph_baseline | 1 | 9 | 1 | 0.1111 | 1.0000 | 0.2000 | ok |
| pair_08_reordered_structure | new | heading_article_baseline | 1 | 18 | 1 | 0.0556 | 1.0000 | 0.1053 | ok |
| pair_08_reordered_structure | new | hybrid_structural | 1 | 10 | 1 | 0.1000 | 1.0000 | 0.1818 | ok |
| pair_09_mixed_significant_and_editorial | new | paragraph_baseline | 3 | 8 | 2 | 0.2500 | 0.6667 | 0.3636 | merged=chunk_002 |
| pair_09_mixed_significant_and_editorial | new | heading_article_baseline | 3 | 19 | 3 | 0.1579 | 1.0000 | 0.2727 | ok |
| pair_09_mixed_significant_and_editorial | new | hybrid_structural | 3 | 12 | 3 | 0.2500 | 1.0000 | 0.4000 | ok |
| pair_10_weakly_structured_document | new | paragraph_baseline | 3 | 8 | 3 | 0.3750 | 1.0000 | 0.5455 | ok |
| pair_10_weakly_structured_document | new | heading_article_baseline | 3 | 1 | 1 | 1.0000 | 0.3333 | 0.5000 | merged=chunk_002,chunk_003 |
| pair_10_weakly_structured_document | new | hybrid_structural | 3 | 8 | 3 | 0.3750 | 1.0000 | 0.5455 | ok |

## 8. Aggregate results

Ниже приведены macro- и micro-агрегаты. Для вывода по Фазе 14 основным ориентиром является macro F1 по оценённым документам, а micro-метрики показывают суммарную картину по всем expected chunks.

| Method | Macro precision | Macro recall | Macro F1 | Micro precision | Micro recall | Micro F1 | Expected total | Found total | Correct total | Mean oversegmentation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| paragraph_baseline | 0.1709 | 0.8333 | 0.2740 | 0.1698 | 0.7826 | 0.2791 | 23 | 106 | 18 | 5.6923 |
| heading_article_baseline | 0.1610 | 0.9231 | 0.1900 | 0.0957 | 0.8696 | 0.1724 | 23 | 209 | 20 | 11.5769 |
| hybrid_structural | 0.1721 | 1.0000 | 0.2861 | 0.1716 | 1.0000 | 0.2930 | 23 | 134 | 23 | 7.0385 |

Ключевой результат: `hybrid_structural` получил максимальные recall и F1 среди трёх методов. Он нашёл все 23 expected boundaries, тогда как paragraph baseline нашёл 18 из 23, а heading/article baseline — 20 из 23. При этом абсолютные значения precision/F1 остаются невысокими, потому что annotation покрывает только целевые chunks, а `found_blocks` считает все blocks документа.

## 9. Анализ ошибок

### Paragraph-based baseline

Paragraph baseline хорошо работает только там, где пустые строки случайно совпадают с целевыми смысловыми блоками. На weakly structured документе `pair_10_weakly_structured_document` он получил F1 = 0.5455, потому что структура памятки естественно оформлена как отдельные абзацные блоки.

На структурированных регламентах baseline часто объединяет несколько пунктов внутри одной статьи. Это видно в `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_07_responsibility_change`, где второй expected chunk попадает в уже использованный paragraph block и отмечается как `merged`. В `pair_03_document_list_change` подпункт `г)` также оказывается внутри общего article/paragraph block, из-за чего отдельная boundary для подпункта не засчитывается.

### Heading/article-based baseline

Heading/article baseline чаще находит point-level boundaries, чем paragraph baseline, и поэтому имеет более высокий recall на structured documents. Однако он сильно oversegment-ит документ: отдельно выделяет title/section/article heading chunks и числовые пункты. Суммарно он нашёл 209 blocks против 134 у hybrid method и 106 у paragraph baseline, что снижает precision.

Основная содержательная ошибка baseline — отсутствие обработки lettered subpoints. В `pair_03_document_list_change` подпункт `г)` остаётся внутри chunk родительского пункта и маркируется как `merged`. На weakly structured документе baseline не применяет production fallback, поэтому весь документ становится одним document-level block; один expected chunk засчитывается, а два других маркируются как merged.

### Hybrid structural chunking

Hybrid method корректно нашёл все expected boundaries на оценённом corpus. Он выделил point-level chunks в structured documents, subpoint-level chunk для `pair_03_document_list_change` и fallback blocks для `pair_10_weakly_structured_document`.

При этом precision остаётся ограниченным, потому что метод честно материализует полный набор chunks документа, включая title и неразмеченные пункты. Это не ошибка production chunking, а следствие того, что corpus содержит key-boundary annotation, а не полную разметку всех правильных chunks.

### Weakly structured case

В `pair_10_weakly_structured_document` hybrid method перешёл к fallback-block segmentation и нашёл все три expected fallback boundaries. Paragraph baseline получил такой же F1, потому что в данном синтетическом документе fallback-блоки совпадают с абзацными разделителями. Heading/article baseline оказался менее устойчивым: без явных markers он сформировал один общий block и потерял две границы.

## 10. Ограничения эксперимента

1. Corpus небольшой: 10 synthetic document pairs и 23 expected chunks. Этого достаточно для первой воспроизводимой оценки в главе 3, но не для статистически сильных выводов.
2. `expected_chunks` не являются полной full-document gold segmentation. Метрики отражают key-boundary detection, а precision консервативно штрафует methods за все найденные, но не размеченные chunks.
3. Matching основан на normalized text containment. Он не оценивает семантическую эквивалентность и не измеряет качество `path_key` напрямую.
4. Baseline methods реализованы как экспериментальные reference methods внутри `experiments/chunking/evaluate_chunking.py`; production method вызван напрямую через текущий `chunk_by_structure_ru`.
5. Фаза 14 не оценивает diff/comparison, moved detection, significance, summary или quiz generation.
6. На weakly structured document paragraph baseline показывает сильный результат из-за совпадения абзацной структуры corpus с fallback-блоками; это нужно учитывать при интерпретации.

## 11. Вывод для диссертации

Результаты эксперимента показывают, что структурно-ориентированное разбиение обеспечивает более полное и устойчивое выделение целевых смысловых фрагментов нормативного документа по сравнению с baseline-подходами. В evaluation corpus hybrid structural chunking достиг recall = 1.0000 и максимального macro F1 = 0.2861, найдя все 23 expected boundaries.

Абзацный baseline оказался конкурентоспособным на weakly structured памятке, но на структурированных регламентах объединял несколько пунктов внутри одного block. Heading/article baseline лучше учитывал явные markers, но oversegment-ил заголовки и не выделил lettered subpoint. Это подтверждает целесообразность использования этапа `S` в составе гибридного метода `M = <E, N, S, C, P, G, R>` перед выполнением сравнения редакций.

Для главы 3 результат следует формулировать аккуратно: hybrid method показывает преимущество по полноте и F1 на размеченных key boundaries, но точность эксперимента ограничена неполной chunk-разметкой corpus. Следующий экспериментальный шаг — Фаза 15, где эти chunks будут использованы для оценки качества diff/comparison.
