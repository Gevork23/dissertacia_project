# Экспериментальные материалы

Этот каталог содержит отчёты по экспериментальной оценке гибридного метода для диссертации. Материалы сгруппированы по фазам и используются в главе 3.

| Файл | Назначение |
|---|---|
| `chunking-evaluation.md` | Отчёт по Фазе 14: оценка структурного разбиения документа и comparison с baseline chunking methods. |
| `diff-evaluation.md` | Отчёт по Фазе 15: оценка diff/comparison layer и сравнение plain text, paragraph и structural chunk diff. |
| `significance-evaluation.md` | Отчёт по Фазе 16: оценка significance-layer и high-priority detection для important/critical changes. |
| `summary-evaluation.md` | Отчёт по Фазе 17: оценка summary-layer, topic coverage, unsupported claims и editorial/noise overemphasis. |
| `quiz-generation-evaluation.md` | Отчёт по Фазе 18: оценка quiz generation, question quality, coverage и source/explanation traceability. |
| `final-method-evaluation.md` | Отчёт по Фазе 19: сводная интегральная оценка метода и end-to-end trace analysis. |
| `final-figures-and-tables.md` | Материал Фазы 20: финальные рисунки, таблицы, подписи, cautious claims и recommended thesis inserts для главы 3. |

## Связанные machine-readable artifacts

- `experiments/final/final_metrics_summary.json` — сводные метрики по этапам.
- `experiments/final/end_to_end_summary.json` — end-to-end funnel summary.
- `experiments/final/end_to_end_trace.csv` — trace important/critical changes through pipeline.
- `experiments/final_visuals/` — dissertation-ready figures, tables and `final_visuals_manifest.json`.

## Примечание по интерпретации

Эксперименты используют synthetic evaluation corpus и key-change/key-boundary annotation. Поэтому результаты следует формулировать как подтверждение применимости гибридного метода в рамках локального MVP-сценария, а не как универсальную юридическую полноту или превосходство над всеми возможными методами анализа документов.
