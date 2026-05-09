# Phase 23 Manifest

Архив содержит артефакты Фазы 23 для переноса в локальный проект.

## Состав

- `docs/thesis/chapter-1-draft.md` — черновик главы 1.
- `docs/thesis/chapter-1-source-map.md` — карта источников главы 1.
- `docs/thesis/chapter-1-review-notes.md` — заметки для проверки и будущей редакции.
- `docs/thesis/chapter-1-figures-and-tables-map.md` — карта таблиц и рисунков главы 1.

## Как применить локально

1. Перейти в корень локального проекта.
2. Распаковать архив так, чтобы файлы попали в `docs/thesis/`.
3. Проверить:

```bash
git status --short
python scripts/validate_evaluation_corpus.py
python experiments/final/aggregate_experiment_results.py
python experiments/final_visuals/build_final_figures.py
```

Backend-проверки запускать только при активированном окружении с Django-зависимостями:

```bash
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test
bash scripts/lint.sh
bash scripts/demo_smoke.sh
```

## Важное примечание

Фаза 23 является документационной. Архив не меняет backend, алгоритмы, evaluation corpus и миграции.
