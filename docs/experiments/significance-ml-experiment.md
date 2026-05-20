# Significance ML Experiment

## Goal

Benchmark ML and hybrid alternatives to the deterministic significance layer without replacing the production-safe rule-based runtime.

## Leakage status

Target leakage has been removed.

- `high_priority_label` is no longer used as an input feature.
- Gold labels remain only in target columns.
- Feature audits are generated automatically and persisted in experiment artifacts.
- Safe features are derived only from document text, structural metadata and rule outputs available before inference.

Why this matters:

- leaked features produce artificially inflated metrics;
- thesis conclusions become invalid if train-time features encode the answer;
- production expectations diverge from offline results if leakage is present.

## Supported split strategies

- Random stratified split
- Group split by `document_id`
- Group split by `pair_id`
- Cross-source split
- Strict gold-only evaluation
- Predefined supervised split from `train.csv` / `test.csv`

## Supported models

- Rule-based baseline
- TF-IDF + Logistic Regression
- TF-IDF + Linear SVM with calibration
- TF-IDF + Random Forest
- TF-IDF + XGBoost when available
- Embedding + Logistic Regression when a local embedding checkpoint is available
- Hybrid rule + ML

## Stored artifacts per run

- `metrics.json`
- `params.json`
- `split_info.json`
- `classification_report.json`
- `confusion_matrix.csv`
- `feature_importance.csv`
- `predictions.csv`
- `manifest.json`
- `error_analysis.csv`
- `shap_summary.csv` when available
- `plots/*.png`

## Metrics

- accuracy
- precision macro
- recall macro
- F1 macro
- F1 weighted
- ROC-AUC macro OVR when probabilities are available
- confusion matrix
- classification report
- class distribution

## Error analysis

Each run stores:

- false positives
- false negatives
- most confident errors
- least confident predictions

Primary CSV columns:

- `document_id`
- `text`
- `true_label`
- `predicted_label`
- `probability`
- `error_type`

## Reproducibility

`manifest.json` includes:

- timestamp
- git commit SHA
- random seed
- model name
- feature set
- split strategy
- dataset size
- class balance
- library versions

## Command

```bash
python backend/manage.py run_significance_ml_experiment
```
