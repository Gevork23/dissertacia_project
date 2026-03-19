# Phase 1 bundle

## Replace these files in the project root
- README.md
- ROADMAP.md
- TASKS.md
- ARCHITECTURE.md
- PROJECT_SCOPE.md
- docker-compose.yml
- setup.cfg

## Replace these files under backend/
- backend/config/settings.py
- backend/entrypoint.sh
- backend/setup.cfg
- backend/documents/tests.py

## Replace these files under infra/
- infra/.env.example

## Replace these files under scripts/
- scripts/lint.sh
- scripts/test.sh

## Replace these files under docs/
- docs/notes.md

## Delete from the project
- backend/config/logging.py
- backend/db.sqlite3
- backend/logs/
- backend/media/
- infra/.env
- .git/
- all __pycache__/ directories

## Verification
```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
python manage.py check
cd ..
DB_ENGINE=sqlite ./scripts/test.sh
./scripts/lint.sh
```
