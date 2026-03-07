#!/usr/bin/env bash
set -euo pipefail
docker exec -it dissertacia_backend sh -c "cd /app && isort . && black . && flake8 ."