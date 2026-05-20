#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LINT_TARGETS=(
  backend/config
  backend/core
  backend/documents
  backend/manage.py
  tools
)

LOCAL_PYTHON=""

pick_local_python() {
  local candidates=(
    "$ROOT_DIR/.venv/Scripts/python.exe"
    "$ROOT_DIR/.venv/bin/python"
    "$ROOT_DIR/venv/Scripts/python.exe"
    "$ROOT_DIR/venv/bin/python"
    "$ROOT_DIR/backend/.venv/Scripts/python.exe"
    "$ROOT_DIR/backend/.venv/bin/python"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ]; then
      LOCAL_PYTHON="$candidate"
      return 0
    fi
  done

  if command -v python >/dev/null 2>&1; then
    LOCAL_PYTHON="$(command -v python)"
    return 0
  fi

  return 1
}

python_has_lint_tools() {
  local py="$1"
  "$py" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

mods = ("isort", "black", "ruff", "flake8", "mypy")
ok = all(importlib.util.find_spec(name) is not None for name in mods)
sys.exit(0 if ok else 1)
PY
}

docker_backend_has_lint_tools() {
  command -v docker >/dev/null 2>&1 || return 1

  docker compose exec -T backend sh -lc '
cd /app &&
python - <<'"'"'PY'"'"'
import importlib.util
import sys

mods = ("isort", "black", "ruff", "flake8", "mypy")
ok = all(importlib.util.find_spec(name) is not None for name in mods)
sys.exit(0 if ok else 1)
PY
' >/dev/null 2>&1
}

run_local_lint() {
  local py="$1"
  cd "$ROOT_DIR"
  "$py" -m isort --check-only "${LINT_TARGETS[@]}"
  "$py" -m black --check "${LINT_TARGETS[@]}"
  "$py" -m ruff check "${LINT_TARGETS[@]}"
  "$py" -m flake8 "${LINT_TARGETS[@]}"
  "$py" -m mypy \
    backend/documents/services/significance_ml_experiment.py \
    backend/documents/services/supervised_ml_corpus.py \
    backend/config/settings.py
}

run_docker_lint() {
  docker compose exec -T backend sh -lc '
cd /app &&
python -m isort --check-only backend/config backend/core backend/documents backend/manage.py tools &&
python -m black --check backend/config backend/core backend/documents backend/manage.py tools &&
python -m ruff check backend/config backend/core backend/documents backend/manage.py tools &&
python -m flake8 backend/config backend/core backend/documents backend/manage.py tools &&
python -m mypy \
  backend/documents/services/significance_ml_experiment.py \
  backend/documents/services/supervised_ml_corpus.py \
  backend/config/settings.py
'
}

if pick_local_python && python_has_lint_tools "$LOCAL_PYTHON"; then
  run_local_lint "$LOCAL_PYTHON"
elif docker_backend_has_lint_tools; then
  run_docker_lint
else
  echo "lint.sh: не найдено рабочее окружение для lint." >&2
  echo "Нужно либо локальное Python-окружение с isort/black/ruff/flake8/mypy, либо backend-контейнер с этими пакетами." >&2
  exit 1
fi
