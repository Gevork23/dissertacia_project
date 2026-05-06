# Diff evaluation error examples

### Example: pair_02_added_obligation, method=plain_text_diff

**Scenario:** plain text diff false positive caused by renumbering

**Expected:**

Only the new notification obligation is a meaningful change.

**Predicted:**

modified: OLD='3. Проект результата передается руководителю подразделения для согласования.' NEW='4. Проект результата передается руководителю подразделения для согласования.'

**Error type:**

FP

**Why it happened:**

The baseline compares full text lines with numeric markers. After inserting a new point, the old point number changes, so an unchanged provision is emitted as modified noise.

### Example: pair_03_document_list_change, method=paragraph_diff

**Scenario:** paragraph diff misses an added lettered subpoint

**Expected:**

chg_001 [added/critical]: OLD='' NEW='г) копию документа, подтверждающего полномочия представителя, если заявление подает представитель.'

**Predicted:**

modified: OLD='Статья 2. Обязательные документы 1. Для рассмотрения заявления заявитель предоставляет: а) заявление по установленной форме; б) копию документа, подтверждающего основание обращения' NEW='Статья 2. Обязательные документы 1. Для рассмотрения заявления заявитель предоставляет: а) заявление по установленной форме; б) копию документа, подтверждающего основание обращения'

**Error type:**

FN / FP

**Why it happened:**

The paragraph baseline treats the whole Article 2 block as one paragraph-level modification. It does not isolate the added lettered subpoint as an added change.

### Example: pair_08_reordered_structure, method=structural_chunk_diff

**Scenario:** structural diff moved-case limitation

**Expected:**

chg_001 [moved/editorial]: OLD='Контроль полноты сведений проводится до регистрации обращения.' NEW='Контроль полноты сведений проводится до регистрации обращения.'

**Predicted:**

No change emitted by production structural comparison.

**Error type:**

diagnostic raw FN

**Why it happened:**

The current MVP comparison deliberately treats exact-text relocation as unchanged and does not materialize moved items. In strict meaningful metrics this moved case is editorial noise, but all-change diagnostics expose it as a moved-detection limit.

### Example: pair_01_deadline_change, method=structural_chunk_diff

**Scenario:** structural diff cleanly detects a deadline change

**Expected:**

chg_001 [modified/critical]: OLD='Срок рассмотрения заявления составляет 10 рабочих дней со дня его регистрации.' NEW='Срок рассмотрения заявления составляет 7 рабочих дней со дня его регистрации.'

**Predicted:**

modified: OLD='Срок рассмотрения заявления составляет 10 рабочих дней со дня его регистрации.' NEW='Срок рассмотрения заявления составляет 7 рабочих дней со дня его регистрации.'

**Error type:**

TP / clean detection

**Why it happened:**

The old and new chunks share the same path_key, so production comparison emits one modified chunk with no extra changed lines.

### Example: pair_05_editorial_change, method=structural_chunk_diff

**Scenario:** editorial change counted as strict noise

**Expected:**

No meaningful expected change under strict usefulness metrics.

**Predicted:**

modified: OLD='Сотрудник осуществляет проверку документов на предмет комплектности.' NEW='Сотрудник выполняет проверку документов на предмет комплектности.'

**Error type:**

editorial noise / FP

**Why it happened:**

The diff layer correctly detects a wording change, but the annotation marks it as editorial. For strict comparison usefulness metrics it is counted as noise and reported separately as editorial_noise.

### Example: pair_10_weakly_structured_document, method=structural_chunk_diff

**Scenario:** weakly structured document uses fallback-block comparison

**Expected:**

chg_001 [modified/critical]: OLD='Обращение рассматривается ответственным подразделением в течение 5 рабочих дней. По итогам рассмотрения готовится ответ с описанием результата и дальнейших действий.' NEW='Обращение рассматривается ответственным подразделением в течение 3 рабочих дней. По итогам рассмотрения готовится ответ с описанием результата и дальнейших действий.'

**Predicted:**

modified: OLD='Рассмотрение обращения Обращение рассматривается ответственным подразделением в течение 5 рабочих дней. По итогам рассмотрения готовится ответ с описанием результата и дальнейших д' NEW='Рассмотрение обращения Обращение рассматривается ответственным подразделением в течение 3 рабочих дней. По итогам рассмотрения готовится ответ с описанием результата и дальнейших д'

**Error type:**

chunking dependency observation

**Why it happened:**

The method still detects the deadline change, but the changed unit is a fallback block rather than a fine-grained point. This illustrates how chunk granularity bounds comparison clarity.
