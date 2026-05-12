# Citation Insertion Plan

> План показывает, где вставлять ссылки на следующей фазе. Фаза 27 не меняет основной текст диссертации.

## Введение

| Paragraph / claim | Suggested citation IDs | Comment |
|---|---|---|
| После первого абзаца актуальности о росте нормативной информации / электронного документооборота. | SRC-DMS-001, SRC-DMS-002 | Вставить 1–2 ссылки. SRC-DMS-001 даёт макро-контекст роста данных; SRC-DMS-002 — управление records/document lifecycle. |
| Абзац о СЭД/DMS/ECM и границах существующих систем. | SRC-DMS-003, SRC-DMS-004 | Лучше группа из 2 источников: классический DMS + ECM. |
| Абзац о document comparison и структурных ограничениях diff. | SRC-DIFF-002, SRC-DIFF-003, SRC-DIFF-004 | Достаточно 2–3 источников; SRC-DIFF-004 нужен для structure-aware части. |
| Абзац о Legal NLP / document intelligence. | SRC-LEGALNLP-001, SRC-DOCINT-001, SRC-DOCINT-002 | Использовать как общий научный контекст, без утверждения о прямой применимости к каждой задаче. |
| Абзац о LLM risks и optional LLM layer. | SRC-LLM-001, SRC-LLM-002, SRC-LLM-003, SRC-HITL-004 | Нужна группа источников: hallucination/factuality + grounding + risk management. |

## Глава 1

| Paragraph / claim | Suggested citation IDs | Comment |
|---|---|---|
| 1.1: тезис о масштабировании ручного контроля изменений. | SRC-DMS-001, SRC-DMS-002 | Вставить после placeholder в конце первого смыслового блока. |
| 1.2: особенности нормативных документов как структурированных объектов. | SRC-LEGAL-002, SRC-LEGAL-003 | Поддержать иерархию, метаданные и machine-readable legal document model. |
| 1.3: контроль усвоения изменений сотрудниками. | SRC-AQG-004, SRC-AQG-005 | Эти источники лучше использовать осторожно: они об item quality, а не о compliance process в целом. |
| 1.4: СЭД/DMS/ECM. | SRC-DMS-003, SRC-DMS-004 | Не утверждать, что все СЭД не умеют аналитику; формулировать как “не всегда закрывают полный контур”. |
| 1.4: legal reference systems vs локальная обработка редакций. | SRC-LEGAL-001, SRC-LEGAL-003, SRC-LEGALNLP-001 | Дать разграничение классов систем и задач. |
| 1.4–1.5: diff approaches. | SRC-DIFF-001, SRC-DIFF-002, SRC-DIFF-003, SRC-DIFF-004, SRC-DIFF-005 | Для ключевого тезиса нужна группа источников. SRC-DIFF-005 оставить после проверки издательских данных. |
| 1.4–1.5: Legal NLP and legal document understanding. | SRC-LEGALNLP-001, SRC-LEGALNLP-002, SRC-LEGALNLP-003, SRC-LEGALNLP-004, SRC-LEGALNLP-005 | Можно использовать 3–4 источника, не обязательно все. |
| 1.5: LLM hallucinations, unsupported claims, groundedness. | SRC-LLM-001, SRC-LLM-002, SRC-LLM-003, SRC-LLM-004, SRC-LLM-005 | Для важного safety-тезиса использовать survey + factuality + RAG/self-check. |
| 1.6: local-first and reproducible MVP. | SRC-ARCH-001, SRC-ARCH-002, SRC-ARCH-004 | SRC-ARCH-003 можно добавить после финальной проверки ГОСТ-полей. |

## Глава 2

| Paragraph / claim | Suggested citation IDs | Comment |
|---|---|---|
| 2.2: сопоставление гибридного метода с document intelligence pipeline. | SRC-DOCINT-001, SRC-DOCINT-002, SRC-DOCINT-004, SRC-DOCINT-005 | Ссылки нужны для контекста; формула M является собственной разработкой и не требует внешнего источника. |
| 2.5: structural chunking. | SRC-LEGAL-003, SRC-DOCINT-002, SRC-DOCINT-004 | Нужны 2–3 источника о структуре/legal markup/layout-aware processing. |
| 2.6: structure-aware comparison. | SRC-DIFF-004, SRC-DIFF-005, SRC-DIFF-006 | SRC-DIFF-005 пометить к финальной проверке. |
| 2.7: rule-based classifier as explainable baseline. | SRC-LEGALNLP-003, SRC-HITL-001, SRC-HITL-003 | Ссылки подтверждают контекст legal NLP/evaluation/HITL; конкретные правила классификатора — собственное решение. |
| 2.8: generated summary as intermediate artifact. | SRC-LLM-002, SRC-LLM-005 | Ссылки нужны только для factuality/verification risks; реализация summary — собственная. |
| 2.9: quiz generation. | SRC-AQG-001, SRC-AQG-002, SRC-AQG-003, SRC-AQG-004, SRC-AQG-005 | Использовать 3–4 источника: AQG survey + ranking + item quality. |
| 2.10: approval workflow. | SRC-HITL-001, SRC-HITL-002, SRC-HITL-003, SRC-HITL-004 | Обосновать human-in-the-loop как quality/safety gate. |
| 2.11: local launch, materialized artifacts, reproducibility. | SRC-ARCH-001, SRC-ARCH-002, SRC-ARCH-004 | Docker source optional; собственные команды запуска не требуют внешнего источника. |

## Глава 3

| Paragraph / claim | Suggested citation IDs | Comment |
|---|---|---|
| 3.2–3.3: prepared synthetic evaluation corpus and limitations. | SRC-EVAL-003, SRC-EVAL-004 | Вставить в methodological limitations; не заменяет описание собственного corpus. |
| 3.3–3.9: precision, recall, F1, classification metrics. | SRC-EVAL-001, SRC-EVAL-002 | Достаточно одного-двух методологических источников; не перегружать таблицы метрик ссылками. |
| 3.10–3.11: threats to validity. | SRC-EVAL-003, SRC-EVAL-004, SRC-ARCH-002 | Ссылки вставить в начало subsection 3.11. |
| 3.4–3.9: конкретные численные результаты проекта. | не требуется внешний источник | Это собственные экспериментальные результаты; ссылаться на docs/experiments и таблицы/рисунки проекта, а не на внешнюю литературу. |

## Заключение

| Paragraph / claim | Suggested citation IDs | Comment |
|---|---|---|
| Выводы о достижении цели и задач. | не требуется внешний источник | Это итог собственных результатов; внешние ссылки нужны только если повторяются общие claims из введения. |
| Ограничения применимости MVP / synthetic corpus. | SRC-EVAL-003, SRC-EVAL-004 | Можно сослаться на methodological framing, но не заменять собственное описание ограничений. |
| Направления дальнейшего развития: OCR, LLM, экспертная разметка. | SRC-DOCINT-003, SRC-LLM-001, SRC-HITL-003 | Вставлять только если раздел остаётся развёрнутым; иначе можно оставить без новых ссылок. |
