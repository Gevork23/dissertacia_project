# Quiz Generation Evaluation

## 1. Цель эксперимента

Цель Фазы 18 — оценить, насколько production quiz generation формирует пригодные контрольно-обучающие материалы по значимым изменениям документов из evaluation corpus. Проверяются не только наличие вопросов, но и их связь с изменением, юридическая корректность, однозначность правильного ответа, качество distractors, отсутствие редакционного шума, traceability и полезность для сотрудника.

## 2. Связь с гибридным методом

Эксперимент относится к этапу `G — Generation of control-learning materials` гибридного метода `M = <E, N, S, C, P, G, R>`. В текущем MVP quiz generation получает не raw document, а summary highlights, сформированные после structural comparison и significance-layer.

## 3. Evaluation corpus

Использован `data/evaluation_corpus/`: 10 синтетических пар документов с `annotation.json`, `expected_changes`, `importance`, `change_type`, `editorial_changes`, `known_difficulties`, `expected_summary_topics` и `expected_quiz_topics`. Валидатор корпуса проходит успешно. Всего размечено 13 expected changes; quiz-worthy important/critical topics для этой фазы — 9.

## 4. Что именно оценивается

Оценивается production-функция `build_quiz_from_summary(...)` из `backend/documents/domain/diff_quiz.py` при входе из pipeline. Workflow materialization в БД (`GeneratedQuiz`, `Question`, `Choice`) не переписывался; эксперимент запускает доменные функции in-memory, чтобы не изменять состояние проекта.

## 5. Evaluation mode

Основной режим — pipeline evaluation:

```text
chunk_by_structure_ru -> build_version_diff -> build_brief_summary -> build_quiz_from_summary
```

Дополнительно сохранён oracle diagnostic: в генератор подаются только annotation expected quiz-worthy changes. Этот режим нужен для отделения ошибок quiz generation от upstream errors и не смешивается с основными pipeline метриками.

## 6. Критерии оценки вопроса

| Criterion | Meaning | Scale |
|---|---|---|
| Change relevance | Связь вопроса с реальным expected change | 1-5 |
| Legal/domain correctness | Корректность формулировки и ответа | 1-5 |
| Unambiguous correct answer | Один очевидный правильный ответ | 1-5 |
| Distractor quality | Правдоподобность и не-дублирование distractors | 1-5 |
| No editorial noise | Вопрос не построен на редакционном/шумовом изменении | 1-5 |
| Explanation/source quality | Наличие объяснения и traceability | 1-5 |
| Employee usefulness | Практическая полезность для сотрудника | 1-5 |

## 7. Scoring rubric

Шкала 1-5: `1` — критерий провален, вопрос misleading/шумовой; `3` — частично приемлемо, но есть существенные ограничения; `5` — критерий выполнен полностью. `overall_question_score` считается как среднее по семи критериям.

## 8. Метрики

Для каждой пары рассчитаны `questions_count`, `correct_questions`, `relevant_questions`, `questions_with_source`, `important_changes`, `covered_important_changes`, `coverage`, `avg_question_score`, `editorial_noise_questions`. Aggregate metrics считаются по question-level строкам и coverage важных/critical expected quiz topics.

## 9. Результаты по вопросам

| Pair | Questions | Correct | Relevant | With source | Coverage | Avg score |
|---|---|---|---|---|---|---|
| pair_01_deadline_change | 1 | 1 | 1 | 1 | 1.0000 | 4.8571 |
| pair_02_added_obligation | 1 | 1 | 1 | 1 | 1.0000 | 4.8571 |
| pair_03_document_list_change | 1 | 1 | 1 | 1 | 1.0000 | 4.8571 |
| pair_04_refusal_ground_change | 1 | 1 | 1 | 1 | 1.0000 | 4.8571 |
| pair_05_editorial_change | 1 | 0 | 0 | 1 | 0.0000 | 1.5714 |
| pair_06_procedure_change | 1 | 0 | 0 | 1 | 0.0000 | 2.8571 |
| pair_07_responsibility_change | 1 | 1 | 1 | 1 | 1.0000 | 3.8571 |
| pair_08_reordered_structure | 0 | 0 | 0 | 0 | 1.0000 | 0.0000 |
| pair_09_mixed_significant_and_editorial | 4 | 2 | 2 | 4 | 1.0000 | 3.4286 |
| pair_10_weakly_structured_document | 1 | 1 | 1 | 1 | 1.0000 | 4.5714 |

## 10. Aggregate results

| Metric | Value |
|---|---|
| Total pairs | 10 |
| Total questions | 12 |
| Correct question rate | 0.6667 |
| Relevant question rate | 0.6667 |
| Source/explanation rate | 1.0000 |
| Important change coverage | 0.8889 |
| Editorial/noise question rate | 0.2500 |
| Average question score | 3.8333 |

## 11. Important change coverage

Pipeline quiz generation покрыл 8 из 9 important/critical expected quiz topics (`0.8889`). Не покрыт ожидаемый topic `новый способ подачи заявления` в `pair_06_procedure_change`: вопрос был связан с правильным source fragment, но upstream semantic classification подал его в quiz generator как document-list change, поэтому answer не проверяет электронную форму во внутреннем портале.

Oracle diagnostic при корректном входе даёт coverage 1.0000 (9 / 9). Этот режим не является реальным pipeline score; он показывает, какие темы quiz generator способен сформулировать при корректном annotation-driven входе, без ошибок structural diff/significance/summary.

## 12. Source/explanation analysis

`source_explanation_rate` = `1.0000`: все сгенерированные вопросы имеют explanation и source metadata/title/old-new text. Однако наличие source не равно корректности вопроса: слабые вопросы в `pair_05` и `pair_09` тоже traceable, но traceability помогает reviewer обнаружить, что source является editorial/noise.

Количество вопросов с explanation/source quality ниже 4: 3. Основная причина снижения — не отсутствие source, а то, что explanation повторяет upstream ошибочную semantic framing.

## 13. Distractor quality analysis

Средняя оценка distractor quality = `3.2500`. Сильная сторона baseline — distractors обычно не дублируют correct answer и дают single-choice структуру. Ограничение — distractors часто generic (`изменений не было`, `перечень документов остался прежним`) либо берутся из answer pool других true changes. В `pair_09` это делает варианты правдоподобными, но методически спорными: distractor может быть истинным изменением документа, просто не отвечающим на данный вопрос.

## 14. Editorial/noise question analysis

Editorial/noise question rate = `0.2500` (3 / 12). Слабые случаи:

- `pair_05_editorial_change`: editorial verb replacement превращён в critical document-list question.
- `pair_09_mixed_significant_and_editorial:q3`: informational notice over-framed as procedure.
- `pair_09_mixed_significant_and_editorial:q4`: editorial wording replacement превращён в deadline question.

Эти ошибки относятся преимущественно к upstream significance/summary representation, потому что quiz generator получает уже завышенные labels/highlights.

## 15. Good question examples

- `pair_01_deadline_change_q01`: новый срок рассмотрения заявления — overall `4.8571`; Directly checks the changed deadline and preserves old/new values.
- `pair_02_added_obligation_q01`: новая обязанность сотрудника по уведомлению заявителя — overall `4.8571`; Directly checks the added notification obligation.
- `pair_03_document_list_change_q01`: новый документ в перечне обязательных документов — overall `4.8571`; Checks the added representative-authority document.
- `pair_04_refusal_ground_change_q01`: новое основание отказа — overall `4.8571`; Checks the new refusal ground without changing its legal condition.
- `pair_09_mixed_significant_and_editorial_q01`: новый срок подготовки справки — overall `4.7143`; Good deadline question in a mixed-change pair.

## 16. Weak question examples

- `pair_09_mixed_significant_and_editorial_q04`: overall `1.4286`; Editorial wording replacement is incorrectly converted into a critical deadline question.
- `pair_05_editorial_change_q01`: overall `1.5714`; Weak case: an editorial verb replacement is over-prioritized upstream and becomes a false document-list question.
- `pair_06_procedure_change_q01`: overall `2.8571`; The source is the real procedure change, but the generated question frames it as a document-list change and misses the electronic-form topic.
- `pair_09_mixed_significant_and_editorial_q03`: overall `2.8571`; Informational status notice is turned into a procedure question; this is traceable but weak as an employee knowledge-control item.

## 17. Связь с summary/significance evaluation

Phase 16 significance: important/critical recall = 1.0, precision = 0.75, editorial false-positive rate = 0.6667.
Phase 17 summary: overall average = 4.1167, covered topics = 8 / 9, missed topics = 1, unsupported claims = 5, editorial/noise overemphasis = 4.

Quiz generation зависит от significance-layer: если significance завышает editorial/informational change, generator воспринимает его как допустимый highlight и строит question. Поэтому ошибки `pair_05` и части `pair_09` классифицируются как upstream-induced. Quiz generation также зависит от summary/source representation: если summary highlight имеет неверный semantic type, вопрос получает неверный template, как в `pair_06` и частично `pair_07`.

## 18. Human-in-the-loop approval

Generated quiz не должен автоматически становиться финальным учебным материалом. В MVP responsible person approval является обязательным quality gate: `GeneratedQuiz` проходит состояния `draft -> pending_review -> approved/rejected`, а employee attempts разрешаются только для approved quiz. Для нормативной области это принципиально: reviewer проверяет legal wording, source reference, корректность correct answer и отсутствие questions по editorial/noise. Это не слабость метода, а осознанное инженерное ограничение MVP.

## 19. Ограничения эксперимента

- Corpus малый и синтетический: 10 пар документов.
- Expert scoring частично ручной, поскольку legal/domain correctness и usefulness нельзя надежно вывести только lexical matching.
- Pipeline-mode метрики включают ошибки upstream stages.
- Oracle diagnostic не является реальным pipeline score.
- ORM workflow не запускался для сохранения GeneratedQuiz rows; использованы те же domain generation functions in-memory.
- Production quiz generation algorithm не изменялся ради улучшения метрик.

## 20. Вывод для диссертации

Экспериментальная оценка quiz generation показала, что этап `G` формирует проверяемые single-choice контрольно-обучающие материалы по большинству important/critical изменений: coverage составил 0.8889, average expert score — 3.8333, доля вопросов с source/explanation — 1.0000. Лучшие вопросы возникают для сроков, обязанностей, перечней документов и оснований отказа. Основные слабые случаи связаны с upstream over-prioritization editorial/informational changes и неверным semantic framing. Следовательно, quiz generation применим для MVP как материализованный baseline-этап гибридного метода, но только при обязательном human-in-the-loop утверждении ответственным лицом.
