# План action recognition (v1)

[English](./ML_ACTION_RECOGNITION_PLAN.md)

Родительская задача: [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392) · runtime: [#416](https://github.com/Gfermoto/BirdLense-Hub/issues/416)
Связано: [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379)

## Таксономия меток v1

Метки поведения ориентированы на модель и обучение (например: `feeding`, `alert`, `idle`).
Legacy weak-label метки (`arrival`, `departure`, `possible_feeding`) архивированы и убраны из runtime API.

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
- метка должна подтверждаться визуальным сигналом в клипе
- не использовать pseudo/proxy-only метки без обучаемого визуального признака

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
- при недоступности action-модели weak-label fallback в runtime API не используется
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
- архивировать legacy weak-label/gate контур и оставить только model/runtime behavior flow.

DoD E0:

- legacy gate скрипты/фикстуры удалены из runtime-контура;
- docs и smoke-потоки ссылаются только на текущий model/runtime behavior path.

### Фаза E1 — dataset bootstrap (#392 -> #379)

- собрать seed-набор action segments по текущему протоколу;
- провести калибровочную двойную разметку;
- зафиксировать inter-annotator agreement и disagreements.

DoD E1:

- опубликован manifest seed-набора (объём, классы, распределение);
- Cohen kappa >= 0.75 на калибровочном срезе или оформлен remediation-план;
- в issue есть отчёт о class imbalance и список hard cases.

Команды:

- Legacy-команды удалены после завершения миграции.

### Фаза E2 — model candidate benchmark (#379)

- выбрать минимум 2 кандидата (лёгкий temporal head + clip-model baseline);
- обучить/оценить на одинаковых сплитах;
- зафиксировать trade-off quality/latency/VRAM.

DoD E2:

- есть сравнительная таблица метрик (F1, boundary delay p95, FP/hour, latency);
- выбран один production-candidate и один fallback;
- в issue #379 приложены артефакты eval и commit со скриптом benchmark.

Команда:

- Legacy-команда удалена после завершения миграции.

### Фаза E3 — hub integration shadow (#379)

- интегрировать inference path без блокировки species pipeline;
- добавить наблюдаемость по выходам behavior-модели и отказам.

DoD E3:

- smoke на hub подтверждает, что species flow не деградировал;
- behavior output появляется в `GET /api/ui/videos/:id` payload без crash-loop;
- зафиксированы kill-switch и rollback шаги.

Команда:

- Legacy-команда удалена после завершения миграции.

### Фаза E4 — guarded rollout (#379)

- включить ограниченный rollout (camera/domain slice);
- собрать post-deploy метрики в двух окнах подряд;
- принять решение: расширять rollout или откат.

DoD E4:

- quality bar из этого документа достигнут на двух независимых окнах;
- нет ухудшения throughput detector/classifier;
- в issue #379 приложен финальный go/no-go отчёт.

## Hub #416 — behavior baseline runtime (реализовано)

Чеклист по issue [#416](https://github.com/Gfermoto/BirdLense-Hub/issues/416):

- **БД**: `video.behavior_label`, `video.behavior_confidence` (миграция), запись из finalize процессора.
- **Процессор**: загрузка `behavior_logistic_export@v1.json`, softmax, **лимит** числа детекций в meta-features (по умолчанию 50).
- **API**: `GET /api/ui/videos/:id` отдаёт `behavior_*`; `PATCH` — contributor/admin, ручная правка/сброс (OpenAPI + UI).
- **Скрипты** (операции):
  - `scripts/ml_behavior_export_video_labels.py --db … --out ….jsonl` — выгрузка подтверждённых меток из SQLite для feedback в обучение.
  - `scripts/ml_behavior_runtime_profile.py --export … --out ….json` — микробенчмарк латентности forward (numpy softmax).

Дальше (вне закрытия #416): OpenVINO/ONNX, полный operator loop → export, расширенный canary.
