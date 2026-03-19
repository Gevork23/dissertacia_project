#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if command -v docker >/dev/null 2>&1 && docker compose ps --services 2>/dev/null | grep -qx backend; then
  docker compose exec backend sh -c "cd /app && isort --check-only backend tools && black --check backend tools && flake8 backend tools"
else
  cd "$ROOT_DIR"
  python -m isort --check-only backend tools
  python -m black --check backend tools
  python -m flake8 backend tools
fi
