# Supervised ML corpus

This directory stores the offline supervised corpus for ML significance experiments.

Build corpus:

```bash
python experiments/ml_corpus/build_supervised_corpus.py
```

Train baseline models:

```bash
python experiments/ml_corpus/train_baseline_models.py
```

Main outputs:

- `full_dataset.csv`
- `train.csv`
- `validation.csv`
- `test.csv`
- `weak_inference_dataset.csv`
- `dataset_profile.json`
- `split_metadata.json`
- `feature_schema.json`
- `label_distribution.csv`
- `dataset_quality_report.md`
- `figures/*.png`
- `baseline_model_results.csv`
- `baseline_confusion_matrix.csv`
- `baseline_feature_importance.csv`

Balanced split protocol:
- strict supervised splits exclude weak examples;
- train/test must both contain all significance classes;
- non-synthetic examples prioritize group-aware no-leakage behavior;
- curated synthetic examples may relax pair grouping to preserve class coverage.

