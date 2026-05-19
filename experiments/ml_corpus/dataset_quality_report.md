# Dataset quality report

## Назначение

Корпус предназначен для supervised ML-экспериментов по классификации значимости изменений и не заменяет production rule-based significance layer.

## Источники данных

- `significance_results`: 13
- `evaluation_corpus`: 13
- `annotation_examples`: 0
- `curated_synthetic`: 160
- `real_world_weak`: 49

## Размер корпуса

- Всего examples: 202
- Strict supervised examples: 153
- Weak examples: 49
- Train size: 110
- Test size: 31
- Validation size: 12

## Распределение labels

- critical: 72
- editorial: 36
- important: 53
- informational: 41

## Распределение semantic types

- editorial: 15
- obligation: 14
- procedure: 13
- refusal_ground_change: 10
- responsibility_change: 10
- deadline_change: 10
- obligation_change: 10
- reference_change: 10
- mixed_change: 10
- contact_or_channel_change: 10
- clarification_change: 10
- procedure_change: 10
- document_list_change: 10
- payment_or_fee_change: 10
- eligibility_change: 10
- terminology_change: 10
- formatting_or_editorial_change: 10
- deadline: 9
- document: 7
- responsibility: 1
- refusal: 1
- informational: 1
- structure: 1

## Распределение operation types

- modified: 135
- added: 56
- moved: 11

## Средние длины текстов

- Средняя длина old_text: 64.14
- Средняя длина new_text: 91.84
- Средняя длина combined_text: 156.71

## Доли источников

- Gold: 0.0644
- Synthetic: 0.6931
- Weak: 0.2426

## Leakage checks

- Pair overlap train/test: []

## Ограничения

- Curated synthetic examples являются controlled supervised corpus и не являются real-world legal benchmark.
- Weak real-world examples вынесены в отдельный inference layer и не используются в strict train/test split.
- Annotation Studio examples подключаются как optional high-priority gold source и зависят от наличия локальной базы или export artifacts.

## Пригодность для scikit-learn

Корпус содержит текстовые поля, бинарные lexical features, numeric length features и устойчивые target columns (`y_significance`, `y_high_priority`, `y_semantic_type`), что делает его пригодным для классических supervised ML baseline-экспериментов.
