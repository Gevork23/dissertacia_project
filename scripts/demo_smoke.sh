#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "[1/5] health"
curl -fsS "$BASE_URL/api/health/" >/dev/null

echo "[2/5] demo dashboard"
curl -fsS "$BASE_URL/demo/" >/dev/null

echo "[3/5] api root"
curl -fsS "$BASE_URL/api/" >/dev/null

echo "[4/5] quizzes list"
curl -fsS "$BASE_URL/api/quizzes/" >/dev/null

echo "[5/5] smoke checks passed"
