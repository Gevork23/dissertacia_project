# Chapter 2 Figures and Tables Map

| Figure/Table | Recommended title | Source | Target section |
|---|---|---|---|
| Figure 2.1 | Общий pipeline системы | `docs/architecture/diagrams/pipeline.mmd` | 2.2 |
| Figure 2.2 | Архитектура системы | `docs/architecture/diagrams/system-overview.mmd` | 2.3 |
| Figure 2.3 | Component diagram разработанной системы | `docs/architecture/diagrams/component-diagram.mmd` | 2.3 |
| Figure 2.4 | Последовательность полного сценария | `docs/architecture/diagrams/full-scenario-sequence.mmd` | 2.3 / 2.10 |
| Figure 2.5 | ERD ключевых сущностей | `docs/architecture/erd.md` | 2.4 |
| Table 2.1 | Этапы гибридного метода | `docs/research/hybrid-method.md`, `docs/thesis/chapter-2-draft.md` | 2.2 |
| Table 2.2 | Связь этапов метода с архитектурными компонентами | `docs/architecture/system-architecture.md` | 2.3 / 2.4 |
| Table 2.3 | Ограничения MVP | `docs/scope/mvp-freeze.md` | 2.12 |

## Notes

- Mermaid-файлы `.mmd` нужно либо вставить как исходные схемы, либо отрендерить в PNG/SVG на этапе финальной вёрстки.
- ERD из `docs/architecture/erd.md` рекомендуется упростить до ключевых сущностей главы 2: `Document`, `DocumentVersion`, `Chunk`, `VersionComparison`, `VersionChangeItem`, `Summary`, `GeneratedQuiz`, `Question`, `Choice`, `QuizAttempt`, `Answer`.
- Таблица 2.1 уже включена в `chapter-2-draft.md`.
- Таблицы 2.2 и 2.3 являются optional: их можно добавить при финальной редактуре, если нужно усилить архитектурную или scope-часть главы.
