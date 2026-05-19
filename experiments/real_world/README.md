# Real-world Regression Suite

Каталог `experiments/real_world/` хранит воспроизводимый weak-labeled regression-контур для проверки устойчивости гибридного pipeline на более широком наборе пар документов, чем demo corpus и малый gold evaluation corpus.

Состав каталога:

- `evaluate_real_world.py` — offline-скрипт запуска suite из корня репозитория;
- `real_world_summary.json` — сводный JSON-отчёт;
- `real_world_pair_results.csv` — результаты по каждой паре;
- `real_world_trace.csv` — детализированная трасса по изменениям;
- `real_world_stage_summary.csv` — агрегированная сводка по стадиям.

Запуск:

```bash
python experiments/real_world/evaluate_real_world.py
```

Альтернативный запуск через Django command:

```bash
python backend/manage.py run_real_world_regression
```

Корпус discovery:

1. `regression/ruslawod_test_cases.json` как weak real-world source;
2. `data/demo_corpus/` как fallback demonstration regression;
3. `data/manual_samples/` как минимальный аварийный fallback.

Suite не пересчитывает experiment artifacts в runtime UI и не претендует на strict accuracy без ручной gold-разметки.
