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

## Execution backlog (issue-driven)

Статус-мэппинг:

- [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392): протокол/датасет/метрики.
- [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379): выбор модели, обучение, интеграция, rollout.

### Фаза E0 — protocol freeze (#392)

- зафиксировать taxonomy/guideline без разночтений в docs;
- в CI/локали прогонять `make ml-verify-action-labeling` на snapshot payload;
- проверить, что gate падает при намеренно сломанном payload (negative smoke).

DoD E0:

- `make ml-verify-action-labeling ACTION_EVENTS=<fixture>` проходит на валидном fixture;
- negative fixture детерминированно падает;
- в issue #392 приложены команды/логи и ссылка на commit с fixtures.

### Фаза E1 — dataset bootstrap (#392 -> #379)

- собрать seed-набор action segments по текущему протоколу;
- провести калибровочную двойную разметку;
- зафиксировать inter-annotator agreement и disagreements.

DoD E1:

- опубликован manifest seed-набора (объём, классы, распределение);
- Cohen kappa >= 0.75 на калибровочном срезе или оформлен remediation-план;
- в issue есть отчёт о class imbalance и список hard cases.

### Фаза E2 — model candidate benchmark (#379)

- выбрать минимум 2 кандидата (лёгкий temporal head + clip-model baseline);
- обучить/оценить на одинаковых сплитах;
- зафиксировать trade-off quality/latency/VRAM.

DoD E2:

- есть сравнительная таблица метрик (F1, boundary delay p95, FP/hour, latency);
- выбран один production-candidate и один fallback;
- в issue #379 приложены артефакты eval и commit со скриптом benchmark.

### Фаза E3 — hub integration shadow (#379)

- интегрировать inference path без блокировки species pipeline;
- при отсутствии action-модели сохранить weak-label fallback;
- добавить наблюдаемость по action-событиям и отказам.

DoD E3:

- smoke на hub подтверждает, что species flow не деградировал;
- action output появляется в `video_action_events@v1`/API payload без crash-loop;
- зафиксированы kill-switch и rollback шаги.

### Фаза E4 — guarded rollout (#379)

- включить ограниченный rollout (camera/domain slice);
- собрать post-deploy метрики в двух окнах подряд;
- принять решение: расширять rollout или откат.

DoD E4:

- quality bar из этого документа достигнут на двух независимых окнах;
- нет ухудшения throughput detector/classifier;
- в issue #379 приложен финальный go/no-go отчёт.
