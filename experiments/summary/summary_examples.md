# Summary evaluation examples

Examples are selected from the primary pipeline-mode evaluation.

## Good examples

### Good example: pair_01_deadline_change

Expected topics:
- срок рассмотрения заявления сокращен с 10 до 7 рабочих дней

Generated summary:

Ключевые значимые изменения
Ключевое изменение: Срок сокращён: было 10 рабочих дней, стало 7 рабочих дней. Изменено фрагментов: 1. Без изменений: 9. Критичных изменений: 1.
Highlights:
1. [critical/deadline] Срок сокращён: было 10 рабочих дней, стало 7 рабочих дней.

Why it is good:
- Covers the expected topic without adding unsupported legal consequences.
- Uses concise human-readable wording and keeps old/new value traceability through highlights.
- Suitable as an intermediate artifact before quiz generation.

Scores:
- completeness: 5
- accuracy: 5
- no_hallucinations: 5
- clarity: 5
- usefulness: 5
- source_alignment: 5
- average: 5.00

### Good example: pair_02_added_obligation

Expected topics:
- добавлена обязанность уведомить заявителя о результате рассмотрения обращения

Generated summary:

Ключевые значимые изменения
Ключевое изменение: Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений. Добавлено фрагментов: 1. Без изменений: 10. Критичных изменений: 1.
Highlights:
1. [critical/obligation] Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений.

Why it is good:
- Covers the expected topic without adding unsupported legal consequences.
- Uses concise human-readable wording and keeps old/new value traceability through highlights.
- Suitable as an intermediate artifact before quiz generation.

Scores:
- completeness: 5
- accuracy: 5
- no_hallucinations: 5
- clarity: 5
- usefulness: 5
- source_alignment: 5
- average: 5.00

### Good example: pair_04_refusal_ground_change

Expected topics:
- добавлено новое основание отказа при непредставлении обязательных документов в установленный срок

Generated summary:

Ключевые значимые изменения
Ключевое изменение: Добавлено новое основание для отказа: Основанием для отказа является непредставление обязательных документов в установленный срок. Добавлено фрагментов: 1. Без изменений: 9. Критичных изменений: 1.
Highlights:
1. [critical/refusal] Добавлено новое основание для отказа: Основанием для отказа является непредставление обязательных документов в установленный срок.

Why it is good:
- Covers the expected topic without adding unsupported legal consequences.
- Uses concise human-readable wording and keeps old/new value traceability through highlights.
- Suitable as an intermediate artifact before quiz generation.

Scores:
- completeness: 5
- accuracy: 5
- no_hallucinations: 5
- clarity: 5
- usefulness: 5
- source_alignment: 5
- average: 5.00

### Good example: pair_08_reordered_structure

Expected topics:
- none

Generated summary:

Изменения не обнаружены
Изменений между выбранными версиями не обнаружено. Без изменений: 10.

Why it is good:
- Covers the expected topic without adding unsupported legal consequences.
- Uses concise human-readable wording and keeps old/new value traceability through highlights.
- Suitable as an intermediate artifact before quiz generation.

Scores:
- completeness: 5
- accuracy: 5
- no_hallucinations: 5
- clarity: 5
- usefulness: 5
- source_alignment: 5
- average: 5.00

## Weak / problematic examples

### Weak example: pair_05_editorial_change

Expected topics:
- none

Generated summary:

Ключевые значимые изменения
Ключевое изменение: Изменены требования к перечню документов. Изменено фрагментов: 1. Без изменений: 9. Критичных изменений: 1.
Highlights:
1. [critical/document] Изменены требования к перечню документов.

What works:
- The output remains readable and uses the same production summary artifact as the MVP pipeline.

What is problematic:
- Editorial-only wording change is presented as a critical document-list requirement change.
- Editorial wording change is over-prioritized as critical.

How to interpret:
- The error is mainly bounded by upstream comparison/significance signals; the summary layer surfaces those signals instead of independently correcting them.

Scores:
- completeness: 2
- accuracy: 2
- no_hallucinations: 2
- clarity: 3
- usefulness: 1
- source_alignment: 2
- average: 2.00

### Weak example: pair_06_procedure_change

Expected topics:
- добавлена возможность подачи заявления через электронную форму во внутреннем портале

Generated summary:

Ключевые значимые изменения
Ключевое изменение: Изменены требования к перечню документов. Изменено фрагментов: 1. Без изменений: 9. Критичных изменений: 1.
Highlights:
1. [critical/document] Изменены требования к перечню документов.

What works:
- The output remains readable and uses the same production summary artifact as the MVP pipeline.

What is problematic:
- Procedure change is summarized as a document-list requirement change.

How to interpret:
- The error is mainly bounded by upstream comparison/significance signals; the summary layer surfaces those signals instead of independently correcting them.

Scores:
- completeness: 1
- accuracy: 2
- no_hallucinations: 3
- clarity: 3
- usefulness: 2
- source_alignment: 2
- average: 2.17

### Weak example: pair_09_mixed_significant_and_editorial

Expected topics:
- срок подготовки справки сокращен с 5 до 4 рабочих дней
- добавлена обязанность уведомления при невозможности подготовки справки

Generated summary:

Ключевые значимые изменения
Выявлено 4 значимых изменений. Основные темы: сроки и обязанности. Добавлено фрагментов: 2. Изменено фрагментов: 2. Без изменений: 8. Критичных изменений: 3. Важных изменений: 1.
Highlights:
1. [critical/deadline] Срок сокращён: было 5 рабочих дней, стало 4 рабочих дня.
2. [critical/deadline] Изменены требования по срокам.
3. [critical/obligation] Добавлена новая обязанность: Сотрудник обязан уведомить заявителя о невозможности подготовки справки при отсутствии обязательных сведений.
4. [important/procedure] Добавлен новый процедурный шаг: Справочная информация о статусе запроса доступна в локальной системе учета.

What works:
- The output remains readable and uses the same production summary artifact as the MVP pipeline.

What is problematic:
- Editorial wording change is incorrectly summarized as another deadline-related critical change.
- Informational status notice is over-framed as an important procedural step.
- Editorial wording change receives a critical deadline highlight.
- Informational/noise item is counted as important in the brief.

How to interpret:
- The error is mainly bounded by upstream comparison/significance signals; the summary layer surfaces those signals instead of independently correcting them.

Scores:
- completeness: 5
- accuracy: 3
- no_hallucinations: 3
- clarity: 4
- usefulness: 3
- source_alignment: 3
- average: 3.50
