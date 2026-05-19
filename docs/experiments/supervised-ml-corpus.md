# Supervised ML corpus

## Назначение

Фаза 6.1 добавляет в проект отдельный supervised ML corpus для офлайн-экспериментов по классификации значимости изменений. Этот слой нужен потому, что исходный labeled corpus Фазы 6 слишком мал для устойчивого train/test режима.

Корпус не заменяет production rule-based significance layer и не влияет на runtime backend.

## Источники данных

Используются несколько слоев:

1. `experiments/significance/significance_results.csv`
2. `data/evaluation_corpus/*/annotation.json`
3. `GoldChangeAnnotation` или export artifacts Annotation Studio, если они доступны
4. curated synthetic supervised examples
5. `experiments/real_world/real_world_trace.csv` только как weak inference layer

## Артефакты

После сборки создаются:

- `experiments/ml_corpus/full_dataset.csv`
- `experiments/ml_corpus/train.csv`
- `experiments/ml_corpus/validation.csv`
- `experiments/ml_corpus/test.csv`
- `experiments/ml_corpus/weak_inference_dataset.csv`
- `experiments/ml_corpus/dataset_profile.json`
- `experiments/ml_corpus/split_metadata.json`
- `experiments/ml_corpus/feature_schema.json`
- `experiments/ml_corpus/label_distribution.csv`
- `experiments/ml_corpus/dataset_quality_report.md`
- `experiments/ml_corpus/figures/*.png`

## Labels и split

Основной target:

- `y_significance = critical | important | informational | editorial`

Дополнительные targets:

- `y_high_priority`
- `y_semantic_type`

Split выполняется с `random_state = 42` и целевым `test_size = 0.2`. Если есть `pair_id`, используется group-aware split для снижения leakage.

Weak examples не включаются в strict train/test.

## Как запустить

```bash
python experiments/ml_corpus/build_supervised_corpus.py
python experiments/ml_corpus/train_baseline_models.py
python backend/manage.py build_supervised_ml_corpus
python backend/manage.py train_baseline_ml_models
```

## Использование через pandas

```python
import pandas as pd

train_df = pd.read_csv("experiments/ml_corpus/train.csv")
test_df = pd.read_csv("experiments/ml_corpus/test.csv")
```

## Ограничения

- curated synthetic examples являются controlled synthetic corpus и не равны real-world legal benchmark;
- weak real-world слой хранится отдельно и не рассматривается как strict training labels;
- annotation-derived gold examples зависят от наличия локальной базы или export artifacts.

## Связь с Фазой 6

Этот корпус усиливает ML / Hybrid significance experiment и дает ему воспроизводимую train/test основу для дальнейших scikit-learn baseline experiments.
