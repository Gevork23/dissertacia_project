# Summary Layer Evaluation

## 1. Цель эксперимента

Эксперимент оценивает качество human-readable summary-layer, который преобразует technical diff/significance results в понятное для сотрудника объяснение изменений. Проверяется не красота текста сама по себе, а полнота, точность, отсутствие неподдержанных утверждений, понятность и пригодность summary как промежуточного артефакта перед quiz generation.

## 2. Связь с гибридным методом

В формуле `M = <E, N, S, C, P, G, R>` summary-layer расположен между `P — Prioritization / Significance classification` и `G — Generation`. Он не является отдельным символом формулы, но связывает машинный список изменений с обучающим контуром: `C` находит change items, `P` назначает semantic/significance labels, summary формирует brief/highlights, а `G` использует highlights для генерации quiz questions.

## 3. Evaluation corpus

Использован `data/evaluation_corpus/`: 10 синтетических пар документов, 13 expected changes и 9 обязательных summary topics. Пары `pair_05_editorial_change` и `pair_08_reordered_structure` являются editorial/structure controls без обязательных смысловых topics.

## 4. Что именно оценивается

Оценивается production summary artifact из `backend/documents/domain/diff_summary.py::build_brief_summary`: `brief_text`, `overview_title` и `highlights` с `concise_explanation`, `semantic_type` и `significance_label`. Raw `old_text/new_text` в highlights рассматривались для source traceability, но не засчитывались как самостоятельное объяснение темы при оценке completeness.

## 5. Evaluation mode

Основной режим — pipeline summary evaluation: `chunk_by_structure_ru` → `build_version_diff` → `build_brief_summary` на in-memory версиях/чанках. Такой adapter использует production diff/summary logic и не изменяет БД. Дополнительно рассчитан oracle-input diagnostic: `build_brief_summary` вызывается на payload из annotation expected changes / expected significance, чтобы отделить собственное качество summary wording от ошибок upstream stages.

## 6. Критерии оценки

| Criterion | Meaning | Scale |
|---|---|---|
| Completeness | Whether expected critical/important topics are covered | 1-5 |
| Accuracy | Whether the summary preserves factual content and old/new values | 1-5 |
| No hallucinations | Whether unsupported claims and invented consequences are avoided | 1-5 |
| Clarity | Whether a non-technical employee can understand the summary quickly | 1-5 |
| Usefulness | Whether the summary helps focus attention and supports downstream quiz generation | 1-5 |
| Source alignment | Whether summary statements trace back to real change items and significance labels | 1-5 |

## 7. Scoring rubric

Каждый критерий оценивался по шкале 1–5. Оценка 5 означает полное соответствие критерию, 4 — minor issues, 3 — частичное соответствие с заметными недостатками, 2 — серьёзные проблемы, 1 — практически непригодный результат по критерию. Topic coverage, forbidden topics и counts рассчитывались автоматически; итоговые scores являются экспертно-эвристической оценкой по зафиксированной rubric, что отражает природу summary evaluation.

## 8. Результаты

| Pair | Completeness | Accuracy | No hallucinations | Clarity | Usefulness | Source alignment | Average |
|---|---:|---:|---:|---:|---:|---:|---:|
| pair_01_deadline_change | 5 | 5 | 5 | 5 | 5 | 5 | 5.00 |
| pair_02_added_obligation | 5 | 5 | 5 | 5 | 5 | 5 | 5.00 |
| pair_03_document_list_change | 5 | 5 | 4 | 5 | 4 | 4 | 4.50 |
| pair_04_refusal_ground_change | 5 | 5 | 5 | 5 | 5 | 5 | 5.00 |
| pair_05_editorial_change | 2 | 2 | 2 | 3 | 1 | 2 | 2.00 |
| pair_06_procedure_change | 1 | 2 | 3 | 3 | 2 | 2 | 2.17 |
| pair_07_responsibility_change | 5 | 4 | 4 | 4 | 4 | 4 | 4.17 |
| pair_08_reordered_structure | 5 | 5 | 5 | 5 | 5 | 5 | 5.00 |
| pair_09_mixed_significant_and_editorial | 5 | 3 | 3 | 4 | 3 | 3 | 3.50 |
| pair_10_weakly_structured_document | 5 | 5 | 5 | 4 | 5 | 5 | 4.83 |

## 9. Aggregate results

| Metric | Value |
|---|---:|
| Average completeness | 4.3000 |
| Average accuracy | 4.1000 |
| Average no hallucinations | 4.1000 |
| Average clarity | 4.3000 |
| Average usefulness | 3.9000 |
| Average source alignment | 4.0000 |
| Overall average | 4.1167 |
| Covered topics | 8 / 9 |
| Missed topics | 1 |
| Unsupported claims | 5 |
| Editorial/noise overemphasis | 4 |

Oracle-input diagnostic overall average: 4.9000. Это показывает, что при корректных upstream change/significance inputs production summary wording работает заметно устойчивее, чем в полном pipeline mode.

## 10. Topic coverage analysis

Автоматическая проверка покрыла 8 из 9 обязательных topics. Единственный missed topic в pipeline mode относится к `pair_06_procedure_change`: summary не упоминает электронную форму во внутреннем портале, потому что upstream enrichment классифицировал изменение как document-list requirement.

- `pair_06_procedure_change` missed: добавлена возможность подачи заявления через электронную форму во внутреннем портале

## 11. Hallucination / unsupported claims analysis

Unsupported claims total: 5. В текущем corpus это не свободные LLM hallucinations, а в основном неверные semantic labels/priority signals, которые summary честно превращает в текст: editorial wording становится document/deadline change, procedure превращается в document-list change, informational notice — в procedural step.

- `pair_05_editorial_change`: Editorial-only wording change is presented as a critical document-list requirement change.
- `pair_05_editorial_change`: Editorial wording change is over-prioritized as critical.
- `pair_06_procedure_change`: Procedure change is summarized as a document-list requirement change.
- `pair_07_responsibility_change`: Responsibility change is framed as a deadline requirement, although the source text still states responsibility.
- `pair_09_mixed_significant_and_editorial`: Editorial wording change is incorrectly summarized as another deadline-related critical change.
- `pair_09_mixed_significant_and_editorial`: Informational status notice is over-framed as an important procedural step.
- `pair_09_mixed_significant_and_editorial`: Editorial wording change receives a critical deadline highlight.
- `pair_09_mixed_significant_and_editorial`: Informational/noise item is counted as important in the brief.

## 12. Editorial overemphasis analysis

Editorial/noise overemphasis total: 4. Наиболее заметные случаи — `pair_05_editorial_change` и `pair_09_mixed_significant_and_editorial`. В `pair_03_document_list_change` key topic корректно покрыт, но brief statistics дополнительно упоминает one editorial/technical change from upstream diff noise.

- `pair_03_document_list_change`: Summary statistics mention one editorial/technical change produced by upstream comparison.
- `pair_05_editorial_change`: Editorial wording change is over-prioritized as critical.
- `pair_09_mixed_significant_and_editorial`: Editorial wording change receives a critical deadline highlight.
- `pair_09_mixed_significant_and_editorial`: Informational/noise item is counted as important in the brief.

## 13. Good examples

- `pair_01_deadline_change` — average 5.00; Covers the deadline reduction and preserves old/new values.
- `pair_02_added_obligation` — average 5.00; Covers the added notification obligation clearly and source-backed.
- `pair_04_refusal_ground_change` — average 5.00; Covers the new refusal ground and keeps the source condition intact.
- `pair_08_reordered_structure` — average 5.00; Correctly avoids inventing a substantive change for pure reordering in the current MVP pipeline.

## 14. Weak examples

- `pair_05_editorial_change` — average 2.00; Weak editorial-control case: upstream semantic/significance classification turns a wording change into a critical highlight.
- `pair_06_procedure_change` — average 2.17; Expected electronic-form submission topic is missed because upstream enrichment misclassifies the changed chunk.
- `pair_09_mixed_significant_and_editorial` — average 3.50; Both expected critical topics are covered, but upstream over-prioritization creates extra misleading highlights.

## 15. Связь с diff/significance evaluation

Summary зависит от comparison и significance. Если comparison пропустил change, summary не сможет его упомянуть; если significance завысил editorial/informational change, summary может превратить это завышение в human-readable but misleading highlight.

Фаза 15 показала для production structural diff: micro precision = 0.7692, micro recall = 1.0, micro F1 = 0.8695, total noise = 3. Это снижает noise относительно baselines, но не устраняет его полностью.

Фаза 16 показала, что significance-layer является recall-oriented deterministic baseline: important/critical recall = 1.0, exact-label accuracy = 0.6923, important/critical F1 = 0.8571, editorial false positive rate = 0.6667. В summary evaluation эти ограничения проявились в editorial controls and mixed cases: summary не исправляет ошибочный label, а делает его понятным пользователю.

## 16. Ограничения эксперимента

- Corpus малый и синтетический: 10 пар документов.
- Annotation содержит key-change topics, а не exhaustive legal summary benchmark.
- Clarity/usefulness/source alignment требуют экспертно-эвристической оценки; полностью автоматические метрики здесь недостаточны.
- Raw snippets в highlights помогают traceability, но не должны искусственно повышать completeness самого explanatory text.
- Production summary algorithm не изменялся; ошибки upstream не исправлялись внутри Фазы 17.
- Oracle-input diagnostic не является реальным pipeline score; он служит только для отделения summary wording от diff/significance errors.

## 17. Вывод для диссертации

Экспериментальная оценка summary-layer показала, что в pipeline mode средняя итоговая оценка составляет 4.1167 из 5. Summary-layer в большинстве случаев превращает технический результат diff/significance в понятную для пользователя выжимку и покрывает 8 из 9 обязательных topics. На сильных случаях summary корректно отражает изменения сроков, обязанностей, перечня документов и оснований отказа. При этом качество summary ограничено upstream stages: завышенная значимость editorial/informational changes или ошибочный semantic_type приводят к unsupported highlights and editorial/noise overemphasis. Oracle-input diagnostic подтверждает, что при корректном входе production summary wording работает устойчиво; следовательно, summary-layer имеет прикладную ценность как промежуточное human-readable представление между анализом изменений и генерацией контрольно-обучающих материалов, но должен интерпретироваться вместе с quality bounds comparison/significance layers.
