# Производительность процессора (разрешение, VA-API, пороги)

[English](../user/processor-performance.md)

Ориентиры для тяжёлого видео: высокое разрешение, VA-API. Цель — не путать **нехватку FPS** со «случайным багом».

## Рычаги

| Параметр | Зачем |
|----------|--------|
| `processor.binary_imgsz` | Даунскейл до binary-детектора; меньше → быстрее, меньше деталей. |
| `processor.frame_processing_warn_ms` | Порог предупреждения «медленный кадр»; **поднять** — меньше шума в логах. |
| GPU / VA-API | Без железа/драйверов будет CPU и дольше — см. [RUNBOOKS](./runbooks.ru.md). |
| Light gate / ночные профили | Частые «no YOLO tracks» могут быть от экспозиции — сначала профили. |

## Качественная таблица

| Разрешение (пример) | `binary_imgsz` | Ожидание |
|---------------------|----------------|----------|
| ≤ 1280×720 | 640–960 | Обычно ок на скромном x86. |
| 1920×1080 | 960–1280 | Следить за slow-frame в логах. |
| ≥ 2560×1440 | Уменьшить `binary_imgsz` или смириться с меньшим FPS | Часто нужен сильный GPU или агрессивный даунскейл. |

## `frame_processing_warn_ms`

Ниже порог — больше предупреждений (удобно при **настройке** нового хоста). Выше — меньше «крика» в логах при приемлемой задержке.

## System → Configuration audit (UI)

В подсказках рантайма два смысла: **счётчик медленных кадров** и **p95 детектора** около порога. Поднять `frame_processing_warn_ms` — про *шум в логах*; уменьшить `binary_imgsz` / ослабить light gate — про *реальную задержку* (с компромиссом по recall мелких птиц).

## Наблюдаемость триггеров (Scale / [#432](https://github.com/Gfermoto/BirdLense-Hub/issues/432))

Снимок `data/diagnostics/processor_runtime_stats.json` дополняется **gauge** для сгруппированных триггеров (`triggers.*`): включённые ветки, живость MQTT, деградация Frigate при отключённом брокере, число сконфигурированных vs эффективных путей после выкидывания MQTT-зависимых триггеров.

**Счётчики** при fallback фабрики motion на один только OpenCV: `trigger_motion_factory_frigate_fallback_opencv_total`, `trigger_motion_factory_opencv_fallback_total`. Обновление gauge — после сборки motion-стека и при connect/disconnect MQTT.

Полная таблица имён — в [PROCESSOR_PERFORMANCE.md](../user/processor-performance.md) (EN).

## Очереди и backpressure {#queues-backpressure}

- **`mqtt.publish_queue_max`** — лимит исходящей очереди публикаций; см. gauge `mqtt_outbound_*` и счётчики `mqtt_outbound_drops_total` / `mqtt_outbound_publish_errors_total`.
- Очередь событий Frigate → motion: `motion_trigger_queue_drop_total`.
- Очередь записи весов: `feeder_scale_queue_drops_total`.

Единый исполнитель «тяжёлых задач» для всего процессора — вне этого документа; при необходимости — отдельное ишью.

Динамический троттлинг / агрегация логов в коде здесь не описаны — отдельное ишью.

Трекинг: [BirdLense-Hub#328](https://github.com/Gfermoto/BirdLense-Hub/issues/328).
