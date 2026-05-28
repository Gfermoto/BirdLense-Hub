# Processor OOM (exit 137) — playbook (#510)

## Симптомы

- Контейнер `birdlense` перезапускается, в `docker inspect` exit code **137**
- В логах: `Killed`, нет Python traceback
- После рестарта пропуски записей, пустой timeline

## Быстрая диагностика

1. **Станция → Сервис** — карточка «Каталог и детекция» / YOLO health
2. API (пароль настроек):
   - `GET /api/ui/system/diagnostics/backpressure` — глубины очередей, drops
   - `GET /api/ui/system/diagnostics/processor-runtime` — полный snapshot
3. На сервере: `app/data/diagnostics/processor_runtime_stats.json`

Ключевые метрики:

| Метрика | Риск |
|---------|------|
| `finalize_queue_depth` ≈ max | finalize не успевает — триггеры откладываются |
| `classification_task_drops_total` растёт | classifier перегружен |
| `recording_trigger_deferred_finalize_backpressure_total` | live recording defer |

## Типичные причины на VPS

1. Параллельный **track regen** + live YOLO (мало RAM)
2. `binary_imgsz` / OpenVINO GPU + большой allowlist
3. Слишком низкий `processor.finalize_queue_maxsize` при burst Frigate

## Действия (по приоритету)

1. Остановить массовый regen (UI или дождаться завершения)
2. В `user_config.yaml` (глобально):
   - `processor.classifier_task_queue_maxsize: 4` (меньше очередь)
   - `processor.finalize_queue_maxsize: 2` (дефолт)
   - `processor.track_regen_frame_step: 5` при offline regen
3. Inference: временно `processor.inference_backend: torch` + CPU если GPU OOM
4. Увеличить swap **только** как временную меру; лучше снизить нагрузку

## Профилактика

- `BIRDLENSE_PROCESSOR_STRICT_CONFIG=1` (дефолт) — не старт с битым YAML
- Мониторить `classification_task_drops_total` / сутки
- Не запускать bulk regen в часы пика Frigate

## Проверка после фикса

```bash
curl -s -H "Cookie: ..." http://HOST:8085/api/ui/system/diagnostics/backpressure | jq .
```

`finalize_queue_saturated` не должен быть постоянно `true` > 5 мин.
