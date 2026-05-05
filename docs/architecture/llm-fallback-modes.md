# LLM Fallback Modes

## 1. Цель документа

Документ фиксирует штатные режимы result/reporting при включённом и отключённом LLM enhancement. Цель Фазы 4 — сделать локальный deterministic режим спокойным и воспроизводимым: отключённый LLM не должен выглядеть как ошибка системы в логах, тестах или demo-сценарии.

## 2. Контекст проекта

Проект реализует локальную интеллектуальную систему для работы с нормативно-правовыми и внутренними регламентными документами. Основной pipeline остаётся deterministic / rule-based / hybrid first:

`document upload → document versioning → text extraction → normalization → structural chunking → version comparison → significance classification → summary → quiz generation → quiz approval workflow → employee attempt → result/reporting`.

Result/reporting строится поверх уже материализованного snapshot завершённой попытки: `score`, `correct_answers`, `answers`, `score_percent`, timestamps и статуса. Reporting layer не является scoring engine и не пересчитывает результат альтернативным способом.

## 3. Почему LLM является optional enhancement

LLM используется только как enhancement для человекочитаемых комментариев и управленческого текста. Базовая ценность системы не зависит от внешнего API: попытка сотрудника, итоговый score, pass/fail, частотные ошибки и fallback feedback формируются локально.

Такой подход важен для магистерского проекта и защиты:

- demo воспроизводится без сетевой зависимости;
- локальный MVP можно запускать без API keys и без Ollama/OpenAI-compatible endpoint;
- штатный deterministic режим не создаёт красные ERROR-логи;
- результат остаётся объяснимым и проверяемым по сохранённым данным попытки.

## 4. Режим `RESULT_LLM_ENABLED=False`

`RESULT_LLM_ENABLED=False` — штатный локальный режим, а не ошибка.

Поведение:

- LLM client не создаётся и не вызывается;
- используется deterministic fallback;
- traceback не формируется;
- ERROR logs не пишутся;
- result/reporting payload остаётся полным;
- cache заполняется fallback-текстами с model marker `rule_based_fallback`.

Допустимый лог:

```text
INFO LLM result enhancement is disabled; deterministic fallback is used.
```

## 5. Режим `RESULT_LLM_ENABLED=True`

При включённом флаге система пытается выполнить LLM enhancement для:

- feedback по отдельной завершённой попытке;
- quiz-level анализа типовых ошибок;
- quiz-level manager summary.

Если LLM работает, enhanced-текст сохраняется в cache и возвращается в result/reporting payload. Тесты не должны зависеть от внешнего API: client мокается локально.

Если LLM реально ломается, пользовательский сценарий не должен падать. Ошибка фиксируется как failure включённого enhancement, после чего используется deterministic fallback.

Допустимый лог:

```text
WARNING LLM result enhancement failed; deterministic fallback is used.
WARNING LLM quiz report enhancement failed; deterministic fallback is used: quiz_id=<id>
```

## 6. Deterministic fallback

Fallback формирует локальные тексты на основе материализованных данных:

- feedback по попытке: score, pass threshold, correct/wrong/unanswered counts, weak topics from saved answers;
- report text по типовым ошибкам: frequent error groups from saved attempt answers;
- manager summary: attempts count, average percentage, pass rate, top problematic topic and recommendation;
- result summary: уже сохранённые score/result fields, без повторного scoring.

Fallback не обращается к сети, не требует API key и не меняет scoring snapshot.

## 7. Logging policy

| Сценарий | Уровень лога | Поведение |
|---|---:|---|
| LLM disabled | INFO/DEBUG | deterministic fallback used; no traceback; no ERROR |
| LLM enabled and works | INFO/DEBUG | enhanced result used and cached |
| LLM enabled and fails | WARNING | failure is visible for developers; deterministic fallback used; user workflow continues |

Важно: disabled mode не должен проходить через generic exception path. Actual LLM failures при включённом режиме не скрываются silent fallback'ом: они логируются как warning с диагностическим контекстом.

## 8. Testing policy

Регрессионные тесты должны подтверждать:

- `RESULT_LLM_ENABLED=False` является нормальным режимом;
- при disabled mode LLM client не вызывается;
- при disabled mode нет `ERROR`, traceback и misleading `generation failed` в логах;
- при `RESULT_LLM_ENABLED=True` исключение LLM client не ломает result/reporting;
- fallback texts и API/demo-compatible payload остаются непустыми;
- тесты не ходят во внешнюю сеть и используют mock/fake client.

## 9. Demo implications

Для demo перед научным руководителем или комиссией безопасный режим по умолчанию — `RESULT_LLM_ENABLED=False`. В этом режиме система демонстрирует весь основной pipeline и result/reporting без красных LLM-ошибок.

LLM можно включать отдельно как optional enhancement, но его недоступность не должна блокировать submit attempt, result endpoint, quiz report или demo detail page.

## 10. Ограничения

Фаза 4 не внедряет новых LLM-провайдеров, RAG, LangGraph, retry/backoff/circuit breaker или агентную архитектуру. Она также не меняет scoring, модели, миграции, quiz generation и границы service layer, зафиксированные после Фазы 3.

## 11. Вывод

LLM enhancement является дополнительным улучшением качества текстового feedback/reporting, а не обязательной основой системы. Штатный локальный режим — deterministic fallback с полным result/reporting payload, спокойным логированием и воспроизводимым demo.
