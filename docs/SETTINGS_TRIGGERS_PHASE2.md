# Settings Phase 2: Composable Triggers

## Goal
Separate trigger configuration from processing configuration and replace the current single `motion.source` model with independently enabled trigger modules.

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

## Target Config Shape
Current model:

```yaml
motion:
  source: opencv | frigate | mqtt | esphome
  ...
integrations:
  scales:
    motion_trigger_enabled: false
```

Target direction:

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

Legacy `motion.*` and `integrations.scales.motion_trigger_*` keys should be migrated forward on load.

## Runtime Refactor
Primary files:

- `app/app_config/default_config.yaml`
- `app/app_config/app_config.py`
- `app/processor/src/motion_runtime.py`
- `app/processor/src/motion_detectors/factory.py`
- `app/processor/src/motion_detectors/or_motion.py`
- `app/processor/src/mqtt_runtime.py`
- `app/processor/src/processor_bootstrap.py`
- `app/ui/src/types.ts`
- `app/ui/src/pages/Settings/sections/*`

Required runtime changes:

1. Replace single-source branching with trigger list assembly.
2. Build `OrMotionDetector` from N enabled trigger modules instead of `primary + additional`.
3. Decouple Frigate subscription from "must be primary trigger".
4. Decouple scale motion trigger from MQTT-primary assumption.
5. Preserve provenance so finalized clips still record what triggered processing.

## Migration Rules
- `motion.source=opencv` -> `triggers.opencv.enabled=true`
- `motion.source=frigate` -> `triggers.frigate.enabled=true`
- `motion.source=mqtt` -> `triggers.mqtt_motion.enabled=true`
- `motion.source=esphome` -> `triggers.esphome_motion.enabled=true`
- `integrations.scales.motion_trigger_enabled=true` with MQTT source -> `triggers.mqtt_scales.enabled=true`
- `integrations.scales.motion_trigger_enabled=true` with ESPHome source -> `triggers.esphome_scales.enabled=true`

Migration should be additive first, with legacy read-compat during one transition phase.

## Test Plan
- unit tests for config migration
- unit tests for trigger factory with mixed enabled sources
- unit tests for OR detector behavior with multiple active inputs
- integration tests for MQTT + Frigate + scales combinations
- settings UI tests for checkbox rendering and conditional fields

## Delivery Order
1. Add new config schema + migration compatibility.
2. Refactor runtime trigger assembly.
3. Update UI types/API contract.
4. Replace settings UI with composable trigger editor.
5. Remove legacy UI paths once migration is stable.
