# Evaluation Corpus Description

## 1. Назначение корпуса

Evaluation corpus создан в Фазе 13 как небольшой, воспроизводимый и вручную размеченный набор синтетических пар документов. Он предназначен для будущего расчёта метрик качества компонентов метода `M = <E, N, S, C, P, G, R>`.

Корпус проверяет:

- structural chunking;
- version comparison / diff;
- significance classification;
- summary generation;
- quiz generation.

## 2. Почему нужен отдельный evaluation corpus

Demo corpus из Фазы 12 нужен для показа MVP pipeline комиссии. Он короткий и демонстрационный.

Evaluation corpus нужен для экспериментальной главы: он содержит ручной эталон, отрицательные примеры, смешанные изменения, weakly structured document и зафиксированные limitations. Это позволяет в следующих фазах считать метрики и честно описывать ошибки baseline.

## 3. Принципы подготовки документов

Документы подготовлены как синтетические внутренние регламенты и памятки. При подготовке соблюдены принципы:

- нет персональных данных, паспортов, адресов, реальных ФИО и реальных внутренних регламентов;
- формат TXT выбран для воспроизводимости и совместимости с текущим ingestion pipeline;
- документы достаточно структурированы для chunking, кроме специально выделенного weakly structured case;
- пары небольшие и пригодны для ручной проверки;
- каждая пара имеет `annotation.json`;
- аннотация описывает не только изменения, но и expected chunks, significance, summary и quiz topics.

## 4. Структура каталога

```text
data/evaluation_corpus/
    pair_01_deadline_change/
        old.txt
        new.txt
        annotation.json
    pair_02_added_obligation/
        old.txt
        new.txt
        annotation.json
    ...
    pair_10_weakly_structured_document/
        old.txt
        new.txt
        annotation.json
```

## 5. Список пар документов

| Pair | Scenario | Main change types | Expected importance | Used for |
|---|---|---|---|---|
| `pair_01_deadline_change` | Deadline change | modified | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_02_added_obligation` | Added obligation | added | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_03_document_list_change` | Document list change | added | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_04_refusal_ground_change` | Refusal ground change | added | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_05_editorial_change` | Editorial change | modified | editorial | Chunking, Diff/comparison, Significance, Summary, No-quiz control |
| `pair_06_procedure_change` | Procedure change | modified | important | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_07_responsibility_change` | Responsibility change | added | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_08_reordered_structure` | Reordered structure | moved | editorial | Chunking, Diff/comparison, Significance, Summary, No-quiz control |
| `pair_09_mixed_significant_and_editorial` | Mixed significant and editorial | added, modified | critical, editorial, informational | Chunking, Diff/comparison, Significance, Summary, Quiz generation |
| `pair_10_weakly_structured_document` | Weakly structured document | modified | critical | Chunking, Diff/comparison, Significance, Summary, Quiz generation |

## 6. Pair descriptions

### 1. `pair_01_deadline_change` — Изменение срока рассмотрения заявления

Сценарий: `Deadline change`. Основная проверка: Срок рассмотрения заявления сокращен с 10 до 7 рабочих дней.. Ключевые chunks: Раздел 2, статья 2, пункт 1. Ожидаемые quiz topics: новый срок рассмотрения заявления.

### 2. `pair_02_added_obligation` — Добавление обязанности уведомления заявителя

Сценарий: `Added obligation`. Основная проверка: Добавлена новая обязанность сотрудника уведомлять заявителя о результате рассмотрения обращения.. Ключевые chunks: Раздел 2, статья 2, пункт 3. Ожидаемые quiz topics: новая обязанность сотрудника по уведомлению заявителя.

### 3. `pair_03_document_list_change` — Добавление документа в обязательный перечень

Сценарий: `Document list change`. Основная проверка: В перечень обязательных документов добавлена копия документа, подтверждающего полномочия представителя.. Ключевые chunks: Раздел 2, статья 2, пункт 1, подпункт г. Ожидаемые quiz topics: новый документ в перечне обязательных документов.

### 4. `pair_04_refusal_ground_change` — Добавление основания для отказа

Сценарий: `Refusal ground change`. Основная проверка: Добавлено новое основание отказа: непредставление обязательных документов в установленный срок.. Ключевые chunks: Раздел 2, статья 3, пункт 3. Ожидаемые quiz topics: новое основание отказа.

### 5. `pair_05_editorial_change` — Редакционное изменение без смыслового влияния

Сценарий: `Editorial change`. Основная проверка: Редакционная замена глагола без изменения обязанности, срока, перечня документов или процедуры.. Ключевые chunks: Раздел 2, статья 2, пункт 1, Раздел 2, статья 2, пункт 1. Ожидаемые quiz topics: не ожидаются.

### 6. `pair_06_procedure_change` — Изменение порядка подачи заявления

Сценарий: `Procedure change`. Основная проверка: Изменен порядок подачи заявления: добавлена возможность подачи через электронную форму во внутреннем портале.. Ключевые chunks: Раздел 2, статья 2, пункт 1, Раздел 2, статья 2, пункт 1. Ожидаемые quiz topics: новый способ подачи заявления.

### 7. `pair_07_responsibility_change` — Добавление ответственности за нарушение срока

Сценарий: `Responsibility change`. Основная проверка: Добавлено правило об ответственности сотрудника за нарушение срока обработки заявления.. Ключевые chunks: Раздел 2, статья 3, пункт 2. Ожидаемые quiz topics: ответственность за нарушение срока.

### 8. `pair_08_reordered_structure` — Перенос фрагмента без изменения текста

Сценарий: `Reordered structure`. Основная проверка: Фрагмент перенесен в другой структурный раздел без изменения содержания.. Ключевые chunks: Раздел 2, статья 2, пункт 2, Раздел 3, статья 3, пункт 1. Ожидаемые quiz topics: не ожидаются.

### 9. `pair_09_mixed_significant_and_editorial` — Смешанные значимые, информационные и редакционные изменения

Сценарий: `Mixed significant and editorial`. Основная проверка: Срок подготовки справки сокращен с 5 до 4 рабочих дней.; Редакционная замена глагола без изменения процедуры проверки.; Добавлена обязанность уведомить заявителя о невозможности подготовки справки.; Добавлено справочное указание о доступности статуса запроса.. Ключевые chunks: Раздел 2, статья 2, пункт 1, Раздел 2, статья 2, пункт 4. Ожидаемые quiz topics: новый срок подготовки справки, уведомление при невозможности подготовки справки.

### 10. `pair_10_weakly_structured_document` — Слабо структурированный документ для fallback chunking

Сценарий: `Weakly structured document`. Основная проверка: В слабо структурированном документе срок рассмотрения обращения изменен с 5 до 3 рабочих дней.. Ключевые chunks: fallback-блок 'Рассмотрение обращения'. Ожидаемые quiz topics: новый срок рассмотрения обращения.

## 7. Coverage по типам изменений

- `added`: 6
- `modified`: 6
- `moved`: 1

Дополнительно по semantic types:

- `deadline`: 3
- `document`: 1
- `editorial`: 2
- `informational`: 1
- `obligation`: 2
- `procedure`: 1
- `refusal`: 1
- `responsibility`: 1
- `structure`: 1

## 8. Coverage по категориям значимости

- `critical`: 8
- `editorial`: 3
- `important`: 1
- `informational`: 1

В проекте используются штатные labels `critical`, `important`, `informational`, `editorial`, `not_evaluated`. Вручную размеченные целевые изменения покрывают первые четыре категории; `not_evaluated` оставлен как техническая категория pipeline.

## 9. Coverage по задачам оценки

| Evaluation task | Pairs used |
|---|---|
| Chunking | `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_03_document_list_change`, `pair_04_refusal_ground_change`, `pair_05_editorial_change`, `pair_06_procedure_change`, `pair_07_responsibility_change`, `pair_08_reordered_structure`, `pair_09_mixed_significant_and_editorial`, `pair_10_weakly_structured_document` |
| Diff/comparison | `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_03_document_list_change`, `pair_04_refusal_ground_change`, `pair_05_editorial_change`, `pair_06_procedure_change`, `pair_07_responsibility_change`, `pair_08_reordered_structure`, `pair_09_mixed_significant_and_editorial`, `pair_10_weakly_structured_document` |
| Significance | `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_03_document_list_change`, `pair_04_refusal_ground_change`, `pair_05_editorial_change`, `pair_06_procedure_change`, `pair_07_responsibility_change`, `pair_08_reordered_structure`, `pair_09_mixed_significant_and_editorial`, `pair_10_weakly_structured_document` |
| Summary | `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_03_document_list_change`, `pair_04_refusal_ground_change`, `pair_05_editorial_change`, `pair_06_procedure_change`, `pair_07_responsibility_change`, `pair_08_reordered_structure`, `pair_09_mixed_significant_and_editorial`, `pair_10_weakly_structured_document` |
| Quiz generation | `pair_01_deadline_change`, `pair_02_added_obligation`, `pair_03_document_list_change`, `pair_04_refusal_ground_change`, `pair_06_procedure_change`, `pair_07_responsibility_change`, `pair_09_mixed_significant_and_editorial`, `pair_10_weakly_structured_document` |
| No-quiz / negative controls | `pair_05_editorial_change`, `pair_08_reordered_structure` |

## 10. Связь с будущими экспериментами

Фаза 14 сможет использовать `expected_chunks` для оценки полноты и точности structural chunking. Фаза 15 сможет использовать `expected_changes` для comparison metrics. Фаза 16 сможет сравнивать `importance` и `semantic_type` с результатами significance-layer. Фаза 17 сможет проверять `expected_summary.must_mention` и `must_not_mention`. Фаза 18 сможет проверять `expected_quiz` и `expected_quiz_topics`.

Корпус не запускает эксперименты сам по себе. Он является входом для будущих фаз.

## 11. Ограничения корпуса

- Все документы синтетические и не являются нормативными актами.
- Объём корпуса малый: 10 пар достаточно для MVP evaluation и главы 3, но не для статистически сильного промышленного benchmark.
- Ручная разметка может содержать экспертную неоднозначность, особенно для `editorial` vs `important`.
- Pair 08 специально фиксирует ограничение текущей реализации moved detection.
- Pair 10 специально использует weak structure, поэтому chunk границы ожидаются как fallback-блоки.
- TXT выбран осознанно; DOCX/PDF не используются, чтобы не смешивать оценку document intelligence pipeline с бинарной extraction variability.

## 12. Вывод

Созданный evaluation corpus отделён от demo corpus, содержит 10 синтетических пар документов и ручную разметку, пригодную для Фаз 14–18. Он покрывает содержательные, редакционные, информационные, структурные и fallback-сценарии, необходимые для доказательной базы экспериментальной главы диссертации.
