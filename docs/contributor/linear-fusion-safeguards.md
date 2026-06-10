# Linear pipeline — fusion safeguards (#622)

[Русский](../ru/linear-fusion-safeguards.ru.md) · [Architecture](./architecture.md)

## Product profiles

| Profile | Default | Frigate/BirdNET role | Frigate salvage |
|---------|---------|----------------------|-----------------|
| **Standalone-first** (default) | `processor.pipeline_mode: linear` | Hints in fusion only; no synthetic persist rows | Off (`detection.frigate_trigger_review_salvage_enabled: false`) |
| **Frigate-site** | Same linear pipeline | Frigate may **trigger** recording; species hint in fusion | Opt-in: `video.cameras[].tuning_role: frigate_site` → `processor.camera_tuning_by_role.frigate_site.frigate_trigger_review_salvage_enabled: true` |

Hub YOLO + ByteTrack remain the **primary** persist drivers in both profiles.

## `linear_skip_*` matrix (`linear_pipeline.py`)

| Helper | When True (skip) | Still runs in linear |
|--------|------------------|----------------------|
| `linear_skip_legacy_fusion_safeguards` | `pipeline_mode` is linear/simple | detect-first restore, weak salvage (when configured), bbox contract, track_first gate, timeline remap |
| `linear_skip_frigate_salvage_paths` | Linear **and** no global/role Frigate salvage opt-in | Frigate salvage when opted in |

### Legacy safeguards skipped in linear

- `collect_post_fusion_rejections` — no second-guess of accepted pre-fusion rows
- `yolo_core_anchor_enabled` — forced off (no fusion-drop anchor restore)

### Safeguards kept in linear

- `restore_detect_first_persist_rows` — detect-first contract (#601)
- Weak YOLO salvage when `detect_first_confirmed` + `yolo_frames_with_tracks` (`weak_salvage_linear_ok`)
- Frigate trigger review salvage when `frigate_salvage_opted_in()` (global or `frigate_site` role)

## Regression checklist

- [ ] `make test-processor-light` green
- [ ] `test_recording_finalize*`, `test_detect_first*`, `test_linear_pipeline` green
- [ ] `yolo_frames_with_tracks / yolo_frames_ran ≥ 0.15` on field clips
- [ ] `fusion_drop` rate stable vs 7d baseline
- [ ] Frigate-only feeders: assign `tuning_role: frigate_site` before enabling salvage
