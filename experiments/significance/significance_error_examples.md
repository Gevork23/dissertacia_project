# Significance evaluation error examples

Primary mode: oracle-change evaluation over manually annotated change spans. The classifier receives old/new change text and runs the production `enrich_change()` wrapper without gold semantic labels.

## Observed oracle-change errors

### Example: pair_03_document_list_change, change chg_001

**Scenario:** observed misclassification

**Expected importance:**

critical

**Predicted importance:**

important

**Predicted semantic type:**

unclassified

**Triggered rules:**

important_keywords

**Change text:**

OLD: -

NEW: г) копию документа, подтверждающего полномочия представителя, если заявление подает представитель.

**Why it happened:**

The text contains document-related wording, but the current document inference pattern is narrower than the annotation scenario and the important keyword path wins.

**Interpretation:**

The change remains in the important/critical positive class, so it is not lost for downstream prioritization, but exact severity is understated.

### Example: pair_05_editorial_change, change chg_001

**Scenario:** observed misclassification

**Expected importance:**

editorial

**Predicted importance:**

important

**Predicted semantic type:**

unclassified

**Triggered rules:**

fallback_manual_review

**Change text:**

OLD: Сотрудник осуществляет проверку документов на предмет комплектности.

NEW: Сотрудник выполняет проверку документов на предмет комплектности.

**Why it happened:**

The wording replacement is semantically soft, but the text-only rule path did not prove normalized equivalence and fell back to manual-review important.

**Interpretation:**

This is an editorial false positive: downstream summary/quiz may over-prioritize a stylistic change unless comparison provides an editorial_change signal or a human reviewer confirms it.

### Example: pair_09_mixed_significant_and_editorial, change chg_002

**Scenario:** observed misclassification

**Expected importance:**

editorial

**Predicted importance:**

important

**Predicted semantic type:**

unclassified

**Triggered rules:**

fallback_manual_review

**Change text:**

OLD: Сотрудник осуществляет проверку сведений по внутренним источникам.

NEW: Сотрудник выполняет проверку сведений по внутренним источникам.

**Why it happened:**

The wording replacement is semantically soft, but the text-only rule path did not prove normalized equivalence and fell back to manual-review important.

**Interpretation:**

This is an editorial false positive: downstream summary/quiz may over-prioritize a stylistic change unless comparison provides an editorial_change signal or a human reviewer confirms it.

### Example: pair_09_mixed_significant_and_editorial, change chg_004

**Scenario:** observed misclassification

**Expected importance:**

informational

**Predicted importance:**

important

**Predicted semantic type:**

unclassified

**Triggered rules:**

fallback_manual_review

**Change text:**

OLD: -

NEW: Справочная информация о статусе запроса доступна в локальной системе учета.

**Why it happened:**

The informational addition does not match the current contact/reference keyword set strongly enough, so the fallback rule marks it important.

**Interpretation:**

The baseline is conservative for unfamiliar informational wording: it prefers manual-review important over missing a possibly relevant change.

## Correct high-priority examples

### Example: pair_01_deadline_change, change chg_001

**Scenario:** correct deadline classification

**Expected importance:**

critical

**Predicted importance:**

critical

**Predicted semantic type:**

deadline

**Triggered rules:**

change_type=deadline;entities=deadline_new,deadline_old;critical_keywords

**Change text:**

OLD: Срок рассмотрения заявления составляет 10 рабочих дней со дня его регистрации.

NEW: Срок рассмотрения заявления составляет 7 рабочих дней со дня его регистрации.

**Why it happened:**

The text contains explicit deadline wording and old/new numeric day values. The production wrapper infers `deadline`, extracts deadline entities and assigns `critical`.

**Interpretation:**

Deadline changes are one of the strongest categories for the current rule-based baseline.

### Example: pair_02_added_obligation, change chg_001

**Scenario:** correct obligation classification

**Expected importance:**

critical

**Predicted importance:**

critical

**Predicted semantic type:**

obligation

**Triggered rules:**

change_type=obligation;entities=staff_action;critical_keywords

**Change text:**

OLD: -

NEW: Сотрудник обязан уведомить заявителя о результате рассмотрения обращения через локальную систему уведомлений.

**Why it happened:**

The added text contains an explicit obligation verb. The wrapper infers `obligation`, extracts a staff-action entity and assigns `critical`.

**Interpretation:**

The classifier correctly treats new mandatory employee actions as high-priority changes.

### Example: pair_07_responsibility_change, change chg_001

**Scenario:** correct responsibility classification

**Expected importance:**

critical

**Predicted importance:**

critical

**Predicted semantic type:**

responsibility

**Triggered rules:**

change_type=responsibility;entities=responsibility_change;critical_keywords

**Change text:**

OLD: -

NEW: За нарушение срока обработки заявления сотрудник несет ответственность в соответствии с внутренним регламентом подразделения.

**Why it happened:**

The added text contains responsibility and deadline signals. The wrapper infers `responsibility` and assigns `critical`.

**Interpretation:**

Responsibility changes are captured reliably in this corpus.

## Error category not observed: expected important/critical -> predicted editorial

No high-priority expected change was downgraded to `editorial` in the oracle-change experiment. This supports high recall for the important/critical positive class on the current corpus, but the corpus is too small to treat the absence of this error as a universal guarantee.

## Error category not applicable: expected medium

The current project labels do not include `medium`; the closest realized lower-priority substantive category is `informational`. Therefore `expected medium -> predicted important` cannot be reported on this corpus.
