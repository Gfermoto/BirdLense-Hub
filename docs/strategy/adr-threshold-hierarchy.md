# ADR: Threshold hierarchy (global → role → camera)

## Status

Accepted (2026-06-12)

## Context

BirdLense accumulated duplicate confidence keys (`min_confidence_binary`, `min_confidence_binary_bird`, `openvino_min_confidence_binary_bird`, `min_confidence_to_process`, scoring thresholds, night `adaptive_profiles`, per-camera overrides). They override each other unpredictably:

- Night adaptive on prod raised bird/process thresholds to **0.28**, wiping weak OpenVINO boxes (0.04–0.12) even when `feeder_far` role preset targeted **0.05–0.08**.
- `openvino_min_confidence_binary_bird` was applied as a **floor raise** in some paths; for distant cameras it must be **`min(role, cap)`**.
- `feeder_close` (BirdBox) lacked explicit OpenVINO caps while `feeder_far` (Forest) was patched ad hoc.
- Merge logic was scattered: `recording_session._camera_processor_overrides`, `frame_processor` profile overlay, `detection_strategy`, `decision_maker`, `scoring_engine`.

## Decision

1. **Canonical module:** `app/processor/src/threshold_resolution.py`
   - `resolve_effective_threshold(app_config, key, camera_id=..., inference_backend=..., adaptive_overrides=...)`
   - `build_camera_processor_overrides(app_config, camera_id)`
   - `merge_adaptive_profile_overrides(camera_overrides, adaptive_overrides)`

2. **Precedence (most specific wins for non-acceptance keys):**

   ```
   global (default_config + user_config merge)
     → processor.camera_tuning_by_role.<tuning_role>
     → detection.camera_overrides.<id> (legacy)
     → processor.camera_overrides.<id>
   ```

   At frame runtime, **adaptive profile** (night) merges under camera/role:
   - **Acceptance keys** (`min_confidence_*`, `openvino_*` caps, `min_confidence_to_process`, scoring floors): `effective = min(role_or_camera, adaptive)` — adaptive **cannot raise** above role/camera.
   - **Other keys** (geometry, light_gate, `min_box_size_px`): camera/role **wins** over adaptive (unchanged behaviour).

3. **OpenVINO caps:** For Bird/binary acceptance, `effective = min(base, openvino_min_confidence_binary_bird)` when backend is OpenVINO. Role may set a **lower** `openvino_min_*` than global.

4. **Role presets in `default_config.yaml`:**
   - `feeder_close` — close-up / BirdBox: explicit `openvino_min_confidence_binary_bird`, `openvino_binary_track_ultralytics_conf`.
   - `feeder_far` — overview / Forest: weak distant boxes (existing).

5. **No `frigate_standalone_when_no_yolo`** — out of scope; Frigate remains hint/salvage opt-in only.

## Consequences

- Prod `user_config` night overrides at 0.28 no longer block Forest/BirdBox when role presets are lower.
- Operators should **remove duplicate global confidence keys** from prod `user_config` that fight role presets (see cleanup list in deploy notes).
- `activity_log` `recording_session_summary` persistence still separate (currently 0 rows on VPS — forensics via container logs).

## Related

- `docs/strategy/adr-classifier-hints-only.md` (linear pipeline, no Frigate-as-primary)
- `processor.camera_tuning_by_role` + `video.cameras[].tuning_role`
