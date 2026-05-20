# Dissertacia Project

Research and engineering platform for version-aware analysis of regulatory documents. The system extracts document text, normalizes structure, compares revisions, prioritizes important changes, generates summaries and quizzes, and records review or assessment results.

## Project overview

This repository serves three roles at once:

1. Master thesis implementation and artifact base.
2. Production-oriented Django backend for local or internal deployment.
3. Reproducible offline research environment for ML and hybrid experiments.

The core product flow is:

`document -> versions -> extraction -> normalization -> chunks -> diff -> significance -> summary -> quiz -> review/reporting`

## Architecture

Main runtime code lives in `backend/`.

- `backend/config`: Django settings, URL routing, runtime configuration.
- `backend/documents/domain`: deterministic domain logic for diff, chunking, enrichment, summary and quiz generation.
- `backend/documents/services`: orchestration, ingestion, offline experiments, reporting, moderation.
- `backend/documents/api`: DRF endpoints.
- `backend/documents/demo`: demo UI and research dashboard views.
- `experiments/`: offline evaluation outputs and generated figures/tables.
- `docs/`: thesis notes, experiment reports, architecture notes and defense materials.

Mermaid diagrams are in [docs/architecture/engineering-diagrams.md](docs/architecture/engineering-diagrams.md).

## Research methodology

The project uses a hybrid methodology:

- Deterministic document processing for extraction, normalization, chunking and version comparison.
- Explainable rule-based significance baseline for production-safe decision support.
- Offline supervised ML experiments to benchmark alternative strategies without replacing the deterministic runtime layer.
- Gold, curated synthetic and weak real-world sources kept explicitly separated in the corpus build process.

Target leakage has been removed from the ML contour. Gold labels are stored only as targets and analysis metadata; they are not used as model input features.

## Dataset creation

The supervised corpus is assembled from:

- `experiments/significance/significance_results.csv`
- `data/evaluation_corpus/*/annotation.json`
- Annotation Studio exports / DB annotations when available
- Curated synthetic examples
- Weak real-world traces kept in a separate inference-only split

Build the corpus:

```bash
python backend/manage.py build_supervised_ml_corpus
```

Generated artifacts include:

- `experiments/ml_corpus/full_dataset.csv`
- `experiments/ml_corpus/train.csv`
- `experiments/ml_corpus/validation.csv`
- `experiments/ml_corpus/test.csv`
- `experiments/ml_corpus/weak_inference_dataset.csv`
- `experiments/ml_corpus/dataset_profile.json`
- `experiments/ml_corpus/split_metadata.json`
- `experiments/ml_corpus/feature_schema.json`
- `experiments/ml_corpus/dataset_quality_report.md`

## Training pipeline

The offline experiment runner evaluates multiple baselines and model families:

- `rule_based_baseline`
- `tfidf_logistic_regression`
- `tfidf_linear_svm`
- `tfidf_random_forest`
- `tfidf_xgboost` when `xgboost` is available
- `embedding_logistic_regression` when a local SentenceTransformer checkpoint is available
- `hybrid_rule_ml`

Implemented features:

- Grid search or randomized search depending on model family
- `class_weight="balanced"` where applicable
- probability calibration for Linear SVM
- feature importance export
- optional SHAP summary export when the environment supports it

Run the full experiment suite:

```bash
python backend/manage.py run_significance_ml_experiment
```

## Evaluation protocol

The experiment runner now supports:

1. Random stratified split.
2. Group split by `document_id`.
3. Group split by `pair_id`.
4. Cross-source split.
5. Strict gold-only evaluation.
6. Predefined supervised split when `train.csv` / `test.csv` already exist.

Each run stores:

- accuracy
- macro precision
- macro recall
- macro F1
- weighted F1
- ROC-AUC macro OVR when probabilities and class coverage permit it
- classification report
- confusion matrix
- class distribution
- predictions and error analysis

## Reproducibility

Every experiment run writes a dedicated directory under `experiments/significance_ml/runs/` with:

- `metrics.json`
- `params.json`
- `split_info.json`
- `classification_report.json`
- `confusion_matrix.csv`
- `feature_importance.csv`
- `predictions.csv`
- `manifest.json`
- `error_analysis.csv`
- `plots/*.png`

`manifest.json` includes timestamp, git commit SHA, random seed, model name, feature set, split strategy, dataset size, class balance and library versions.

Smoke test:

```bash
python backend/manage.py smoke_test_project
```

It validates settings, DB access, demo data, corpus build and one offline ML experiment pass.

## Limitations

- OCR for scanned PDFs is not implemented in the main runtime contour.
- Research corpora are still relatively small and partly synthetic.
- Optional embedding / XGBoost / SHAP integrations depend on local packages and locally available model artifacts.
- The demo UI is demonstration-oriented, not a full production frontend.

## Ethical considerations

- The system is document-analysis software, not a substitute for legal review.
- Offline ML outputs are benchmark artifacts and do not override deterministic production-safe rules by default.
- Human review remains necessary for ambiguous or high-risk regulatory changes.
- Synthetic examples are clearly marked and must not be reported as real-world benchmark evidence.

## Quick start

### Local Python

1. Create a Python 3.12 environment.
2. Install runtime and dev dependencies.
3. Export required environment variables.
4. Run migrations and start the server.

Example:

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
set DJANGO_SECRET_KEY=local-dev-secret
set DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
python manage.py migrate
python manage.py runserver
```

### Docker

`infra/.env.example` contains the expected variables.

```bash
docker compose up --build
```

The image is now self-contained; `docker-compose.yml` still mounts the source tree for local development convenience.

## Running experiments

```bash
python backend/manage.py build_supervised_ml_corpus
python backend/manage.py run_significance_ml_experiment
python backend/manage.py smoke_test_project
```

Useful outputs:

- `experiments/ml_corpus/`
- `experiments/significance_ml/`
- `/demo/research/` research dashboard

## Docker deployment

Production-facing defaults are stricter now:

- `DJANGO_SECRET_KEY` is required outside tests.
- `DJANGO_DEBUG=False` by default.
- `DJANGO_ALLOWED_HOSTS` must be configured when debug is disabled.
- secure cookie and security header settings are enabled for non-test production profiles.

## CI status

GitHub Actions workflow: `.github/workflows/ci.yml`

The CI pipeline runs:

- `python manage.py check`
- targeted Django tests
- formatting and lint hooks when dependencies are available locally

## Security notes

Key configuration changes:

- `SECRET_KEY` only from environment outside test mode
- `DEBUG=False` by default
- `CSRF_COOKIE_HTTPONLY=True`
- `SESSION_COOKIE_SECURE=True` in non-debug non-test profiles
- `SECURE_CONTENT_TYPE_NOSNIFF=True`
- `SECURE_REFERRER_POLICY="same-origin"`
- `X_FRAME_OPTIONS="DENY"`

## Additional documentation

- [docs/architecture/engineering-diagrams.md](docs/architecture/engineering-diagrams.md)
- [docs/experiments/significance-ml-experiment.md](docs/experiments/significance-ml-experiment.md)
- [docs/experiments/supervised-ml-corpus.md](docs/experiments/supervised-ml-corpus.md)
- [docs/research-dashboard.md](docs/research-dashboard.md)
