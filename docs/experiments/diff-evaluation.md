# Diff / Version Comparison Evaluation

## 1. Цель эксперимента

Эксперимент оценивает качество этапа `C — Comparison / Diff` гибридного метода. Цель — сравнить текущий structural chunk diff с двумя baseline-подходами и проверить, формирует ли он менее шумный и более пригодный для дальнейшей обработки набор изменений.

## 2. Связь с гибридным методом

В методе `M = <E, N, S, C, P, G, R>` данный эксперимент проверяет этап `C`. Его входом является нормализованный текст и, для основного метода, structural chunks этапа `S`; выходом являются изменения `added`, `removed`, `modified`, `moved`, которые далее используются significance-layer, summary и quiz generation.

## 3. Evaluation corpus

Использован `data/evaluation_corpus/`: 10 синтетических пар документов. В annotation найдено 13 raw expected changes, из них 10 meaningful/key changes для strict-метрик и 3 editorial/diagnostic changes. Разметка является key-change gold standard, а не exhaustive full diff всех технических отличий.

## 4. Сравниваемые методы

| Method | Description | Role |
|---|---|---|
| plain_text_diff | Line-level difflib baseline over minimally normalized text. | baseline |
| paragraph_diff | Paragraph/block difflib baseline over blank-line paragraphs. | stronger baseline |
| structural_chunk_diff | Production structural comparison via hybrid chunks and build_version_diff. | proposed method |

### 4.1 Plain text diff

Baseline сравнивает минимально нормализованный текст построчно через `difflib.SequenceMatcher`. Он сохраняет числовые markers строк и поэтому чувствителен к перенумерации пунктов после вставок.

### 4.2 Paragraph diff

Более крупный baseline сравнивает блоки, разделённые пустыми строками. Он снижает часть line-level шума, но часто склеивает несколько смысловых изменений внутри одного article/paragraph block.

### 4.3 Structural chunk diff

Основной метод использует production `chunk_by_structure_ru` и `build_version_diff`: сопоставление по `text_hash`, `path_key`, `canonical_label`, `section_path`, `heading`, lexical similarity и fallback matching. Core algorithm не изменялся ради метрик.

## 5. Метрики

Для каждой пары и метода считаются `TP`, `FP`, `FN`, `precision`, `recall`, `F1`, `noise_count = FP`, `noise_ratio = FP / max(1, predicted_changes)`. В summary дополнительно сохранены micro/macro агрегаты и диагностические raw-метрики по всем expected_changes, включая editorial.

## 6. Matching rule

Predicted change засчитывается как TP, если его статус совместим с expected status и side-specific lexical score не ниже 0.72. Для `modified` проверяются old и new sides; для `added` — new side; для `removed` — old side. Leading markers вида `1.`, `2)`, `г)` нормализуются перед сопоставлением. Один predicted change может закрыть только один expected change, чтобы merged paragraph-block не давал несколько TP. Для `moved` в raw diagnostics допускается частичное совпадение через `moved`, `added`, `removed` или `modified`, поскольку production moved detector в текущем MVP не материализует moved items.

## 7. Учет editorial noise

Primary strict metrics оценивают полезные/key changes и исключают `importance=editorial` из expected set. Predicted changes, совпавшие с `editorial_changes`, учитываются в `editorial_noise_count`; если они не закрывают meaningful expected change, они также входят в FP. Это отделяет качество detection как raw факта от полезности diff для downstream summary/quiz.

## 8. Результаты

| Pair | Method | TP | FP | FN | Precision | Recall | F1 | Noise |
|---|---|---|---|---|---|---|---|---|
| pair_01_deadline_change | plain_text_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_01_deadline_change | paragraph_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_01_deadline_change | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_02_added_obligation | plain_text_diff | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 | 1 |
| pair_02_added_obligation | paragraph_diff | 0 | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_02_added_obligation | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_03_document_list_change | plain_text_diff | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 | 1 |
| pair_03_document_list_change | paragraph_diff | 0 | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_03_document_list_change | structural_chunk_diff | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 | 1 |
| pair_04_refusal_ground_change | plain_text_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_04_refusal_ground_change | paragraph_diff | 0 | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_04_refusal_ground_change | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_05_editorial_change | plain_text_diff | 0 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_05_editorial_change | paragraph_diff | 0 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_05_editorial_change | structural_chunk_diff | 0 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_06_procedure_change | plain_text_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_06_procedure_change | paragraph_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_06_procedure_change | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_07_responsibility_change | plain_text_diff | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 | 1 |
| pair_07_responsibility_change | paragraph_diff | 0 | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| pair_07_responsibility_change | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_08_reordered_structure | plain_text_diff | 0 | 5 | 0 | 0.0000 | 0.0000 | 0.0000 | 5 |
| pair_08_reordered_structure | paragraph_diff | 0 | 2 | 0 | 0.0000 | 0.0000 | 0.0000 | 2 |
| pair_08_reordered_structure | structural_chunk_diff | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | 0 |
| pair_09_mixed_significant_and_editorial | plain_text_diff | 3 | 1 | 0 | 0.7500 | 1.0000 | 0.8571 | 1 |
| pair_09_mixed_significant_and_editorial | paragraph_diff | 1 | 1 | 2 | 0.5000 | 0.3333 | 0.4000 | 1 |
| pair_09_mixed_significant_and_editorial | structural_chunk_diff | 3 | 1 | 0 | 0.7500 | 1.0000 | 0.8571 | 1 |
| pair_10_weakly_structured_document | plain_text_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_10_weakly_structured_document | paragraph_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |
| pair_10_weakly_structured_document | structural_chunk_diff | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0 |

## 9. Aggregate results

| Method | TP | FP | FN | Micro precision | Micro recall | Micro F1 | Noise | Editorial noise |
|---|---|---|---|---|---|---|---|---|
| plain_text_diff | 10 | 10 | 0 | 0.5000 | 1.0000 | 0.6667 | 10 | 4 |
| paragraph_diff | 4 | 8 | 6 | 0.3333 | 0.4000 | 0.3636 | 8 | 4 |
| structural_chunk_diff | 10 | 3 | 0 | 0.7692 | 1.0000 | 0.8695 | 3 | 2 |

## 10. FP/FN analysis

Plain text diff хорошо находит single-line textual edits, но создаёт FP при перенумерации пунктов после вставки. Paragraph diff часто объединяет несколько пунктов внутри одного крупного block, что снижает recall для added subpoints и добавляет FP modified-blocks. Structural chunk diff получил лучший strict micro F1 в этом запуске: `structural_chunk_diff` является лидером по агрегату, а structural method даёт наименьший noise среди методов, сохраняющих высокий recall.

## 11. Error examples

Подробные примеры сохранены в `experiments/diff/diff_error_examples.md`. Они покрывают line-level FP из-за перенумерации, paragraph-level FN/FP из-за склейки блоков, moved-case limitation production structural diff, clean structural TP и editorial noise.

## 12. Влияние chunking quality на comparison

Comparison зависит от качества этапа `S`: если key boundary выделена плохо, structural diff может получить ложный modified/added/removed или пропустить изменение. Результаты Фазы 14 показали, что `hybrid_structural` нашёл все 23 expected boundaries и получил micro recall=1.0 и micro F1=0.293 на key-boundary разметке. Это усиливает интерпретацию Фазы 15: structural comparison работает лучше там, где chunk boundaries устойчивы. При этом вывод остаётся ограниченным, потому что chunking gold standard не является full-document segmentation.

## 13. Ограничения эксперимента

1. Corpus малый: 10 synthetic pairs, strict meaningful expected changes = 10.
2. Annotation задаёт key-change gold standard, а не exhaustive full diff.
3. Matching основан на containment/lexical overlap, а не на экспертной семантической оценке каждого predicted fragment.
4. Strict metrics намеренно считают editorial-only predictions шумом; raw diagnostics сохранены отдельно.
5. Production structural diff не материализует moved items; exact-text relocation считается unchanged.
6. Weakly structured case оценивается через fallback-block chunks, поэтому clarity ниже, чем у point/subpoint-level chunks.

## 14. Вывод для диссертации

Экспериментальная оценка показала, что structural chunk diff формирует более пригодный для дальнейшей обработки набор изменений, чем plain text diff и paragraph diff. Использование structural chunks, `path_key` и `text_hash` снижает количество шумовых изменений и повышает интерпретируемость результата сравнения. Вывод следует формулировать в рамках текущего key-change corpus: преимущество подтверждено для размеченных synthetic pairs, но более строгая оценка потребует расширенной full-document разметки и отдельной Фазы 16 для significance-layer.
