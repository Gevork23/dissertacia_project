# Demo Corpus

Актуальное описание demo corpus Фазы 12 находится в:

- `docs/demo/demo-corpus-description.md`

Файловый корпус расположен в:

- `data/demo_corpus/`

Стандартная загрузка:

```bash
python backend/manage.py load_demo_corpus
```

Совместимый alias для прежних инструкций:

```bash
python backend/manage.py load_demo_pairs
```

Demo corpus является синтетическим демонстрационным набором, а не evaluation corpus для расчёта метрик.
