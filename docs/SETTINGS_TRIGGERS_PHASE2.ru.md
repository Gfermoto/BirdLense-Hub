# Настройки, фаза 2: композируемые триггеры

[English](./SETTINGS_TRIGGERS_PHASE2.md)

## Цель

Вынести конфигурацию триггеров из настроек обработки и заменить текущую единую модель `motion.source` на **независимо включаемые** модули триггеров.

## Продуктовый результат

- Пользователь может включать любую комбинацию источников триггеров чекбоксами.
- У каждого включённого триггера отображаются **только его** настройки.
- Настройки триггеров отвечают на вопрос: «**что** запускает анализ клипа?»
- Настройки процессора/детекции остаются отдельно и отвечают: «**как** анализируется клип?»

## Источники триггеров в объёме работ

- Движение OpenCV
- Frigate (MQTT)
- Датчик движения по MQTT
- Датчик движения по ESPHome
- Весы кормушки по MQTT
- Весы кормушки по ESPHome

## Вне объёма

- Нет редизайна архива или пайплайна обработки клипов вне оркестрации триггеров.
- Нет попытки свести все интеграции к одной универсальной схеме сверх конфигурации триггеров.
- Нет тихого удаления legacy-ключей YAML без миграции.

## Целевой UX

Блок настроек верхнего уровня:

- `Triggers` (Триггеры)
  - переключатель `OpenCV motion`
  - переключатель `Frigate`
  - переключатель `MQTT motion sensor`
  - переключатель `ESPHome motion sensor`
  - переключатель `MQTT feeder scales`
  - переключатель `ESPHome feeder scales`

Для каждого включённого источника:

- показывать только поля, специфичные для источника;
- общие поясняющие тексты держать короткими;
- продвинутые пороги помечать отдельно.

## Целевая форма конфига

Текущая модель:

```yaml
motion:
  source: opencv | frigate | mqtt | esphome
  ...
integrations:
  scales:
    motion_trigger_enabled: false
```

Целевое направление:

```yaml
triggers:
  opencv:
    enabled: true
    check_every_n_frames: 1
    diff_threshold: 18
    min_contour_area: 500
  frigate:
    enabled: true
    camera_filter: []
    label_filter: []
    label_exclude: []
    trigger_on_tracked_object: true
  mqtt_motion:
    enabled: false
    topic: stat/bird_pir/STATE
  esphome_motion:
    enabled: false
    url: http://device.local
    sensor_id: bird_pir
  mqtt_scales:
    enabled: false
    topic_prefix: birdlense/scale
    min_delta_kg: 0.02
    debounce_seconds: 1.5
  esphome_scales:
    enabled: false
    url: http://device.local
    weight_sensor_id: weight_live_internal
    bird_present_sensor_id: bird_present
    tare_button_id: manual_tare
```

Legacy-ключи `motion.*` и `integrations.scales.motion_trigger_*` при загрузке нужно мигрировать вперёд.

## Рефакторинг рuntime

Основные файлы:

- `app/app_config/default_config.yaml`
- `app/app_config/app_config.py`
- `app/processor/src/motion_runtime.py`
- `app/processor/src/motion_detectors/factory.py`
- `app/processor/src/motion_detectors/or_motion.py`
- `app/processor/src/mqtt_runtime.py`
- `app/processor/src/processor_bootstrap.py`
- `app/ui/src/types.ts`
- `app/ui/src/pages/Settings/sections/*`

Необходимые изменения в runtime:

1. Заменить ветвление «один источник» на сборку списка триггеров.
2. Собирать `OrMotionDetector` из N включённых модулей триггеров вместо `primary + additional`.
3. Отвязать подписку Frigate от условия «должен быть основным триггером».
4. Отвязать триггер движения по весам от предположения «основной источник — MQTT».
5. Сохранять provenance, чтобы у финализированных клипов по-прежнему было видно, что запустило обработку.

## Правила миграции

- `motion.source=opencv` → `triggers.opencv.enabled=true`
- `motion.source=frigate` → `triggers.frigate.enabled=true`
- `motion.source=mqtt` → `triggers.mqtt_motion.enabled=true`
- `motion.source=esphome` → `triggers.esphome_motion.enabled=true`
- `integrations.scales.motion_trigger_enabled=true` при источнике MQTT → `triggers.mqtt_scales.enabled=true`
- `integrations.scales.motion_trigger_enabled=true` при источнике ESPHome → `triggers.esphome_scales.enabled=true`

Миграция сначала **аддитивная**, с чтением legacy в одной переходной фазе.

## План тестов

- юнит-тесты миграции конфига;
- юнит-тесты фабрики триггеров со смешанными включёнными источниками;
- юнит-тесты поведения OR-детектора при нескольких активных входах;
- интеграционные тесты для комбинаций MQTT + Frigate + весы;
- тесты UI настроек: чекбоксы и условные поля.

## Порядок поставки

1. Новая схема конфига + совместимость миграции.
2. Рефакторинг сборки триггеров в runtime.
3. Обновление типов UI / контракта API.
4. Замена UI настроек на редактор композируемых триггеров.
5. Удаление legacy-путей UI после стабилизации миграции.
