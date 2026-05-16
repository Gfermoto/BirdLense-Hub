# Настройки, фаза 2: композируемые триггеры

[English](./SETTINGS_TRIGGERS_PHASE2.md)

## Цель

Разделить конфигурацию триггеров и настроек обработки: **каноническая модель** — независимо включаемые блоки **`triggers.*`**, без единого переключателя **`motion.source`**.

## Статус (май 2026)

- **`default_config.yaml`** задаёт только **`triggers.*`** для OpenCV / Frigate / датчика / весового триггера; оборудование весов остаётся в **`integrations.scales.*`**.
- Устаревший блок **`motion:`** в `user_config.yaml` при загрузке переносится в **`triggers`** и удаляется (`migrate_legacy_motion_block`); после merge default+user срабатывает **`fold_legacy_motion_out_of_merged_config`** (`app/app_config/trigger_config.py`).
- **`get_effective_trigger_config`** читает только **`triggers.*`**. Для топика Frigate сохранён fallback через **`migrate_legacy_trigger_topics`** (**`mqtt.frigate_topic`** → **`triggers.frigate.topic`**). Чтобы Frigate участвовал в записи, нужно **`triggers.frigate.enabled: true`** (одного брокера MQTT недостаточно).

## Продуктовый результат

- Пользователь включает комбинации триггеров чекбоксами (**Настройки → Захват и кормушка**).
- У каждого включённого блока только свои поля.
- Вопрос триггеров: «**что** запускает анализ клипа?». Вопрос процессора: «**как** анализируется клип?».

## Источники триггеров в объёме работ

- OpenCV motion
- Frigate (MQTT)
- Датчик по MQTT или ESPHome (`triggers.motion_sensor`)
- Весовой триггер (`triggers.scales` + `integrations.scales`)

## Вне объёма

- Редизайн архива/клип-пайплайна не входит сюда.
- Нельзя удалять ключи пользователя без миграции: legacy **`motion:`** сворачивается при загрузке.

## Целевой UX

См. чекбоксы OpenCV / Frigate / MQTT motion / ESP motion / scales в блоке «Захват и кормушка».

## Каноническая форма конфига (в поставке)

```yaml
triggers:
  opencv:
    enabled: true
    check_every_n_frames: 1
    diff_threshold: 18
    min_contour_area: 240
  frigate:
    enabled: false
    topic: "frigate/events"
    camera_filter: []
    label_filter: []
    label_exclude: []
    trigger_on_tracked_object: true
    min_trigger_score: 0.50
    min_trigger_score_by_camera: {}
  motion_sensor:
    enabled: false
    source: mqtt  # mqtt | esphome
    mqtt_topic: ""
    esphome_url: ""
    esphome_sensor_id: ""
  scales:
    enabled: false
    source: mqtt
    motion_trigger_min_delta_kg: 0.02
    motion_trigger_debounce_seconds: 1.5
integrations:
  scales:
    enabled: false
    source: mqtt
    motion_trigger_enabled: false  # legacy — по-прежнему влияет на эффективный триггер весов
```

Старые установки могли сохранять верхний уровень **`motion:`**; при следующей загрузке он разворачивается в **`triggers`** и исчезает из merged-снимка.

## Правила миграции (реализовано)

- Пары полей см. **`_fold_motion_fields_into_triggers`** / **`migrate_legacy_motion_block`** (`trigger_config.py`).
- По **`motion.source`** при сворачивании выставляются соответствующие **`enabled`** (opencv/frigate/motion_sensor).

## Основные файлы

- `app/app_config/default_config.yaml`
- `app/app_config/app_config.py`
- `app/app_config/trigger_config.py`
- `app/processor/src/motion_runtime.py`
- `app/processor/src/motion_detectors/factory.py`
- `app/processor/src/motion_detectors/or_motion.py`
- `app/processor/src/mqtt_runtime.py`
- `app/processor/src/processor_bootstrap.py`
- `app/ui/src/types.ts`
- `app/ui/src/pages/Settings/sections/*`

## Поведение runtime (после рефакторинга)

1. **`OrMotionDetector`** собирается из активных источников, которые возвращает **`get_effective_trigger_config`** (OpenCV, Frigate aggregator, MQTT/ESPHome датчик, веса).
2. Frigate зависит от **`triggers.frigate.enabled`** и **`mqtt.broker`**, без **`motion.source`**.
3. В provenance сохраняется сводка **`get_active_trigger_names`**.

## Проверка

- Автотесты: **`app/web/tests/test_legacy_config_migration.py`**, **`test_service_layer_slice_293.py`**, **`processor/tests/test_mqtt_frigate_filters.py`**. Тесты aggregator с MQTT требуют **`paho-mqtt`**.

## Историческая справка

Черновые имена (**`mqtt_motion`**, **`esphome_scales`**) заменены схемой **`triggers.motion_sensor`** (`source: mqtt | esphome`) и блоком **`integrations.scales`** + **`triggers.scales`** для параметров весового триггера.
