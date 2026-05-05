# Tasks

## 1. Completed MVP stabilization

- [x] Phase 1 — current state audit
- [x] Phase 2 — repository cleanup
- [x] Phase 3 — service layer deduplication
- [x] Phase 4 — LLM fallback normal mode
- [x] Phase 5 — MVP scope freeze

Результат блока: технический MVP больше не расширяется продуктовыми функциями до завершения научной упаковки. Защищаемый pipeline зафиксирован как:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

## 2. Active next block: research core

- [ ] Phase 6 — hybrid method formalization
- [ ] Phase 7 — system architecture formalization
- [ ] Phase 8 — structural chunking method
- [ ] Phase 9 — version comparison method
- [ ] Phase 10 — significance method
- [ ] Phase 11 — quiz generation method

Правило блока: формализуем уже реализованный MVP, а не добавляем новые runtime-функции.

## 3. Experiment block

- [ ] Phase 12 — demo corpus formalization for experiments
- [ ] Phase 13 — evaluation corpus design
- [ ] Phase 14 — chunking evaluation
- [ ] Phase 15 — diff evaluation
- [ ] Phase 16 — significance evaluation
- [ ] Phase 17 — summary evaluation
- [ ] Phase 18 — quiz evaluation
- [ ] Phase 19 — final evaluation

Правило блока: экспериментальные корпуса и метрики создаются после методической формализации, не в Фазе 5.

## 4. Thesis block

- [ ] Phase 20 — thesis structure synchronization
- [ ] Phase 21 — chapter on problem statement and related work
- [ ] Phase 22 — chapter on proposed hybrid method
- [ ] Phase 23 — chapter on system architecture and implementation
- [ ] Phase 24 — chapter on experiments and evaluation
- [ ] Phase 25 — final thesis editing and consistency pass

## 5. Defense block

- [ ] Phase 26 — final documentation package
- [ ] Phase 27 — demo script freeze
- [ ] Phase 28 — presentation
- [ ] Phase 29 — defense Q&A preparation

## 6. Explicitly postponed future work

Эти задачи не являются долгами текущего MVP и не выполняются до завершения научной упаковки:

- [ ] OCR for scanned PDF
- [ ] Full RAG-chat
- [ ] LangGraph / multi-agent workflow
- [ ] Consultant+ / external legal system integration
- [ ] External legal monitoring
- [ ] Production auth/RBAC
- [ ] Enterprise BI/dashboard
- [ ] Large LMS functionality
- [ ] Production-grade user management
- [ ] Distributed/cloud-first deployment
- [ ] Training or fine-tuning a custom large model
- [ ] Universal search across all laws of the Russian Federation

## 7. Scope control rule

Новая задача попадает в текущий рабочий контур только если она:

- поддерживает уже зафиксированный MVP pipeline;
- нужна для научной формализации реализованного метода;
- нужна для воспроизводимого эксперимента в соответствующей будущей фазе;
- нужна для защиты.

Если задача расширяет продукт за пределы pipeline «версия → результат», она переносится в `Explicitly postponed future work`.
