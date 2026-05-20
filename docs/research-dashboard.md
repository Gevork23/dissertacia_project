# Research Dashboard

Route: `/demo/research/`

## Purpose

Display already generated research artifacts without recalculating experiments during an HTTP request.

## Current research blocks

- final pipeline metrics
- figures and tables
- end-to-end diagnostics
- real-world regression summary
- significance ML experiment summary
- supervised ML corpus summary

## Updated ML expectations

The dashboard now reflects a safer experimental posture:

- target leakage is audited and exposed in artifact metadata;
- experiment summaries may contain multiple split strategies and multiple model families;
- root `experiments/significance_ml/*.json|csv` files mirror the current primary run for quick inspection, while detailed run folders live under `experiments/significance_ml/runs/`.

## Recommended workflow

1. Build the corpus.
2. Run the significance experiment suite.
3. Open `/demo/research/`.
4. Use linked artifacts for thesis figures, tables and defense discussion.
