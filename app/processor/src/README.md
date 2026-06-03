# Processor runtime contours

`app/processor/src` intentionally keeps flat imports because the container runs with
`PYTHONPATH=/app:/app/web:/app/processor/src`. Do not physically move anchor modules
unless the old import path stays available through a shim and every external caller is
checked.

Карта каталога процессора (модели, скрипты): [../README.md](../README.md), [../models/README.md](../models/README.md).

## Product contract (standalone-first)

Hub работает **без** Frigate, BirdNET и прочих сайтов. Минимальный контур:

**триггер (OpenCV / вес / MQTT-реле) → YOLO binary + ByteTrack → параллельно ReID, классификатор, поведение → fusion / notify / persist.**

Frigate и BirdNET — **опционально**: доп. триггер, подсказка вида, bias в fusion. Они не подменяют трек, bbox и запись.

### Сценарии пользователя (north star)

| # | Пользователь | Успех |
|---|--------------|--------|
| 1 | Одна камера на кормушке, только OpenCV | Движение → запись → зелёный bbox на птице в Live (во время записи) → TG с узнаваемым кадром → визит с видом |
| 2 | Несколько камер, разное качество | То же per camera; настройки камеры, не зависимость от Frigate |
| 3 | + Frigate в LAN | Frigate может **стартовать** запись или дать hint вида; трек и bbox — **свой YOLO** |
| 4 | + BirdNET | Подсказка вида в fusion; без BirdNET — только классификатор |

**Не цель:** «Frigate видит — значит OK»; synthetic rows без `frames[]`; длинные клипы без YOLO «потому что Frigate шевелится».

## Contours

| Contour | `models/` | Owns | Primary modules | Main dependencies |
| --- | --- | --- | --- |
| `runtime` | — | Process entrypoint, dependency assembly, main motion loop | `main.py`, `processor_bootstrap.py`, `processor_support.py`, `processor_cv2_init.py` | `app_config`, `api`, `media_runtime`, `motion_runtime`, `mqtt_runtime`, `detection_stack`, `recording_session`, `processor_runtime_stats` |
| `media` | [opencv/](../models/opencv/README.md) | Camera/file sources, Go2RTC stream handling, MJPEG preview feeder | `media_runtime.py`, `sources/go2rtc_stream_source.py`, `sources/video_file_source.py`, `sources/streaming_server.py`, `file_test_control.py`, `file_test_paths.py` | `app_config.cameras`, `api`, `processor_support`, `cv2`, `subprocess`, source-local classes |
| `motion` | — | Motion trigger selection and detector implementations | `motion_runtime.py`, `motion_detectors/*`, `frigate_scope.py` | `app_config.trigger_config`, `mqtt_runtime`, `mqtt_aggregator`, `media_runtime`, detector-specific HTTP/MQTT clients |
| `mqtt_integrations` | — | MQTT subscriptions, Frigate/BirdNET/scales event buffers, HA publishes | `mqtt_runtime.py`, `mqtt_aggregator.py`, `mqtt_event_parsers.py`, `mqtt_scale_state.py`, `birdnet_mqtt_confidence.py`, `birdnet_merge_key.py`, `birdnet_fifo_persist.py`, `birdnet_fifo_snapshot.py`, `scale_sample_log.py`, `frigate_bbox.py` | `app_config`, `paho.mqtt`, `processor_runtime_stats`, `motion_detectors.frigate_mqtt`, `motion_detectors.scale_weight_motion` |
| `detection` | [detection/](../models/detection/README.md), [tracker/](../models/tracker/README.md) | YOLO strategy construction, frame processing, light gate, tracking rows | `detection_stack.py`, `detection_strategy.py`, `frame_processor.py`, `interfaces.py`, `light_level_detector.py`, `processor_runtime_profile.py`, `pipeline_policy.py`, `ebird_regional_confidence.py` | `app_config`, `ultralytics.YOLO`, `cv2`, `numpy`, `processor_runtime_stats`, `decision_maker` |
| `fusion` | [fusion/](../models/fusion/README.md) | Accepted/rejected decision rows, cross-source merge, provenance and runtime contracts | `decision_maker.py`, `detection_fusion.py`, `species_normalizer.py`, `fusion_model.py`, `fusion_metrics.py`, `hypothesis_arbitration.py`, `runtime_contract.py`, `decision_outcome.py`, `decision_trace_builder.py`, `processor_provenance.py`, `multi_camera_confidence.py` | `app_config`, detection tracks, MQTT events, `birdnet_merge_key`, `processor_runtime_stats` |
| `reid` | [reid/](../models/reid/README.md) | DINOv2 embeddings at finalize | `reid_runtime.py` | `torch`, `processor.reid.*`, SQLite `reid_embedding` |
| `behavior` | [behavior/](../models/behavior/README.md) | Meta + video behavior labels | `behavior_baseline_runtime.py`, `behavior_video_runtime.py`, `behavior_openvino_runtime.py` | `processor.behavior_recognition`, models/behavior (single canonical video model dir) |
| `recording` | — | One motion recording session, finalize, crops, spectrogram, offline track regen | `recording_session.py`, `recording_finalize.py`, `recording_cleanup_policy.py`, `recording_dataset_crops.py`, `recording_decision_trace_log.py`, `recording_file_gate.py`, `recording_ingest_gate.py`, `recording_mqtt_window.py`, `recording_no_detection_log.py`, `recording_notify_dispatch.py`, `recording_notify_errors.py`, `recording_notify_policy.py`, `recording_notify_preview_log.py`, `recording_post_fusion_rejections.py`, `recording_scales_evidence.py`, `recording_session_cleanup.py`, `recording_spectrogram.py`, `recording_video_response.py`, `track_regenerator.py`, `dataset_saver.py`, `spectrogram.py`, `notify_preview_encode.py`, `fps_tracker.py` | `api`, `app_config`, `media_runtime`, `detection_fusion`, `decision_trace_builder`, `processor_support`, `shared.detection_crop_contract` |
| `hub_client` | — | Processor-to-web API contract | `api.py`, `schemas/events.py` | `API_URL_BASE`, `PROCESSOR_SECRET`, `requests`, `processor_provenance`, `processor_runtime_stats` |
| `diagnostics` | — | Runtime stats, profiles, encoding state, support files | `processor_runtime_stats.py`, `processor_runtime_profile.py`, `encoding_status.py`, `runtime_contract.py` | `DATA_DIR`, `app_config`, callers across runtime/detection/fusion/heartbeat |

## Anchor modules

These modules are stable import names. Other code imports them directly by basename, so
moving them requires a shim at the old path, a targeted import audit, and tests for both
old and new import paths.

| Anchor | Why it is anchored | Current contour |
| --- | --- | --- |
| `main.py` | Docker/entrypoint process target. | `runtime` |
| `processor_bootstrap.py` | Assembles media, MQTT, motion detector, detection stack, and recording session. | `runtime` |
| `processor_support.py` | Logging side effects, heartbeat, restart flag, data/output paths. | `runtime` / `diagnostics` |
| `api.py` | Processor -> web HTTP client; used by runtime, recording, heartbeat. | `hub_client` |
| `detection_stack.py` | Shared factory for live processor and track regeneration. | `detection` |
| `detection_strategy.py` | YOLO model ownership and `DetectionResult` shape. | `detection` |
| `interfaces.py` | Protocol used by `FrameProcessor` and tests without loading YOLO weights. | `detection` |
| `frame_processor.py` | Tracking state shape consumed by `DecisionMaker`, finalize, and regen. | `detection` |
| `decision_maker.py` | Decision row contract and stop-recording policy. | `fusion` |
| `detection_fusion.py` | Cross-source merge contract for persisted detections. | `fusion` |
| `species_normalizer.py` | Canonical species-name helpers shared by fusion and arbitration. | `fusion` |
| `mqtt_aggregator.py` | Long-lived MQTT event buffer and publish surface. | `mqtt_integrations` |
| `recording_session.py` | Orchestrates `motion -> record -> finalize` for live runtime. | `recording` |
| `recording_finalize.py` | Persists/deletes session output and calls hub API. | `recording` |
| `track_regenerator.py` | Offline video reprocessing path used from web/system jobs. | `recording` |

`fusion_*` modules (`fusion_model.py`, `fusion_metrics.py`) are also treated as anchors
because their names describe the current flat fusion API and are imported by tests and
nearby merge code.

## Safe decomposition rules

1. Add new logic in small contour-local modules first, then import it from the anchor.
2. Keep the anchor file as the compatibility surface until call sites and tests are
   migrated deliberately.
3. Do not introduce package-relative imports in flat modules unless the whole execution
   path is tested under the container `PYTHONPATH`.
4. For detection changes, prefer tests that avoid loading YOLO weights; use
   `DetectionStrategyProtocol` and stubs where possible.
5. For recording/fusion changes, assert the persisted detection row shape and rejected
   decision rows, not only the happy-path species name.
6. For MQTT/motion changes, test parser/filter helpers separately from broker/network
   behavior.

## Current runtime flow

1. `main.py` configures OpenCV/FFmpeg logging, starts heartbeat, parses args.
2. `processor_bootstrap.build_processor_run_context()` creates `API`, media sources,
   MQTT aggregator, motion detector, detection stack, and `MotionRecordingSession`.
3. `run_motion_loop()` waits for a motion trigger and calls `session.run()`.
4. `recording_session.py` captures frames, runs `FrameProcessor`, updates
   `DecisionMaker`, and collects runtime stats.
5. `recording_finalize.py` merges YOLO decisions with MQTT events, writes crops and
   spectrogram metadata, posts video/detection data to web, and publishes MQTT output.
