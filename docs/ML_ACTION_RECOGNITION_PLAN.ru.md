# План action recognition (v1)

[English](./ML_ACTION_RECOGNITION_PLAN.md)

Родительская задача: [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392)
Связано: [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379)

## Таксономия меток v1

- `arrival`
- `departure`
- `possible_feeding`

Расширение (следующая фаза):

- `drinking`
- `aggression`
- `nesting_behavior`

## Спецификация датасета (v1)

Единица разметки: action-segment на track-aligned клипе.

Обязательные поля:

- `video_id`
- `track_id`
- `camera_id`
- `action_label`
- `t_start_ms`
- `t_end_ms`
- `confidence` (уверенность аннотатора)
- `annotator_id`
- `created_at_utc`

Формат для обучения: JSONL + manifest со schema version.

## Гайдлайн разметки

- минимальная длительность сегмента: 300 ms
- overlap допускается только при реально одновременных действиях
- `arrival` и `departure` — boundary events: ставим узкие окна
- `possible_feeding` требует визуального контакта с кормушкой или proxy-сигнала от веса

Согласованность разметки:

- целевой Cohen kappa >= 0.75 на калибровочном срезе
- очередь рассогласований ревьюится еженедельно

## План baseline-моделей

Stage A:

- temporal head поверх текущих track clips (лёгкий baseline)

Stage B:

- clip-model baseline (например семейство VideoMAE/TSN) на curated subset

Stage C:

- сравнение temporal head vs clip model на одинаковых eval-срезах

## Вычислительный бюджет (начальный)

- bootstrap-разметка: 2-3 операторо-дня для seed-набора
- baseline training: 1x GPU 24 GB, до 12 часов на кандидата
- evaluation/ablation: до 6 часов дополнительного GPU-времени

## Интеграционные ограничения

- action head не должен ухудшать throughput detector/classifier
- при недоступности action-модели weak-label API остаётся рабочим
- action output только добавляет сигнал и не блокирует species inference

## Quality bar для первого production trial

- event-based F1 >= 0.70 на валидационных срезах
- boundary delay p95 <= 1.5 s
- false positives per hour <= согласованный порог от операторского baseline
