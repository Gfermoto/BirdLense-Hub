# Processor performance (resolution, VA-API, thresholds)

[Русский](../ru/processor-performance.ru.md)

Guidance for **two-stage** detection when video is heavy (high resolution, VA-API). Goal: align expectations with hardware — slow frames are often **capacity**, not a random bug.

## Levers

| Knob | Role |
|------|------|
| `processor.binary_imgsz` | Downscale before binary detector; smaller → faster, less detail. |
| `processor.frame_processing_warn_ms` | Log threshold for “slow frame”; raising it reduces **noise** in logs without speeding up work. |
| GPU (Orin) | If NVIDIA runtime is missing, CPU fallback is slower — verify with `nvidia-smi` per [RUNBOOKS](./runbooks.md). |
| Light gate / night profiles | Frequent “no YOLO tracks” can interact with exposure — tune profiles before blaming YOLO. |

## Qualitative table (not a SLA)

Exact ms depend on CPU, iGPU, driver, and concurrent load. Use this as **relative** guidance:

| Input resolution (example) | `binary_imgsz` | Expectation |
|------------------------------|------------------|---------------|
| ≤ 1280×720 | 640–960 | Usually comfortable on modest x86. |
| 1920×1080 | 960–1280 | Watch slow-frame logs; tune if sustained warnings. |
| ≥ 2560×1440 | Lower `binary_imgsz` or accept fewer FPS | Often needs strong iGPU/dGPU or aggressive downscale. |

## `frame_processing_warn_ms`

- **Lower** threshold → more warnings; good while **profiling** a new machine.
- **Raise** when warnings are steady but operator accepts latency (avoid “cry wolf” in logs).
- Pair with **config audit** hints from `processor_runtime_stats.json` (see [RUNBOOKS](./runbooks.md) slow-frame section).

## System → Configuration audit (UI)

The hub renders **two kinds** of runtime hints when the snapshot has data: **slow-frame count** vs **detector p95** near your warn threshold. Treat **raising `frame_processing_warn_ms`** as fixing *log noise*; treat **lowering `binary_imgsz` / relaxing the light gate** as addressing *actual latency* (with the recall trade-off for very small birds).

## Trigger path observability (Scale / [#432](https://github.com/Gfermoto/BirdLense-Hub/issues/432))

Runtime snapshot `data/diagnostics/processor_runtime_stats.json` adds **gauges** for grouped triggers (`triggers.*`):

| Gauge | Meaning |
|-------|---------|
| `trigger_cfg_opencv_enabled` | `triggers.opencv.enabled` (1/0) |
| `trigger_cfg_frigate_enabled` | `triggers.frigate.enabled` (1/0) |
| `trigger_cfg_motion_sensor_enabled` | `triggers.motion_sensor.enabled` (1/0) |
| `trigger_cfg_scales_enabled` | `triggers.scales.enabled` (1/0) |
| `trigger_mqtt_configured` | Broker configured via env/YAML (1/0) |
| `trigger_mqtt_live` | MQTT client considers broker reachable (`is_mqtt_live`, 1/0) |
| `trigger_frigate_degraded_no_mqtt` | Frigate enabled **and** MQTT configured **but** not live |
| `trigger_configured_paths_count` | Count from enabled `triggers.*` blocks |
| `trigger_effective_paths_count` | Paths remaining after MQTT-down stripping (`effective_active_trigger_names_for_mqtt_status`) |
| `trigger_degraded_effective_lt_configured` | `1` when MQTT outage hides MQTT-only triggers |

**Counters** when the motion factory falls back to OpenCV-only motion:

- `trigger_motion_factory_frigate_fallback_opencv_total`
- `trigger_motion_factory_opencv_fallback_total`

Refresh happens after motion stack startup and on MQTT connect/disconnect.

## Queues & backpressure {#queues-backpressure}

| Knob / signal | Role |
|---------------|------|
| `mqtt.publish_queue_max` | Bounds outbound MQTT publish queue in `MQTTEventAggregator`. Gauges: `mqtt_outbound_queue_capacity`, `mqtt_outbound_queue_depth`; counters: `mqtt_outbound_drops_total`, `mqtt_outbound_publish_errors_total`. |
| Frigate motion ingest | `motion_trigger_queue_drop_total` when the bounded trigger queue spills (`motion_detectors/frigate_mqtt.py`). |
| Feeder scale writes | `feeder_scale_queue_drops_total` when the scale worker queue is full. |

A unified CPU-heavy job executor is **out of scope** for this note — tracked separately if product wants one queue for all heavy work.

## Code changes

Dynamic throttling / log aggregation for slow frames is **not** implemented here — open a focused issue if product wants it.

Tracking: [BirdLense-Hub#328](https://github.com/Gfermoto/BirdLense-Hub/issues/328).
