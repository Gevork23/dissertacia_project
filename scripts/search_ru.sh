#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/search_ru.sh "обязан" 9
#   ./scripts/search_ru.sh "ответственность" 9

Q="${1:-}"
V="${2:-}"

if [[ -z "$Q" || -z "$V" ]]; then
  echo "Usage: $0 \"query\" version_id"
  exit 1
fi

# Use python for URL encoding to avoid Git Bash encoding issues
ENC_Q="$(python -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$Q")"

curl -s "http://localhost:8000/api/search/?q=${ENC_Q}&version_id=${V}"
echo