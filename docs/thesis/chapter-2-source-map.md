# Chapter 2 Source Map

| Section | Source documents | Source code / data | Figures/tables |
|---|---|---|---|
| 2.1 | `docs/research/hybrid-method.md`, `docs/scope/mvp-freeze.md`, `PROJECT_SCOPE.md`, `README.md` | `backend/documents/models.py`, `backend/documents/services/*` | Figure 2.1 pipeline |
| 2.2 | `docs/research/hybrid-method.md`, `docs/thesis/chapter-3-draft.md` | `backend/documents/domain/*`, `backend/documents/services/*`, `backend/documents/models.py` | Table 2.1 method stages; Figure 2.1 pipeline |
| 2.3 | `docs/architecture/system-architecture.md`, `docs/architecture/service-boundaries.md`, `docs/architecture/llm-fallback-modes.md` | `backend/documents/demo/views.py`, `backend/documents/api/*`, `backend/documents/services/*`, `backend/documents/domain/*`, `backend/documents/models.py`, `docker-compose.yml` | Figure 2.2 system overview; Figure 2.3 component diagram; Figure 2.4 full scenario sequence |
| 2.4 | `docs/architecture/erd.md`, `docs/architecture/system-architecture.md` | `backend/documents/models.py`, migrations | Figure 2.5 ERD key entities |
| 2.5 | `docs/research/structural-chunking-method.md`, `docs/research/hybrid-method.md` | `backend/documents/domain/text_extractors.py`, `backend/documents/domain/text_processing.py`, `backend/documents/services/ingestion.py`, `backend/documents/tests/test_text_extraction.py`, `backend/documents/tests/test_text_normalization.py`, `backend/documents/tests/test_chunking.py` | Figure 2.1 pipeline |
| 2.6 | `docs/research/version-comparison-method.md`, `docs/research/hybrid-method.md` | `backend/documents/domain/diff.py`, `backend/documents/services/workflows.py`, `backend/documents/models.py`, `backend/documents/tests/test_compare_and_entities.py` | — |
| 2.7 | `docs/research/significance-method.md`, `docs/research/hybrid-method.md` | `backend/documents/domain/change_enrichment.py`, `backend/documents/domain/change_classification.py`, `backend/documents/services/importance.py`, `backend/documents/tests/test_importance.py`, `backend/documents/tests/test_significance_pipeline.py` | — |
| 2.8 | `docs/research/hybrid-method.md`, `docs/architecture/system-architecture.md`, `docs/experiments/summary-evaluation.md`, `docs/thesis/chapter-3-draft.md` | `backend/documents/domain/diff_summary.py`, `backend/documents/services/workflows.py`, `backend/documents/models.py` | — |
| 2.9 | `docs/research/quiz-generation-method.md`, `docs/research/hybrid-method.md`, `docs/experiments/quiz-generation-evaluation.md`, `docs/thesis/chapter-3-draft.md` | `backend/documents/domain/diff_quiz.py`, `backend/documents/services/workflows.py`, `backend/documents/services/quiz_workflow.py`, `backend/documents/models.py` | — |
| 2.10 | `docs/architecture/system-architecture.md`, `docs/architecture/service-boundaries.md`, `docs/scope/mvp-freeze.md` | `backend/documents/services/quiz_workflow.py`, `backend/documents/services/quiz_attempts.py`, `backend/documents/services/result_reporting.py`, `backend/documents/models.py`, `backend/documents/templates/demo/*` | Figure 2.4 full scenario sequence |
| 2.11 | `docs/architecture/system-architecture.md`, `docs/scope/mvp-freeze.md`, `README.md`, `docker-compose.yml` | `scripts/validate_evaluation_corpus.py`, `scripts/lint.sh`, `scripts/demo_smoke.sh`, `experiments/final/aggregate_experiment_results.py`, `experiments/final_visuals/build_final_figures.py` | — |
| 2.12 | `docs/scope/mvp-freeze.md`, `PROJECT_SCOPE.md`, `docs/architecture/llm-fallback-modes.md`, `docs/thesis/chapter-3-review-notes.md` | фактическое отсутствие OCR/RBAC/BI/LMS/RAG/LangGraph в backend scope | — |
| 2.13 | Все документы главы 2; `docs/thesis/chapter-3-draft.md` | materialized artifacts in `backend/documents/models.py` and services | — |

## Cross-check with Chapter 3

| Chapter 2 concept | Chapter 3 evaluation link |
|---|---|
| Structural chunking / `S` | 3.4 structural chunking evaluation |
| Structural comparison / `C` | 3.5 diff/comparison evaluation |
| Significance-layer / `P` | 3.6 significance evaluation |
| Summary-layer / part of `G` | 3.7 summary evaluation |
| Quiz generation / part of `G` | 3.8 quiz evaluation |
| End-to-end materialized pipeline | 3.9 integrated evaluation |
| MVP limitations and human-in-the-loop | 3.10–3.11 limitations and threats to validity |
