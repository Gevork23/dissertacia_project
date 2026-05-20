# Supervised ML Corpus

## Purpose

Build a reproducible offline corpus for significance-classification experiments while keeping weak and synthetic evidence explicitly separated from strict gold evaluation.

## Data sources

- `experiments/significance/significance_results.csv`
- `data/evaluation_corpus/*/annotation.json`
- Annotation Studio DB / export data when available
- Curated synthetic examples
- Weak real-world traces stored separately

## Leakage controls

- Target-derived fields are not used as model input features.
- `feature_schema.json` includes a leakage audit section.
- Weak examples are excluded from strict train/validation/test splits.
- Group-aware split checks detect pair overlap.

## Outputs

- `full_dataset.csv`
- `train.csv`
- `validation.csv`
- `test.csv`
- `weak_inference_dataset.csv`
- `dataset_profile.json`
- `split_metadata.json`
- `feature_schema.json`
- `dataset_quality_report.md`
- `figures/*.png`

## Notes

- `document_id` is now carried through the dataset to support document-level group splits.
- `high_priority_label` remains a derived target for analysis only and is not part of the feature set.
- The corpus builder keeps `rule_based_confidence` and `rule_based_requires_manual_review` because they are available before ML inference and do not use gold labels.

## Command

```bash
python backend/manage.py build_supervised_ml_corpus
```
