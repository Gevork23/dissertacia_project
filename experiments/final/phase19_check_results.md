# Phase 19 check results

| Command | Status | Comment |
|---|---|---|
| `python scripts/validate_evaluation_corpus.py` | pass | Evaluation corpus validation PASS; 10 pairs, 13 expected changes, 23 expected chunks. |
| `python experiments/final/aggregate_experiment_results.py` | pass | Rebuilt Phase 19 CSV/JSON/PNG/MD artifacts. |
| `python backend/manage.py check` | fail / environment | Django is not installed in the execution environment (`ModuleNotFoundError: No module named 'django'`). |
| `python backend/manage.py makemigrations --check --dry-run` | fail / environment | Django is not installed in the execution environment. |
| `python backend/manage.py test` | fail / environment | Django is not installed in the execution environment. |
| `bash scripts/lint.sh` | fail / environment | Lint environment is unavailable; script reports missing isort/black/flake8 or backend container. |
| `bash scripts/demo_smoke.sh` | fail / environment | Demo server is not running; curl cannot connect to `127.0.0.1:8000`. |
| `git status --short` | dirty | Dirty state contains existing Phase 14-18 experiment/report changes from the uploaded archive plus new Phase 19 artifacts. No runtime files such as `db.sqlite3`, `media/`, logs, `__pycache__/`, or `.pytest_cache/` were intentionally added. |
