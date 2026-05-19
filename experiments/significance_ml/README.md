# ML / Hybrid significance experiment

Offline research artifacts for comparing three significance strategies:

- `rule_based_baseline`
- `ml_text_model`
- `hybrid_model`

Main entry points:

```bash
python experiments/significance_ml/evaluate_significance_ml.py
python backend/manage.py run_significance_ml_experiment
```

Generated artifacts:

- `significance_ml_summary.json`
- `significance_ml_predictions.csv`
- `significance_ml_confusion_matrix.csv`
- `significance_ml_feature_report.csv`
- `significance_ml_error_examples.csv`

The experiment is read-only with respect to the production pipeline. It uses the labeled significance evaluation artifacts as an offline dataset and does not change runtime significance classification.
