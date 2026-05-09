# Bibliography Placeholders for Chapters 1–3

Документ фиксирует места, где нужны внешние источники. Конкретные ГОСТ-записи, авторы и статьи здесь не выдумываются.

| Chapter section | Claim requiring source | Suggested source type | Priority |
|---|---|---|---|
| 1.1 | Рост объёма нормативной информации, документооборота и частоты обновления регламентов усложняет ручной контроль изменений. | Статистический отчёт, отраслевой обзор, научная статья по электронному документообороту / regulatory change management | High |
| 1.3 | Ручное доведение изменений до сотрудников плохо масштабируется и требует контроля усвоения. | Источник по compliance learning, employee training, knowledge transfer in organizations | Medium |
| 1.4 | Системы электронного документооборота хорошо решают хранение и маршрутизацию документов, но не закрывают полный pipeline анализа значимых изменений. | Обзор document management systems / ECM / СЭД | High |
| 1.4 | Правовые справочные системы обеспечивают доступ к нормативной информации, но не решают локальный контур version-first анализа внутренних редакций. | Обзор legal information systems / legal tech systems | Medium |
| 1.4–1.5 | Традиционные document comparison / text diff approaches обнаруживают текстовые отличия, но ограничены при структурном анализе нормативных документов. | Научные публикации или технические обзоры по diff algorithms, document comparison, structured document comparison | High |
| 1.4–1.5 | Legal NLP и information extraction применимы к юридическим текстам, но требуют аккуратной постановки задачи, разметки и контроля качества. | Обзор legal NLP / NLP for legal documents / information extraction | High |
| 1.4–1.5 | LLM-based document analysis требует контроля hallucinations, unsupported claims, воспроизводимости и traceability. | Исследования по LLM reliability, hallucinations, grounded generation, document QA risks | High |
| 1.5, 2.10, 3.10–3.11 | Human-in-the-loop workflow необходим для проверки автоматически подготовленных материалов в нормативной области. | Публикации по human-in-the-loop systems, responsible AI, AI-assisted decision support | High |
| 1.6, 2.11–2.12 | Local-first / reproducible MVP оправдан для исследования, где важны воспроизводимость и ограничение внешних зависимостей. | Источник по reproducible software systems / local-first software / research prototypes | Medium |
| 2.2 | Формализация pipeline как гибридного метода должна быть сопоставлена с литературой по document intelligence pipelines. | Публикации по document intelligence, workflow/pipeline architectures, hybrid NLP systems | Medium |
| 2.5 | Structural chunking нормативных текстов опирается на идею структурного представления документа, а не только на абзацное разбиение. | Источники по structured document processing, segmentation of legal/regulatory texts | High |
| 2.6 | Structural comparison имеет преимущества над plain text / paragraph diff для структурированных документов. | Источники по structure-aware document comparison / semantic diff | High |
| 2.7 | Rule-based significance classification является baseline-подходом, не заменяющим экспертную оценку. | Источники по rule-based classification, legal text classification, explainable baselines | Medium |
| 2.9–2.10 | Generated quiz questions должны проходить review before use, поскольку автоматическая генерация не гарантирует корректность. | Источники по AI-generated educational content, assessment quality, human review | Medium |
| 3.2–3.3 | Synthetic evaluation corpus допустим для первичной MVP-оценки, но ограничивает external validity. | Источники по methodology for NLP/document system evaluation, synthetic datasets limitations | High |
| 3.10–3.11 | Threats to validity должны интерпретировать ограничения corpus, annotation, metrics и downstream propagation. | Методологические источники по empirical software engineering / NLP evaluation validity | High |

## Категории источников, которые нужно подобрать вручную

- электронный документооборот;
- document management systems;
- document comparison / diff algorithms;
- legal NLP;
- LLM hallucinations / reliability;
- human-in-the-loop systems;
- employee training / compliance learning;
- evaluation methodology for NLP/document systems.
