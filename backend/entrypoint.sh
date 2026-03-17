#!/bin/sh
set -eu

echo "[entrypoint] starting backend bootstrap"

python - <<'PY'
import os
import socket
import sys
import time

services = [
    (
        os.environ.get("POSTGRES_HOST", "db"),
        int(os.environ.get("POSTGRES_PORT", "5432")),
        "postgres",
    ),
]

if os.environ.get("QDRANT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}:
    services.append(
        (
            os.environ.get("QDRANT_HOST", "qdrant"),
            int(os.environ.get("QDRANT_PORT", "6333")),
            "qdrant",
        )
    )

timeout_seconds = int(os.environ.get("STARTUP_WAIT_TIMEOUT_SECONDS", "60"))
started = time.time()

for host, port, name in services:
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[entrypoint] {name} is reachable on {host}:{port}")
                break
        except OSError:
            if time.time() - started > timeout_seconds:
                print(
                    f"[entrypoint] timeout waiting for {name} on {host}:{port}",
                    file=sys.stderr,
                )
                sys.exit(1)
            time.sleep(2)
PY

python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000
