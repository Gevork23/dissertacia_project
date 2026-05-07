# Quiz Generation Examples

Examples are selected from the primary pipeline evaluation.

### Good example: pair_01_deadline_change_q01

Expected topic:
- новый срок рассмотрения заявления

Question:
Какое изменение по срокам должен учитывать сотрудник в разделе «Статья 2: Сроки рассмотрения · Пункт 1»?

Options:
A. Срок сокращён: было 10 рабочих дней, стало 7 рабочих дней.
B. Сроки выполнения требований не изменились.
C. Изменение касается только перечня документов, а не сроков.

Correct answer:
Срок сокращён: было 10 рабочих дней, стало 7 рабочих дней.

Explanation/source:
Проверяет понимание изменения: Срок сокращён: было 10 рабочих дней, стало 7 рабочих дней. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=deadline, entities=deadline_new,deadline_old, critical_keywords.

Scores:
- relevance: 5
- correctness: 5
- unambiguous answer: 5
- distractor quality: 4
- no editorial noise: 5
- explanation/source: 5
- usefulness: 5
- overall: 4.8571

What is good:
- directly linked to the deadline change
- correct answer is unambiguous
- source includes old and new deadline values

What is weak:
- distractors are generic rather than old-value based

Interpretation:
Directly checks the changed deadline and preserves old/new values.

### Good example: pair_02_added_obligation_q01

Expected topic:
- новая обязанность сотрудника по уведомлению заявителя

Question:
Какое изменение в обязанностях отражено в разделе «Статья 2: Подготовка результата · Пункт 3»?

Options:
A. Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений.
B. Обязанности сотрудников и заявителей не изменились.
C. Изменение касается только справочной информации.

Correct answer:
Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений.

Explanation/source:
Проверяет понимание изменения: Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=obligation, entities=staff_action.

Scores:
- relevance: 5
- correctness: 5
- unambiguous answer: 5
- distractor quality: 4
- no editorial noise: 5
- explanation/source: 5
- usefulness: 5
- overall: 4.8571

What is good:
- question is tied to the new obligation
- correct answer states the action and notification channel
- source/explanation are sufficient for reviewer validation

What is weak:
- distractors are mostly generic negations

Interpretation:
Directly checks the added notification obligation.

### Good example: pair_03_document_list_change_q01

Expected topic:
- новый документ в перечне обязательных документов

Question:
Какое изменение в перечне документов нужно учитывать в разделе «Статья 2: Обязательные документы · Пункт 1 · Подпункт г»?

Options:
A. Добавлен новый пункт о документах: копию документа, подтверждающего полномочия представителя, если заявление подает представитель.
B. Перечень документов остался прежним.
C. Изменение касается только сроков предоставления услуги.

Correct answer:
Добавлен новый пункт о документах: копию документа, подтверждающего полномочия представителя, если заявление подает представитель.

Explanation/source:
Проверяет понимание изменения: Добавлен новый пункт о документах: копию документа, подтверждающего полномочия представителя, если заявление подает представитель. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=document.

Scores:
- relevance: 5
- correctness: 5
- unambiguous answer: 5
- distractor quality: 4
- no editorial noise: 5
- explanation/source: 5
- usefulness: 5
- overall: 4.8571

What is good:
- question uses the document-list template
- answer contains the newly required document
- traceability points to the added subpoint

What is weak:
- distractors do not include near-miss document options

Interpretation:
Checks the added representative-authority document.

### Good example: pair_04_refusal_ground_change_q01

Expected topic:
- новое основание отказа

Question:
Какое изменение в основаниях отказа отражено в разделе «Статья 3: Основания для отказа · Пункт 3»?

Options:
A. Добавлено новое основание для отказа: Основанием для отказа является непредставление обязательных документов в установленный срок.
B. Основания для отказа остались без изменений.
C. Изменение касается только сроков оказания услуги.

Correct answer:
Добавлено новое основание для отказа: Основанием для отказа является непредставление обязательных документов в установленный срок.

Explanation/source:
Проверяет понимание изменения: Добавлено новое основание для отказа: Основанием для отказа является непредставление обязательных документов в установленный срок. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=refusal, entities=refusal_change.

Scores:
- relevance: 5
- correctness: 5
- unambiguous answer: 5
- distractor quality: 4
- no editorial noise: 5
- explanation/source: 5
- usefulness: 5
- overall: 4.8571

What is good:
- question is aligned with refusal-ground semantics
- answer preserves the non-submission condition
- source reference is clear

What is weak:
- distractors are broad and easy

Interpretation:
Checks the new refusal ground without changing its legal condition.

### Good example: pair_09_mixed_significant_and_editorial_q01

Expected topic:
- новый срок подготовки справки

Question:
Какое изменение по срокам должен учитывать сотрудник в разделе «Статья 2: Срок и проверка · Пункт 1»?

Options:
A. Срок сокращён: было 5 рабочих дней, стало 4 рабочих дня.
B. Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о невозможности подготовки справки при отсутствии обязательных сведений.
C. Добавлен новый процедурный шаг: Справочная информация о статусе запроса доступна в локальной системе учета.

Correct answer:
Срок сокращён: было 5 рабочих дней, стало 4 рабочих дня.

Explanation/source:
Проверяет понимание изменения: Срок сокращён: было 5 рабочих дней, стало 4 рабочих дня. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=deadline, entities=deadline_new,deadline_old, critical_keywords.

Scores:
- relevance: 5
- correctness: 5
- unambiguous answer: 5
- distractor quality: 3
- no editorial noise: 5
- explanation/source: 5
- usefulness: 5
- overall: 4.7143

What is good:
- covers one of the two critical expected quiz topics
- answer includes old and new values
- source points to the deadline fragment

What is weak:
- distractors are other true changes, not realistic deadline alternatives

Interpretation:
Good deadline question in a mixed-change pair.

### Weak/problematic example: pair_09_mixed_significant_and_editorial_q04

Expected topic:
- no expected quiz-worthy topic covered

Question:
Какое изменение по срокам должен учитывать сотрудник в разделе «Статья 2: Срок и проверка · Пункт 2»?

Options:
A. Изменены требования по срокам.
B. Срок сокращён: было 5 рабочих дней, стало 4 рабочих дня.
C. Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о невозможности подготовки справки при отсутствии обязательных сведений.

Correct answer:
Изменены требования по срокам.

Explanation/source:
Проверяет понимание изменения: Изменены требования по срокам. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=deadline.

Scores:
- relevance: 1
- correctness: 1
- unambiguous answer: 2
- distractor quality: 2
- no editorial noise: 1
- explanation/source: 2
- usefulness: 1
- overall: 1.4286

What is good:
- source fragment is available for detecting the problem

What is weak:
- question is based on editorial/noise
- answer is unsupported by the source text
- another true deadline change appears as a distractor

Interpretation:
Editorial wording replacement is incorrectly converted into a critical deadline question.

### Weak/problematic example: pair_05_editorial_change_q01

Expected topic:
- no expected quiz-worthy topic covered

Question:
Какое изменение в перечне документов нужно учитывать в разделе «Статья 2: Первичная проверка · Пункт 1»?

Options:
A. Изменены требования к перечню документов.
B. Перечень документов остался прежним.
C. Изменение касается только сроков предоставления услуги.

Correct answer:
Изменены требования к перечню документов.

Explanation/source:
Проверяет понимание изменения: Изменены требования к перечню документов. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=document.

Scores:
- relevance: 1
- correctness: 1
- unambiguous answer: 2
- distractor quality: 3
- no editorial noise: 1
- explanation/source: 2
- usefulness: 1
- overall: 1.5714

What is good:
- question remains traceable to the changed fragment

What is weak:
- no quiz should be generated for this editorial-only change
- question invents a document-list requirement
- answer does not follow from the new version

Interpretation:
Weak case: an editorial verb replacement is over-prioritized upstream and becomes a false document-list question.

### Weak/problematic example: pair_06_procedure_change_q01

Expected topic:
- no expected quiz-worthy topic covered

Question:
Какое изменение в перечне документов нужно учитывать в разделе «Статья 2: Способы подачи · Пункт 1»?

Options:
A. Изменены требования к перечню документов.
B. Перечень документов остался прежним.
C. Изменение касается только сроков предоставления услуги.

Correct answer:
Изменены требования к перечню документов.

Explanation/source:
Проверяет понимание изменения: Изменены требования к перечню документов. Причина значимости: Изменение затрагивает ключевые условия применения документа, обязанности, сроки или основания отказа. Сработали правила: change_type=document.

Scores:
- relevance: 3
- correctness: 2
- unambiguous answer: 2
- distractor quality: 3
- no editorial noise: 5
- explanation/source: 3
- usefulness: 2
- overall: 2.8571

What is good:
- question is attached to the changed source fragment

What is weak:
- correct answer is generic and does not mention the electronic form
- semantic template is wrong for the procedure change
- employee cannot learn the new submission channel from the answer

Interpretation:
The source is the real procedure change, but the generated question frames it as a document-list change and misses the electronic-form topic.
