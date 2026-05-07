# Integrated Evaluation of the Hybrid Method

## 1. Цель сводной оценки

Фаза 19 объединяет результаты частных экспериментов Фаз 14–18 в единую экспериментальную оценку гибридного метода. Цель оценки — показать не только значения отдельных метрик, но и связность pipeline: как структурное разбиение влияет на сравнение версий, как noise из comparison-layer может попадать в significance-layer, summary и quiz generation, и насколько весь метод пригоден для локального MVP-сценария.

## 2. Связь с методом M = <E, N, S, C, P, G, R>

Экспериментально оценивались этапы S, C, P и два downstream-проявления G: summary и quiz generation. Этапы E, N и R входят в общий MVP pipeline как инфраструктурные компоненты, но в Фазах 14–18 не оценивались отдельными метриками качества. Поэтому выводы Фазы 19 относятся к воспроизводимой цепочке от structural chunking до контрольных материалов, а не к полному юридическому анализу документа.

## 3. Evaluation corpus

Использован evaluation corpus из 10 синтетических пар документов в `data/evaluation_corpus/`. Корпус содержит deadline, obligation, document-list, refusal-ground, procedure, responsibility, mixed and weakly structured cases, а также editorial/reordered cases для проверки noise handling. Аннотация является key-change / key-boundary annotation и не является полным full-document gold standard.

## 4. Сводка частных экспериментов

| Phase | Component | Required artifacts | Status | Notes |
|---|---|---|---|---|
| 14 | Structural chunking | docs/experiments/chunking-evaluation.md; experiments/chunking/chunking_results.csv; experiments/chunking/chunking_summary.json; experiments/chunking/chunking_f1.png | complete | Found 4/4. |
| 15 | Diff/comparison | docs/experiments/diff-evaluation.md; experiments/diff/diff_results.csv; experiments/diff/diff_summary.json; experiments/diff/diff_fp_fn.png; experiments/diff/diff_precision_recall_f1.png | complete | Found 5/5. |
| 16 | Significance | docs/experiments/significance-evaluation.md; experiments/significance/significance_results.csv; experiments/significance/significance_summary.json; experiments/significance/significance_confusion_matrix.png; experiments/significance/significance_class_metrics.png | complete | Found 5/5. |
| 17 | Summary | docs/experiments/summary-evaluation.md; experiments/summary/summary_results.csv; experiments/summary/summary_evaluation_summary.json; experiments/summary/summary_pair_scores.png; experiments/summary/summary_quality_scores.png | complete | Found 5/5. |
| 18 | Quiz generation | docs/experiments/quiz-generation-evaluation.md; experiments/quiz/quiz_results.csv; experiments/quiz/quiz_pair_results.csv; experiments/quiz/quiz_evaluation_summary.json; experiments/quiz/quiz_coverage.png; experiments/quiz/quiz_pair_scores.png; experiments/quiz/quiz_quality_scores.png | complete | Found 7/7. |

## 5. Results by pipeline stage

| Stage | Component | Metric | Result | Interpretation |
|---|---|---|---|---|
| S | Structural chunking | micro F1 / key recall | 0.293 / 1.0 | Hybrid better than baselines on target/key boundary annotation. |
| C | Structural comparison | F1 / noise_count | 0.8695 / 3 | Lower noise than plain-text and paragraph baselines. |
| P | Significance | important/critical recall / F1 | 1.0 / 0.8571 | Recall-oriented high-priority detection; precision affected by overclassification. |
| G-summary | Summary | overall average / topics | 4.1167 / 8/9 | Useful human-readable representation, but upstream-dependent. |
| G-quiz | Quiz generation | coverage / average question score | 0.8889 / 3.8333 | Most important changes covered; approval remains required. |

## 6. End-to-end trace analysis

End-to-end trace сохранён в `experiments/final/end_to_end_trace.csv` и построен для expected important/critical changes. Для каждого изменения зафиксировано, было ли оно обнаружено structural diff, классифицировано как significant, отражено в summary topic и покрыто quiz topic/question.

Ключевое наблюдение: все 9 important/critical changes были обнаружены comparison-layer и классифицированы как significant. Один expected change (`pair_06_procedure_change`) не прошёл downstream summary/quiz coverage: изменение процедуры подачи заявления было найдено и классифицировано, но не попало в summary topic и quiz topic.

## 7. End-to-end coverage

- important_changes_total: 9
- important_changes_detected_by_diff: 9
- important_changes_classified_as_significant: 9
- important_changes_covered_by_summary: 8
- important_changes_covered_by_quiz: 8
- strict_end_to_end_success_rate: 0.8889
- practical_end_to_end_success_rate: 0.8889

Strict success означает: diff_detected=yes, significance_correct=yes, summary_covered=yes, quiz_covered=yes. Practical success означает, что change дошло до summary или quiz в полезной форме при сохранении diff/significance detection. На текущем corpus оба показателя равны 0.8889, потому что один important procedure change не был покрыт ни summary, ни quiz.

## 8. Error propagation analysis

| Error source | Downstream effect | Evidence from phases | Interpretation |
|---|---|---|---|
| Chunking boundary error | Diff may miss, merge, or split an expected change. | Phase 14 key-boundary evaluation and Phase 15 strict diff notes/known difficulties. | Structural comparison depends on stable chunk boundaries; corpus results are strong but not a full segmentation guarantee. |
| Diff false positive / noise | Noise can be treated as a candidate semantic change by the significance layer. | Phase 15 structural noise_count=3; plain text noise_count=10; paragraph noise_count=8. | Structural diff reduces but does not eliminate noise entering P/G stages. |
| Significance overclassification | Editorial/informational changes may be promoted to important highlights. | Phase 16 editorial high-priority false positives=2; Phase 17 editorial/noise overemphasis=4; Phase 18 weak/noise questions. | Recall-oriented baseline is MVP-suitable only with human-in-the-loop approval. |
| Weak upstream summary representation | Quiz generation can materialize weak or less relevant questions. | Phase 17 unsupported claims=5; Phase 18 correct/relevant question rate=0.6667. | Source traceability helps review, but approval by responsible staff remains required. |

## 9. Сильные стороны метода

- Метод воспроизводим и материализован в repository artifacts: CSV, JSON, PNG и Markdown reports.
- Structural chunking улучшает обнаружение meaningful/key boundaries по сравнению с baselines.
- Structural comparison снижает strict noise_count и повышает интерпретируемость diff.
- Significance-layer не пропускает important/critical changes на текущем corpus.
- Summary-layer делает технические результаты diff/significance понятными для пользователя.
- Quiz generation покрывает большинство важных изменений и формирует применимые baseline questions.
- Human-in-the-loop approval workflow снижает риск использования слабых или noisy вопросов.
- Локальный deterministic baseline работает без обязательного LLM, RAG или внешнего сервиса.

## 10. Ограничения метода

- Evaluation corpus синтетический и небольшой: 10 пар документов.
- Key-change annotation не равна full-document gold standard.
- Chunking evaluation оценивает selected expected chunks, а не все возможные валидные boundaries.
- Significance baseline является recall-oriented и может overclassify editorial/informational noise.
- Summary может содержать unsupported claims или over-framed highlights.
- Quiz generation может материализовать слабые вопросы из upstream noise.
- Human-in-the-loop approval обязателен для MVP.
- Метод не заменяет юридическую экспертную оценку.
- В scope отсутствуют OCR, full RAG/legal search, enterprise LMS/RBAC.

## 11. Практическая применимость MVP

Результаты подтверждают практическую применимость гибридного метода для локального MVP-сценария: pipeline обнаруживает и проводит через stages большинство важных изменений, а обязательное согласование вопросов ответственным лицом компенсирует риски downstream materialization of noise. Метод пригоден как baseline document intelligence workflow для нормативно-правовых и внутренних регламентных документов при ограниченном scope.

## 12. Роль human-in-the-loop

Human-in-the-loop является не декоративным, а необходимым элементом safety and quality control. Approval workflow должен проверять summary highlights и generated quiz questions, особенно при editorial/noise overemphasis, unsupported claims и weak questions. Это позволяет использовать recall-oriented deterministic baseline без утверждения, что система автономно заменяет эксперта.

## 13. Threats to validity

### Internal validity

Метрики зависят от качества annotation. Pipeline stages влияют друг на друга: ошибки S/C могут менять вход P/G. Часть summary/quiz evaluation основана на expert-style rubric, а не на полностью автоматическом объективном gold standard.

### External validity

Корпус синтетический и ограничен по числу типов документов. Результаты нельзя обобщать на все нормативные акты, юридические документы или реальные enterprise archives без дополнительных экспериментов.

### Construct validity

Key-change metrics измеряют ожидаемые изменения, а не exhaustive legal diff. Summary/quiz quality scores являются semi-expert criteria и отражают применимость материалов, но не гарантируют юридическую полноту.

### Reproducibility

Все входные и выходные experiment artifacts сохранены в repository. Aggregation script производит CSV/JSON/PNG outputs из уже существующих summary artifacts. Deterministic baseline может быть локально перезапущен.

## 14. Что можно утверждать в диссертации

1. В рамках подготовленного evaluation corpus structural comparison показал более высокий F1 и меньший noise_count по сравнению с plain text и paragraph baselines.
2. Rule-based significance-layer работает как recall-oriented baseline для high-priority изменений, не пропуская critical/important changes на текущем corpus.
3. Summary-layer обеспечивает понятное human-readable представление изменений, но зависит от качества upstream stages.
4. Quiz generation покрывает большинство важных изменений и формирует применимые baseline questions, однако требует human-in-the-loop approval.
5. В совокупности результаты подтверждают практическую применимость гибридного метода для локального MVP-сценария.

## 15. Что нужно формулировать осторожно

- Нельзя утверждать, что метод универсально превосходит все diff algorithms на всех нормативных документах.
- Нельзя утверждать, что significance-layer заменяет экспертную юридическую оценку.
- Нельзя утверждать, что quiz generation всегда формирует полностью корректные учебные материалы без проверки человеком.
- Нельзя обобщать результаты за пределы synthetic evaluation corpus без дополнительных экспериментов.
- Нельзя трактовать key-change recall/F1 как полную юридическую полноту анализа документа.

## 16. Future work

- Расширить evaluation corpus реальными и более разнообразными документами.
- Подготовить full-document segmentation gold standard для отдельной оценки S.
- Добавить более точную оценку moved/reordered fragments.
- Улучшить filtering of editorial/informational noise перед summary/quiz generation.
- Провести отдельную human expert evaluation для summary и quiz outputs.
- Подготовить финальные визуализации и dissertation-ready tables в Фазе 20.

## 17. Вывод для главы 3

Сводная экспериментальная оценка показала, что разработанный гибридный метод обеспечивает воспроизводимый pipeline от структурного анализа изменений до формирования контрольно-обучающих материалов. На подготовленном evaluation corpus structural comparison снизил шум по сравнению с baseline-подходами, significance-layer обеспечил высокий recall для важных изменений, summary-layer сформировал понятные выжимки, а quiz generation покрыл большинство значимых изменений. Ограничения эксперимента связаны с синтетическим корпусом, key-change annotation и необходимостью human-in-the-loop контроля, однако полученные результаты подтверждают применимость метода в рамках локального MVP.
