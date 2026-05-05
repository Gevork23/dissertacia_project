# Significance Assessment Method

## 1. Назначение документа

Документ формализует реализованный в проекте слой оценки значимости изменений нормативно-правовых и внутренних регламентных документов. Цель документа — описать stage `P` из гибридного метода `M = <E, N, S, C, P, G, R>` как защищаемый baseline-компонент, а не как набор неформальных эвристик.

Фаза 10 не добавляет новый классификатор, не вводит ML/LLM-оценку значимости, не меняет модели БД и не запускает экспериментальную оценку качества. Документ фиксирует фактическое состояние проекта после Фазы 9 на основе кода, моделей, тестов и документации.

Основные исходные файлы реализации:

- `backend/documents/services/importance.py` — rule-based классификатор importance/significance;
- `backend/documents/domain/change_enrichment.py` — извлечение текстов изменения, вывод semantic type, enrichment diff payload;
- `backend/documents/domain/diff.py` — источник materialized change candidates и structural/diff features;
- `backend/documents/domain/diff_summary.py` — использование significance при построении brief summary;
- `backend/documents/domain/diff_quiz.py` — использование significance при генерации quiz;
- `backend/documents/services/workflows.py` — materialization `VersionComparison`, `VersionChangeItem`, `Summary`, `GeneratedQuiz`;
- `backend/documents/models.py` — поля significance на `VersionChangeItem`.

## 2. Контекст задачи

После структурного разбиения документа и сравнения двух редакций система получает множество найденных изменений: добавленные, удалённые, изменённые и перемещённые фрагменты. На этом уровне diff отвечает только на вопрос: **что изменилось между версиями**.

Для практического сценария системы этого недостаточно. Сотруднику, руководителю или ответственному за обучение важно не только увидеть технические изменения текста, но и понять, какие изменения могут повлиять на:

- сроки выполнения действий;
- обязанности сотрудников или заявителей;
- перечень документов;
- основания отказа;
- условия предоставления услуги;
- порядок процедуры;
- ответственность;
- справочную или контактную информацию;
- необходимость ручной проверки неоднозначного изменения.

Поэтому поверх comparison-layer реализован deterministic/rule-based significance-layer, который преобразует технические diff items в приоритизированные элементы дальнейшего pipeline.

## 3. Роль significance-layer в гибридном методе

В гибридном методе проекта:

```text
M = <E, N, S, C, P, G, R>
```

слой significance соответствует этапу `P` — **Prioritization / Significance classification**.

Связь этапов:

```text
C(materialized structural diff)
    → P(significance classification / prioritization)
    → G(summary and quiz generation)
```

Этап `P` располагается после comparison, потому что он не извлекает текст и не ищет изменения самостоятельно. Его входом являются уже найденные diff candidates, дополненные структурным контекстом и предварительной классификацией типа изменения.

Этап `P` располагается перед generation, потому что summary и quiz должны работать не по произвольному списку diff items, а по приоритизированному множеству изменений, которые потенциально значимы для человека.

## 4. Почему одного diff недостаточно

Обычный diff фиксирует факт отличия строк, абзацев или структурных фрагментов. Для нормативных и регламентных документов это приводит к двум проблемам:

1. **Шум редакционных правок.** Изменение буквы `е/ё`, пунктуации, нумерации или расположения фрагмента может выглядеть как diff item, но не всегда меняет действия сотрудника.
2. **Разная практическая важность изменений.** Изменение срока, обязанности или основания отказа требует большего внимания, чем добавление справочного телефона или стилистическое уточнение.

Significance-layer переводит technical diff в user-oriented analysis:

| Уровень | Вопрос | Результат |
|---|---|---|
| Diff / comparison | Что изменилось? | Список added/removed/modified/moved фрагментов |
| Significance | Что из этого потенциально важно? | `semantic_type`, `significance_label`, score, rules, reason, manual-review flag |
| Summary / Quiz | Что нужно показать и проверить? | Prioritized highlights и вопросы по значимым изменениям |

Без significance summary мог бы быть перегружен техническими правками, а quiz мог бы проверять понимание редакционных изменений вместо содержательных требований.

## 5. Входные и выходные данные

### 5.1 Вход

Фактический вход significance-layer — change payload из comparison-layer. Он может поступать как:

- элементы `added`, `removed`, `modified`, `moved` из diff payload;
- материализуемые элементы `VersionChangeItem` при сохранении comparison;
- уже enriched payload, содержащий `semantic_type`, `significance_label` или nested `significance`.

Основные входные поля, которые использует `change_enrichment.py`:

| Группа | Поля / источник | Использование |
|---|---|---|
| Old/new text | `old_text`, `new_text`, `before_text`, `after_text`, `from_chunk.text`, `to_chunk.text` | Лексический анализ и построение `diff_text` |
| Diff operation | `added`, `removed`, `modified`, `moved` из `iter_ordered_change_entries` | Материализация и downstream ordering |
| Change classification | `change_classification.primary_type` из `diff.py` | Маппинг `deadline_change → deadline`, `service_procedure_change → procedure` и т.д. |
| Structural chunk metadata | `fragment_type`, `path_key`, `canonical_label`, `heading`, `section_path`, `chunk_index`, `text_hash` | Используется comparison-layer и summary titles; в significance score напрямую не добавляет boost |
| Existing semantic fields | `semantic_type`, `change_type`, `category`, `kind` | Если уже известны, используются до regex inference |
| Extracted entities | `extracted_entities` | Усиливают назначение category и explanation |

Важно: в текущей реализации significance-layer не запускает отдельный semantic parser по структуре документа. Structural context используется **косвенно**: comparison-layer формирует matched chunks, `change_classification`, `match_reason`, `similarity` и payload с chunk metadata; significance-layer затем обогащает эти changes.

### 5.2 Выход

Выход significance-layer — enriched change payload и материализованные поля на `VersionChangeItem`.

Фактические поля:

| Поле | Где хранится | Смысл |
|---|---|---|
| `semantic_type` | `VersionChangeItem.semantic_type`; enriched payload | Содержательный тип изменения: `deadline`, `document`, `obligation`, ... |
| `extracted_entities` | `VersionChangeItem.extracted_entities`; enriched payload | Baseline-сущности, извлечённые из изменения |
| `significance_label` | `VersionChangeItem.significance_label`; enriched payload | Категория значимости |
| `significance_score` | `VersionChangeItem.significance_score`; enriched payload | Confidence/priority score `0.0..1.0` |
| `significance_reason` | `VersionChangeItem.significance_reason`; enriched payload | Человекочитаемое объяснение |
| `significance_rules` | `VersionChangeItem.significance_rules`; enriched payload | Список сработавших правил |
| `requires_manual_review` | `VersionChangeItem.requires_manual_review`; enriched payload | Флаг неоднозначной автоматической оценки |
| `importance_*` aliases | enriched payload | Backward-compatible алиасы: `importance_label`, `importance_confidence`, `importance_explanation`, `importance_triggered_rules` |

Отдельной модели `ChangeSignificance`, `SignificanceAssessment` или `ChangePriority` в проекте нет. Significance материализуется непосредственно на `VersionChangeItem`.

## 6. Категории значимости

Фактически реализованные категории отличаются от раннего планового набора `critical / important / medium / minor / editorial`. В текущем проекте поддерживаются:

```text
critical
important
informational
editorial
not_evaluated
```

В `backend/documents/services/importance.py` основной набор классификатора — `critical`, `important`, `informational`, `editorial`. Значение `not_evaluated` присутствует как техническое default-состояние модели `VersionChangeItem` и как допустимое значение в `change_enrichment.py`, но обычный вызов `classify_change_importance()` возвращает одну из четырёх основных категорий.

Приоритет категорий в коде:

| Category | Priority |
|---|---:|
| `critical` | 4 |
| `important` | 3 |
| `informational` | 2 |
| `editorial` | 1 |
| `not_evaluated` | 0 |

Категории `medium` и `minor` в модели и сервисе отсутствуют. Их нельзя описывать как реализованные. В текущей версии роль менее значимых, но содержательных изменений частично выполняет `informational`, а технически неоценённые изменения представлены `not_evaluated`.

## 7. Типы изменений

В проекте нужно различать два уровня типов изменений.

Первый уровень — **операция diff** в `VersionChangeItem.ChangeType`:

```text
added
removed
modified
moved
```

Второй уровень — **semantic type** в `VersionChangeItem.SemanticType` и `change_enrichment.KNOWN_CHANGE_TYPES`:

```text
deadline
document
obligation
procedure
refusal
condition
responsibility
informational
editorial
structure
unclassified
```

Дополнительно в `domain/change_types.py` и `domain/change_classification.py` используются имена предварительной классификации stage `C`:

```text
deadline_change
document_change
obligation_change
service_procedure_change
refusal_change
editorial_change
structural_change
```

`change_enrichment.infer_change_type()` маппит эти значения в semantic types:

| Classification type from C | Semantic type in P |
|---|---|
| `deadline_change` | `deadline` |
| `document_change` | `document` |
| `obligation_change` | `obligation` |
| `service_procedure_change` | `procedure` |
| `refusal_change` | `refusal` |
| `editorial_change` | `editorial` |
| `structural_change` | `structure` |

## 8. Признаки значимости

### 8.1 Лексические признаки

Лексические правила реализованы через regex patterns в `backend/documents/services/importance.py` и в inference-логике `backend/documents/domain/change_enrichment.py`.

#### Critical patterns

`critical` назначается или усиливается при признаках сроков, отказов, обязанностей, ответственности и некоторых обязательных документов:

```text
срок
рабоч* дн
основан* для отказ
отказ*
обязан*
обязател*
дисциплинарн*
материальн*
ответственност*
снилс
доверенност*
```

#### Important patterns

`important` назначается или усиливается при признаках процедурного порядка, взаимодействия и условий:

```text
предварительн* запис
личн* кабинет
представител*
уведомлен*
консультирован*
окн* обслуживан
месту пребывания
выдается / выдаётся
проверка заявлен
профильн* отдел
```

#### Informational patterns

`informational` назначается или усиливается при справочных и контактных изменениях:

```text
телефон*
горяч* лини
официальн* сайт
информационн* стенд
пример* заполнен
справочн* номер
пояснен*
8-800
```

#### Editorial patterns

Для `editorial` нет отдельного словаря смысловых терминов. Основные признаки:

- `change_type`/`semantic_type` равен `editorial` или `structure`;
- entity type равен `editorial_change` или `structure_change`;
- canonical old/new text совпадает после удаления пунктуации, кавычек, тире, скобок, символа `№` и нормализации пробелов;
- предварительный comparison classifier может отнести фрагмент к editorial при высокой лексической близости и отсутствии сильных доменных сигналов.

### 8.2 Структурные признаки

Structural features возникают в stage `S` и `C`, а в significance-layer используются преимущественно косвенно.

| Structural feature | Где формируется | Как влияет на significance pipeline |
|---|---|---|
| `fragment_type` | `Chunk` / `diff.serialize_chunk()` | Участвует в matching и change classification; сохраняется в payload |
| `path_key` | structural chunking | Используется comparison-layer для matching и `match_reason`; structural change может быть classified как `structure` |
| `canonical_label` | structural chunking | Используется comparison-layer как structural anchor |
| `section_path` | structural chunking | Используется matching, title generation и explanation context |
| `heading` | structural chunking | Используется matching, title generation, prompt generation |
| `chunk_index` | structural chunking | Используется ordering и index proximity в diff |
| `text_hash` | structural chunking | Используется comparison-layer для exact unchanged matching |
| `similarity` | comparison-layer | Используется quiz fallback и change classification, не как прямой score boost importance.py |
| `match_reason` | comparison-layer | Сохраняется и выводится в summary/quiz source metadata |

В текущем implementation `importance.py` не добавляет отдельный structural boost вида `section/article/paragraph → +score`. Поэтому структурные признаки нужно описывать как часть входного контекста и materialized traceability, а не как самостоятельную весовую формулу significance score.

### 8.3 Признаки типа изменения

`classify_change_importance()` использует `change_type` как самый сильный сигнал. Если semantic type уже определён, он даёт score `100` соответствующей category.

| Semantic type | Category signal |
|---|---|
| `deadline` | `critical` |
| `document` | `critical` |
| `refusal` | `critical` |
| `obligation` | `critical` |
| `responsibility` | `critical` |
| `procedure` | `important` |
| `condition` | `important` |
| `informational` | `informational` |
| `editorial` | `editorial` |
| `structure` | `editorial` |

Это означает, что semantic type является главным baseline-признаком. Лексика и entities используются как дополнительные объяснимые сигналы или fallback, если тип не задан.

### 8.4 Признаки влияния на сотрудника

В коде нет отдельного поля `employee_impact`. Влияние на сотрудника реализовано не как самостоятельная модель, а как интерпретация rule-based semantic signals.

| Impact dimension | Реализация в коде | Интерпретация |
|---|---|---|
| Сроки | `deadline`, `deadline_old`, `deadline_new`, critical patterns | Меняются временные ожидания и контроль исполнения |
| Обязанности | `obligation`, `staff_action`, обязан/обязател | Меняются действия сотрудника или заявителя |
| Документы | `document`, `required_documents_old/new`, паспорт/СНИЛС/доверенность | Меняется набор проверяемых или принимаемых документов |
| Основания отказа | `refusal`, `refusal_change`, отказ | Меняются основания принятия решения |
| Ответственность | `responsibility`, `responsibility_change`, дисциплинарная/материальная ответственность | Меняются риски и accountability |
| Процедура | `procedure`, `procedure_change`, запись/кабинет/уведомление | Меняется порядок действий |
| Условия | `condition`, `condition_change`, место пребывания/представитель | Меняются условия применимости нормы |
| Справка | `informational`, `info_change`, телефон/сайт/стенд | Обновляется справочная информация |
| Редакция | `editorial`, normalized equality | Не выявлено влияния на действия или требования |

## 9. Таблица категорий значимости

| Category | Meaning | Typical triggers | Example | Downstream behavior |
|---|---|---|---|---|
| `critical` | Потенциально критичное изменение требований, сроков, документов, отказов, обязанностей или ответственности | `change_type` in `deadline/document/refusal/obligation/responsibility`; critical entities; critical keywords | «Срок рассмотрения заявления изменён с 10 до 5 рабочих дней» | Попадает в начало priority order, включается в summary, является главным кандидатом для quiz |
| `important` | Важное содержательное изменение процедуры или условий, но не из наиболее критичных доменных групп | `change_type` in `procedure/condition`; important entities; important keywords; fallback manual review | «Приём заявлений осуществляется по предварительной записи через портал» | Попадает в summary и quiz после `critical`; при fallback может требовать ручной проверки |
| `informational` | Справочное или контактное изменение, полезное для сотрудника, но обычно не меняющее обязанность или срок | `informational` type, `info_change`, телефон, сайт, стенд, 8-800 | «Добавлен телефон горячей линии 8-800...» | Может попасть в summary и quiz после `critical/important`; имеет меньший приоритет |
| `editorial` | Редакционная, техническая или структурная правка без выявленного смыслового изменения | `editorial/structure` type, `editorial_change`, normalized old/new equality | «Прием» заменён на «Приём» | Обычно исключается из quiz; в summary используется только как editorial fallback |
| `not_evaluated` | Техническое состояние до оценки или допустимый label для совместимости payload | Default model value или payload без оценки | Change item создан, но classification ещё не применена | Может учитываться как primary label в summary/quiz только как compatibility fallback; штатный classifier его не возвращает |

## 10. Таблица типов изменений

| Change type | Description | Typical markers | Potential importance | Example |
|---|---|---|---|---|
| `deadline` | Изменение сроков или временных ограничений | `срок`, `рабочих дней`, `deadline_old`, `deadline_new` | `critical` | «Срок рассмотрения заявления составляет 7 рабочих дней» |
| `document` | Изменение перечня или состава документов | `документ`, `заявление`, `паспорт`, `СНИЛС`, `доверенность`, `required_documents_old/new` | `critical` | «Заявитель представляет паспорт и СНИЛС» |
| `obligation` | Изменение обязанности сотрудника, заявителя или органа | `обязан`, `обязател`, `staff_action` | `critical` | «Сотрудник обязан уведомить заявителя» |
| `procedure` | Изменение порядка действий или взаимодействия | `предварительная запись`, `личный кабинет`, `уведомление`, `консультирование`, `procedure_change` | `important` | «Приём осуществляется по предварительной записи» |
| `refusal` | Изменение оснований отказа | `отказ`, `основание для отказа`, `refusal_change` | `critical` | «Основанием для отказа является непредставление СНИЛС» |
| `condition` | Изменение условий применимости нормы или услуги | `месту пребывания`, `законный представитель`, `condition_change` | `important` | «Услуга предоставляется заявителям старше 18 лет» |
| `responsibility` | Изменение ответственности или санкционных последствий | `ответственность`, `дисциплинарная`, `материальная`, `responsibility_change` | `critical` | «Сотрудник несёт дисциплинарную ответственность» |
| `informational` | Справочная или контактная информация | `телефон`, `горячая линия`, `официальный сайт`, `информационный стенд`, `info_change` | `informational` | «Добавлен справочный номер горячей линии» |
| `editorial` | Редакционное изменение текста | normalized old/new equality, `editorial_change` | `editorial` | «Прием» → «Приём» |
| `structure` | Структурная правка или перемещение без смыслового изменения | `structural_change`, изменение `path_key`, `canonical_label`, `section_path`, `heading` | `editorial` | Фрагмент перенесён без изменения текста |
| `unclassified` | Неоднозначное изменение без уверенного semantic type | Нет сработавших type rules | fallback `important` + manual review | «Специалист выполняет действие по согласованному маршруту» |

## 11. Таблица правил классификации

Фактическая логика — это не суммирующая модель весов, а rule cascade с максимумом score по category. Функция `hit(label, score, reason)` сохраняет максимальный score для label и список причин. Итоговый label выбирается по `(score, LABEL_PRIORITY)`.

| Rule ID | Rule description | Input signals | Output category | Score / confidence | Explanation |
|---|---|---|---|---:|---|
| R1 | Critical semantic type | `change_type` in `deadline`, `document`, `refusal`, `obligation`, `responsibility` | `critical` | 1.00 | Самый сильный сигнал: изменение относится к ключевым требованиям |
| R2 | Important semantic type | `change_type` in `procedure`, `condition` | `important` | 1.00 | Изменение влияет на порядок работы или условия взаимодействия |
| R3 | Informational semantic type | `change_type=informational` | `informational` | 1.00 | Изменение относится к справочной информации |
| R4 | Editorial/structure semantic type | `change_type` in `editorial`, `structure` | `editorial` | 1.00 | Изменение похоже на редакционное или структурное |
| R5 | Critical entity evidence | `deadline_old/new`, `required_documents_old/new`, `refusal_change`, `staff_action`, `responsibility_change` | `critical` | 0.95 | В extracted entities найдены критичные domain signals |
| R6 | Important entity evidence | `procedure_change`, `condition_change` | `important` | 0.95 | Entity layer указывает на процедуру или условия |
| R7 | Informational entity evidence | `info_change` | `informational` | 0.95 | Entity layer указывает на справочное изменение |
| R8 | Editorial entity evidence | `editorial_change`, `structure_change` | `editorial` | 0.95 | Entity layer указывает на редакционную/структурную правку |
| R9 | Critical keywords | Regex по срокам, отказам, обязанностям, ответственности, СНИЛС, доверенности | `critical` | 0.90 | Лексические маркеры указывают на практическую значимость |
| R10 | Important keywords | Regex по предварительной записи, личному кабинету, уведомлению, консультации, месту пребывания и т.д. | `important` | 0.90 | Лексические маркеры указывают на изменение порядка или условий |
| R11 | Informational keywords | Regex по телефону, горячей линии, официальному сайту, стенду, 8-800 и т.д. | `informational` | 0.90 | Добавлена или изменена справочная информация |
| R12 | Normalized text equality | Canonical old/new text equal after punctuation/spacing normalization | `editorial` | 0.85 | Смысловое отличие не обнаружено на baseline-уровне |
| R13 | Contact/reference addition | New text longer than old and informational markers appear only in new text | `informational` | 0.80 | Похоже на добавление контакта или справочного блока |
| R14 | Fallback manual review | Нет ни одного score по labels | `important` + `requires_manual_review=True` | 0.51 | Неоднозначное изменение не отбрасывается, но требует human-in-the-loop |

## 12. Общая логика алгоритма

Алгоритм работает на уровне одного change item и затем применяется ко всем changes в diff payload.

Общий pipeline:

1. Получить `old_text`, `new_text`, `diff_text` из change payload.
2. Определить semantic type:
   - использовать уже заданный `semantic_type`/`change_type`/`category`/`kind`, если он известен;
   - иначе использовать `change_classification.primary_type` из comparison-layer;
   - иначе применить regex inference по тексту.
3. Сформировать baseline `extracted_entities`, если они отсутствуют.
4. Вызвать `classify_change_importance()`.
5. Получить label, confidence, triggered rules, explanation и manual-review flag.
6. Записать результат в enriched payload.
7. При materialization сохранить результат в `VersionChangeItem`.
8. Использовать результат для summary, quiz и demo/API.

Особенность текущей реализации: scores не суммируются. Например, если change type даёт `critical=100`, а keywords дают `important=90`, победит `critical`. При равном score применяется `LABEL_PRIORITY`.

## 13. Editorial detection

Editorial detection реализован как conservative baseline, а не как полноценная семантическая проверка.

Основные механизмы:

1. **Direct semantic signal.** Если `change_type` равен `editorial` или `structure`, классификатор назначает `editorial` со score `1.00`.
2. **Entity signal.** Если среди entities есть `editorial_change` или `structure_change`, назначается `editorial` со score `0.95`.
3. **Canonical equality.** Если old/new text совпадают после lowercasing, замены `ё→е`, удаления пунктуации/кавычек/скобок/тире/символа `№` и нормализации пробелов, назначается `editorial` со score `0.85`.
4. **Comparison classifier.** На предыдущем этапе `domain/change_classification.py` может классифицировать modified pair как `editorial_change`, если тексты лексически близки, профиль извлечённых сущностей не изменился и нет сильных доменных сигналов.
5. **Structural movement.** `structural_change` маппится в semantic type `structure`, а затем в `editorial` category.

Downstream effect:

- `diff_summary.py` предпочитает non-editorial highlights;
- если все изменения editorial, summary получает `selection_scope="editorial_fallback"` и текст «значимых смысловых изменений не обнаружено»;
- `diff_quiz.py` исключает semantic types `editorial` и `structure` из обычных quiz candidates;
- если изменения только editorial и нет содержательного fallback, quiz не создаётся.

Ограничение: editorial detection может давать false positives и false negatives. Например, минимальное изменение формулировки может иметь юридический смысл, но baseline может счесть его редакционным; наоборот, стилистическая правка с доменным словом может быть завышена.

## 14. Materialization significance results

Materialization выполняется в `backend/documents/services/workflows.py` функцией `materialize_comparison()`.

Фактическая последовательность:

```text
build_comparison_payload()
    → build_version_diff()
    → enrich_compare_payload()
    → build_brief_summary()
    → VersionComparison.update_or_create()
    → comparison.change_items.all().delete()
    → VersionChangeItem.objects.create(... significance fields ...)
    → Summary.update_or_create(... highlights ...)
```

Significance хранится не в отдельной таблице, а в полях `VersionChangeItem`:

- `semantic_type`;
- `extracted_entities`;
- `significance_label`;
- `significance_score`;
- `significance_reason`;
- `significance_rules`;
- `requires_manual_review`.

Почему materialization важна:

1. **Воспроизводимость.** Для сохранённой пары версий можно увидеть, какие change items были признаны critical/important/editorial.
2. **Traceability.** `Summary.highlights` получает `source_change_item_id`, что связывает brief с конкретным `VersionChangeItem`.
3. **Quiz provenance.** `Question.source_change_item` связывает вопрос с исходным изменением.
4. **Explainability.** `significance_reason` и `significance_rules` позволяют объяснить, почему изменение попало в summary или quiz.
5. **Recalculation.** Повторный вызов `materialize_comparison()` пересоздаёт `change_items` для пары версий, потому что старые items удаляются перед новой материализацией. Уникальность пары версий обеспечивается `VersionComparison` constraint `uniq_version_comparison_pair`.

## 15. Использование significance в downstream pipeline

| Downstream слой | Как использует significance | Почему это важно |
|---|---|---|
| API compare | `VersionDiffSerializer` возвращает `significance`, `significance_label`, `significance_score`, `significance_reason`, `significance_rules`, `requires_manual_review`; summary содержит `by_significance` | API показывает не только diff, но и объяснимую оценку важности |
| Demo compare UI | `compare.html` показывает счётчики `Critical/Important/Informational/Editorial/Manual review`, labels, reasons и semantic type | Комиссии виден explainable bridge от diff к human-oriented результату |
| Summary / brief | `build_brief_summary()` сортирует изменения по priority, предпочитает non-editorial, включает `critical/important/informational/not_evaluated` в primary pool | Выжимка не перегружается шумовыми правками |
| Summary materialization | `Summary.text` и `Summary.highlights` сохраняются с `significance_label`, `significance_reason`, `requires_manual_review`, `source_change_item_id` | Позволяет проверить, почему highlight был выбран |
| Quiz generation | `build_quiz_from_summary()` берёт candidates с labels `critical/important/informational/not_evaluated`, исключает semantic types `editorial/structure` | Quiz проверяет содержательные изменения, а не пунктуацию |
| Saved quiz | `Question.source_change_item` связывает вопрос с materialized change item | Можно проследить происхождение вопроса |
| Quiz workflow | Empty quiz rejected через `EmptyQuizError`, если нет достаточно значимых изменений | Не создаётся бессодержательный тест по редакционным правкам |
| Future experiments | Materialized labels и source links могут быть сопоставлены с expected labels | Даёт базу для Фазы 16 без изменения production pipeline |

## 16. Псевдокод алгоритма

```text
Input:
    diff_payload with added/removed/modified/moved change entries

Output:
    enriched_diff_payload with significance fields
    materialized VersionChangeItem records

Algorithm enrich_compare_payload(diff_payload):
    for each change in ordered diff entries:
        old_text, new_text, diff_text = extract_change_texts(change)

        semantic_type = change.semantic_type or change.change_type
        if semantic_type is unknown:
            if change.change_classification.primary_type exists:
                semantic_type = map_comparison_type_to_semantic_type(primary_type)
            else:
                semantic_type = infer_change_type_by_regex(old_text, new_text, diff_text)

        extracted_entities = change.extracted_entities
        if extracted_entities is empty:
            extracted_entities = extract_entities_baseline(semantic_type, old_text, new_text)

        prediction = classify_change_importance(
            old_text=old_text,
            new_text=new_text,
            diff_text=diff_text,
            change_type=semantic_type,
            extracted_entities=extracted_entities,
        )

        change.semantic_type = semantic_type
        change.extracted_entities = extracted_entities
        change.significance_label = prediction.label
        change.significance_score = prediction.confidence
        change.significance_reason = prediction.explanation
        change.significance_rules = prediction.triggered_rules
        change.requires_manual_review = prediction.requires_manual_review

    update diff_payload.summary.by_significance
    update diff_payload.summary.manual_review_count
    return diff_payload

Algorithm classify_change_importance(change):
    initialize scores for critical, important, informational, editorial with 0
    initialize reasons for all labels
    requires_manual_review = false

    if semantic_type belongs to critical semantic types:
        hit(critical, 100, "change_type=<type>")
    if semantic_type belongs to important semantic types:
        hit(important, 100, "change_type=<type>")
    if semantic_type belongs to informational semantic types:
        hit(informational, 100, "change_type=<type>")
    if semantic_type belongs to editorial semantic types:
        hit(editorial, 100, "change_type=<type>")

    parse extracted_entities
    apply entity rules with score 95
    apply keyword regex rules with score 90

    if canonical(old_text) == canonical(new_text):
        hit(editorial, 85, "normalized_text_equal")

    if informational contact/reference appears only in new_text:
        hit(informational, 80, "contact_or_reference_added")

    if no scores were assigned:
        hit(important, 51, "fallback_manual_review")
        requires_manual_review = true

    best_label = max(labels, key=(scores[label], LABEL_PRIORITY[label]))
    confidence = scores[best_label] / 100
    explanation = build_explanation(best_label, reasons[best_label], requires_manual_review)

    return ImportancePrediction(best_label, confidence, reasons[best_label], explanation, requires_manual_review)
```

## 17. Примеры классификации

Примеры ниже отражают текущую baseline-логику, а не экспертную юридическую оценку.

### Example 1 — deadline change

```text
OLD: Срок рассмотрения заявления составляет 10 рабочих дней.
NEW: Срок рассмотрения заявления составляет 7 рабочих дней.
```

Expected significance: `critical`.

Reason: semantic type `deadline`, deadline markers and extracted `deadline_old/deadline_new` относятся к critical signals.

### Example 2 — obligation change

```text
NEW: Сотрудник обязан уведомить заявителя о готовности результата.
```

Expected significance: `critical`.

Reason: semantic type `obligation` and markers `обязан` / `staff_action` indicate a change in employee action.

### Example 3 — document list change

```text
OLD: Заявитель представляет паспорт.
NEW: Заявитель представляет паспорт и СНИЛС.
```

Expected significance: `critical`.

Reason: semantic type `document`, entity `required_documents_new`, marker `СНИЛС`; changes required documents.

### Example 4 — responsibility change

```text
NEW: Сотрудник несёт дисциплинарную и материальную ответственность в соответствии с законодательством.
```

Expected significance: `critical`.

Reason: semantic type `responsibility`; critical markers `дисциплинарн*`, `материальн*`, `ответственност*`.

### Example 5 — procedure change

```text
OLD: Приём заявлений осуществляется в порядке живой очереди.
NEW: Приём заявлений осуществляется по предварительной записи через региональный портал.
```

Expected significance: `important`.

Reason: semantic type `procedure` and important marker `предварительная запись` affect workflow.

### Example 6 — informational addition

```text
OLD: Консультации предоставляются в рабочее время.
NEW: Консультации предоставляются в рабочее время. Дополнительно указан телефон горячей линии 8-800-100-00-00.
```

Expected significance: `informational`.

Reason: contact/reference information is added; markers `телефон`, `горячая линия`, `8-800`.

### Example 7 — editorial change

```text
OLD: Прием документов осуществляется ежедневно.
NEW: Приём документов осуществляется ежедневно.
```

Expected significance: `editorial`.

Reason: canonical old/new text equal after normalization (`ё→е`, punctuation/spacing normalization); no domain-impact marker changes.

### Example 8 — unclassified fallback

```text
OLD: Специалист выполняет действие по установленному маршруту.
NEW: Специалист выполняет действие по согласованному маршруту.
```

Expected significance: `important` with `requires_manual_review=True`.

Reason: no strong semantic/entity/keyword signal; current baseline intentionally does not discard ambiguous changes.

## 18. Baseline nature of the method

Текущий significance-layer является **deterministic rule-based baseline**.

Он не использует:

- embeddings;
- ML classifier;
- LLM-based classification;
- external API;
- RAG;
- probabilistic semantic model;
- юридическую экспертную систему.

Сильные стороны baseline:

- полностью локальное выполнение;
- воспроизводимость результата;
- объяснимые `significance_rules` и `significance_reason`;
- простая проверка unit/integration tests;
- пригодность для MVP и защиты как первого метода приоритизации;
- возможность будущей экспериментальной оценки на размеченном корпусе.

Ограничение baseline: он опирается на surface-level lexical/entity/semantic-type rules и не понимает все юридические эффекты сложных формулировок.

## 19. Связь с архитектурой системы

Significance-layer согласован с local-first layered architecture проекта.

| Архитектурный слой | Компоненты | Роль significance |
|---|---|---|
| Domain layer | `importance.py`, `change_enrichment.py`, `diff_summary.py`, `diff_quiz.py` | Детерминированные правила, enrichment и prioritization |
| Service layer | `workflows.py` | Оркестрация comparison → significance → summary → quiz |
| Persistence layer | `VersionChangeItem`, `Summary`, `GeneratedQuiz`, `Question` | Materialized results and provenance |
| API layer | serializers/endpoints | Возвращает significance fields и summary counts |
| Demo layer | Django templates | Показывает labels, reasons, manual-review flags и quiz preview |

Соответствие `M = <E, N, S, C, P, G, R>`:

| Stage | Реализация | Связь с P |
|---|---|---|
| `E` | text extraction | Даёт текст версии |
| `N` | normalization | Стабилизирует текст для chunking/diff |
| `S` | `Chunk` and structural chunking | Даёт фрагменты и structural anchors |
| `C` | `VersionComparison`, `VersionChangeItem`, `diff.py` | Формирует materialized changes для significance |
| `P` | significance fields on `VersionChangeItem` | Приоритизирует changes and explains importance |
| `G` | `Summary`, `GeneratedQuiz`, `Question`, `Choice` | Использует prioritized changes for brief and quiz |
| `R` | `QuizAttempt`, `Answer`, reporting | Фиксирует результат прохождения quiz |

Significance не противоречит MVP scope: он остаётся rule-based и не требует LLM. Optional LLM в проекте относится к result/reporting enhancement и не является частью stage `P`.

## 20. Связь с будущей экспериментальной оценкой

Фаза 10 описывает метод. Качество significance-layer должно оцениваться позже, в Фазе 16.

Потенциальные метрики Фазы 16:

| Metric | Purpose |
|---|---|
| Accuracy | Общая доля совпадения predicted label с expected label |
| Precision по `critical` | Насколько часто critical predictions действительно critical |
| Recall по `critical` | Сколько critical changes baseline не пропускает |
| Precision по `important` | Насколько надёжны important predictions |
| Recall по `important` | Сколько important changes найдено |
| Confusion matrix | Какие категории чаще путаются |
| Editorial false positive rate | Доля editorial правок, ошибочно признанных significant |
| Significant false negative rate | Доля important/critical изменений, ошибочно признанных editorial/informational |
| Manual review rate | Доля fallback cases with `requires_manual_review=True` |
| Expected importance vs predicted importance | Сопоставление экспертной разметки с baseline output |

В Фазе 10 не создаётся новый evaluation corpus и не запускается confusion matrix. Уже существующие `data/importance_dataset/*` и `tools/evaluate_importance_rules.py` не меняются и не используются как результат Фазы 10.

## 21. Ограничения метода

1. Метод является baseline/rule-based, а не ML/LLM-классификатором.
2. Качество significance зависит от качества structural chunking stage `S`.
3. Качество significance зависит от качества comparison stage `C` и корректности matched chunks.
4. Лексические правила могут ошибаться на сложных юридических формулировках.
5. Editorial detection может давать false positives и false negatives.
6. `employee_impact` не реализован отдельной моделью; он выводится из semantic types, entities and lexical markers.
7. Structural features не дают отдельного числового boost в `importance.py`; они используются косвенно через diff/classification context и traceability.
8. `significance_score` является confidence/priority score правила, а не статистической вероятностью.
9. Категории значимости не являются юридическим заключением.
10. Метод не заменяет экспертизу юриста или владельца регламента.
11. Неоднозначные случаи требуют human-in-the-loop через `requires_manual_review` и quiz approval workflow.
12. Optional LLM не является обязательной частью significance-layer.
13. Категории `medium` и `minor` не реализованы; нельзя заявлять их как поддерживаемые.
14. Будущая экспериментальная оценка требует размеченного evaluation corpus и отдельной методологии.

## 22. Формулировка для диссертации

В рамках разработанного гибридного метода предложен baseline-метод оценки значимости изменений нормативно-правовых и регламентных документов. Метод использует материализованные результаты структурно-ориентированного сравнения редакций, тип diff-операции, предварительно определённый semantic type, лексические маркеры, baseline-сущности, structural context фрагмента и признаки потенциального влияния изменения на действия сотрудника. Результатом работы метода является присвоение change item категории `critical`, `important`, `informational` или `editorial`, а также сохранение confidence score, объяснения, списка сработавших правил и флага необходимости ручной проверки. Это позволяет отделять содержательные изменения от редакционных правок и использовать приоритетные изменения при формировании краткой выжимки и контрольно-обучающих материалов.

Фактическая реализация метода является deterministic/rule-based baseline и не использует обязательный LLM или ML-классификатор. Такой подход обеспечивает локальную воспроизводимость, объяснимость и возможность последующей экспериментальной оценки качества на размеченном корпусе.

## 23. Вывод

Significance-layer в проекте является самостоятельным stage `P` гибридного метода `M = <E, N, S, C, P, G, R>`. Он получает materialized changes из comparison-layer, классифицирует их по semantic type и significance label, сохраняет объяснимые результаты на `VersionChangeItem` и передаёт приоритетные изменения в summary и quiz generation.

Главный научно-инженерный результат Фазы 10: реализованный слой significance можно описывать как защищаемый baseline-метод приоритизации изменений по потенциальной значимости для сотрудников организации. Метод не является полноценным юридическим reasoning engine, но он существенно сильнее простого diff, потому что переводит технические различия между версиями в человеко-ориентированные категории важности, пригодные для выжимки, обучения и будущей экспериментальной оценки.
