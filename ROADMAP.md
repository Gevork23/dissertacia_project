# Roadmap

## 1. Completed technical MVP

Технический MVP считается собранным и стабилизированным в границах локального version-first pipeline:

**версия документа → анализ изменений → выжимка → тест → утверждение → прохождение → результат.**

Завершённый блок технической стабилизации:

- ревизия текущего состояния проекта;
- repository cleanup и усиление hygiene-правил;
- нормализация service boundaries и устранение критических дублей business logic;
- штатный deterministic fallback при отключённом LLM enhancement;
- MVP freeze и фиксация границ защищаемого scope.

В текущий technical MVP входят:

- document upload;
- document versioning;
- extraction;
- normalization;
- structural chunking;
- version comparison;
- significance classification;
- summary/brief;
- quiz generation;
- quiz approval workflow;
- employee attempt;
- result/reporting;
- demo UI;
- API;
- tests;
- smoke.

MVP больше не расширяется новыми продуктовыми направлениями до завершения научной упаковки.

## 2. Current stabilization block

Текущий блок после MVP freeze не означает бесконечную разработку функций. Его цель — подготовить уже реализованный MVP к научному описанию, воспроизводимым экспериментам и защите.

В блок входят:

- scope freeze;
- research method formalization;
- architecture formalization;
- синхронизация терминологии между scope, architecture, README и главами;
- контроль того, что optional/future work не попадает обратно в core MVP.

Definition of Done:

- MVP можно объяснить одной фразой;
- core / optional / future work разделены;
- документация не обещает OCR, RAG, LangGraph, Консультант+, BI, LMS, auth/RBAC или внешние integration как реализованный MVP;
- дальнейшие задачи относятся к научной упаковке и защите, а не к расширению продукта.

## 3. Research packaging

Следующий крупный блок — научная формализация уже реализованной системы.

- hybrid method;
- architecture;
- structural chunking method;
- version comparison method;
- significance method;
- quiz generation method.

Цель блока — описать метод так, чтобы он был воспроизводимым, объяснимым и связанным с кодом MVP.

Важно: research packaging не добавляет новые runtime-функции. Он формализует уже существующие инженерные решения и готовит их к экспериментальной проверке.

## 4. Experiments

Экспериментальный блок выполняется после формализации методов.

- demo corpus formalization;
- evaluation corpus;
- chunking evaluation;
- diff evaluation;
- significance evaluation;
- summary evaluation;
- quiz evaluation;
- final evaluation.

На Фазе 5 корпуса и evaluation suite не создаются. Этот блок фиксируется как следующий этап после научной формализации.

## 5. Thesis and defense

Блок подготовки диссертации и защиты:

- chapters;
- final docs;
- demo script;
- presentation;
- Q&A;
- контрольный прогон локального сценария;
- финальная сверка того, что защита показывает реализованный MVP, а не future work.

## 6. Future work after defense

После защиты можно рассматривать расширения, которые сознательно не входят в текущий MVP:

- OCR для сканированных PDF;
- RAG-chat по корпусу документов;
- LangGraph / multi-agent orchestration;
- интеграция с Консультант+ или другими внешними правовыми системами;
- external legal monitoring;
- production auth/RBAC;
- advanced BI / enterprise dashboard;
- большая LMS или LMS-интеграции;
- distributed/cloud-first deployment;
- обучение или дообучение специализированной модели.

Эти направления не являются долгами Фазы 5. Они зафиксированы как осознанно отложенные возможности после защиты или после отдельного research/product decision.
