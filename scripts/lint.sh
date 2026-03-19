#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if command -v docker >/dev/null 2>&1 && docker compose ps --services 2>/dev/null | grep -qx backend; then
  docker compose exec backend sh -c "cd /app && isort --check-only . && black --check . && flake8 ."
else
  cd "$BACKEND_DIR"
  python -m isort --check-only .
  python -m black --check .
  python -m flake8 .
fi