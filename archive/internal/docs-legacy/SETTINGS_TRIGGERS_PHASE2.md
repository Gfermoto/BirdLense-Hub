# Settings Phase 2: Composable Triggers

[Русский](./SETTINGS_TRIGGERS_PHASE2.ru.md)

## Goal

Separate trigger configuration from processing configuration using **one composable schema**. The obsolete single-switch **`motion.source`** layout is superseded by independently enabled **`triggers.*`** blocks.

## Status (May 2026)

- **`default_config.yaml`** defines **`triggers.*`** only for motion/OpenCV/Frigate/sensors/scales trigger toggles (feeder scales hardware remains under **`integrations.scales.*`**).
- Legacy **`motion:`** in `user_config.yaml` is rewritten into **`triggers`** when the Hub loads (`migrate_legacy_motion_block`). After merging default + user, **`fold_legacy_motion_out_of_merged_config`** folds any stray **`motion:`** (`app/app_config/trigger_config.py`).
- **`get_effective_trigger_config`** reads **`triggers.*`** only. The Frigate MQTT topic also honours **`mqtt.frigate_topic`** (migrated into **`triggers.frigate.topic`**). **`triggers.frigate.enabled`** must be **true** to use Frigate as a trigger (the broker alone does not auto-enable Frigate).

## Product Outcome
- User can enable any combination of trigger sources with checkboxes.
- Each enabled trigger exposes only its own settings.
- Trigger settings answer one question: "what starts clip analysis?"
- Processor/detection settings stay separate and answer: "how is the clip analyzed?"

## Trigger Sources In Scope
- OpenCV motion
- Frigate (MQTT)
- Motion sensor over MQTT
- Motion sensor over ESPHome
- Feeder scales over MQTT
- Feeder scales over ESPHome

## Non-Goals
- No redesign of archive or clip-processing pipeline outside trigger orchestration.
- No attempt to merge all integrations into one generic schema beyond trigger configuration.
- No silent removal of legacy YAML keys without migration.

## Canonical config shape (shipped)

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
    motion_trigger_enabled: false  # legacy; effective trigger still respects triggers.scales + this flag
```

Old installs could still persist a top-level **`motion:`** block; on load those keys populate **`triggers`** and **`motion`** is dropped from the merged snapshot after fold.

## Target UX

Top-level settings block:

- `Triggers`
  - `OpenCV motion` toggle
  - `Frigate` toggle
  - `MQTT motion sensor` toggle
  - `ESPHome motion sensor` toggle
  - `MQTT feeder scales` toggle
  - `ESPHome feeder scales` toggle

For every enabled source:
- show only source-specific fields
- keep shared explanatory copy short
- mark advanced thresholds separately

## Migration rules (implemented)

- Any remaining top-level **`motion:`** block after default+user merge is folded into **`triggers.*`** and removed from the merged tree (`fold_legacy_motion_out_of_merged_config`).
- Persisted user files are rewritten when **`migrate_legacy_motion_block`** runs (`app_config.py` loader).
- Field map (examples): **`frigate_*`** → **`triggers.frigate.*`**, **`opencv_*` intervals / thresholds** → **`triggers.opencv.*`**, **`mqtt_topic` / `esphome_*` for PIR** → **`triggers.motion_sensor.*`**.
- During fold, **`motion.source`** still forces the implied trigger flags (`opencv`, `frigate`, `mqtt`, `esphome` paths) so old configs remain usable until the user saves a clean file.
- **`integrations.scales.motion_trigger_enabled`** continues to influence **`triggers.scales.enabled`** defaults inside **`get_effective_trigger_config`**.

## Primary files (touchpoints)

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


## Runtime behaviour (post-refactor)

1. `OrMotionDetector` composes whatever trigger modules **`get_effective_trigger_config`** exposes (OpenCV detector, MQTT Frigate path, MQTT/ESPHome motion sensors, scale-weight pending callbacks).
2. Frigate ingestion depends solely on **`triggers.frigate.enabled`** plus **`mqtt.broker`** wiring — **`motion.source` is gone from defaults**.
3. Provenance persists active trigger summaries via **`get_active_trigger_names`**.

## Verification

- Regression coverage: **`app/web/tests/test_legacy_config_migration.py`**, **`app/web/tests/test_service_layer_slice_293.py`**, **`app/processor/tests/test_mqtt_frigate_filters.py`**. Full Frigate aggregator tests (**`test_mqtt_frigate_geometry_trigger.py`**, **`test_mqtt_frigate_event_queue.py`**) expect **`paho-mqtt`** in the processor toolchain.

## Historical note

Older drafts referenced placeholder keys such as **`mqtt_motion`** / **`esphome_scales`**. The shipped schema uses **`triggers.motion_sensor`** (with **`source: mqtt`** or **`esphome`**) and keeps feeder hardware under **`integrations.scales.*`** with **`triggers.scales`** for motion-weight gating parameters.