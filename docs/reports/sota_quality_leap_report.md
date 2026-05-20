# SOTA Quality Leap Report (2026-05-20)

## Executive summary

Radical FP suppression + artifact hygiene for production NVR-grade quality.

| Metric (offline validation) | Before filters @0.28 | After `DetectionQualityPipeline` |
|------------------------------|----------------------|----------------------------------|
| `094147` accepted frames | 25 | **7** (−72%) |
| `094147` bird proxy retained | 7 | **7** (100%) |
| `093950` giant phantom | 5 | **0** |
| `050815` clear bird | 37 | **37** (100%) |

Session-level prod (post hotfix 0.28): avg `yolo_accepted` dropped ~17× vs 0.08 era; new pipeline adds **motion + texture + masks + 8s static** on top.

---

## Industry patterns implemented (Frigate / Blue Iris)

### 1. Ignore masks & zones (`detection_masks.py`)

- `processor.detection_ignore_masks`: polygons (normalized 0–1), permanent no-detect zones (branches, building corners).
- `processor.detection_interest_zones` + `detection_interest_zones_required`: optional ROI-only detection.

**User setup** in `user_config.yaml`:

```yaml
processor:
  detection_ignore_masks:
    - [[0.72, 0.55], [0.95, 0.55], [0.95, 0.95], [0.72, 0.95]]  # feeder glare patch
```

### 2. Motion-verified detection (`detection_quality.py`)

- Global: if whole frame `mean(absdiff) < 1.5` → reject all boxes (model hallucination on static frame).
- Per-ROI: if bbox region `mean(absdiff) < 6` vs previous frame → reject (`roi_no_motion`).

### 3. Adaptive / layered thresholds

- Night profile in `adaptive_profiles` (existing) + square-box hard reject `<0.38` (`StaticObjectFilter`).
- Long static temporal: **8s @ 7fps ≈ 56 frames**, jitter **≤2px**.

### 4. Texture / edge gate

- Laplacian variance inside bbox `< 20` → reject (blur/shadow vs bird feathers).

### 5. Hard negatives mine

- Rejected crops → `app/data/hard_negatives/` (configurable) for retraining.

---

## Architecture cleanup

### Active behavior model (single truth)

```yaml
behavior:
  active_video_model: "video_v1"
  video_openvino_path: "models/behavior_v1_openvino"
```

- `behavior_v2_openvino/`, `behavior_v2_1_openvino/` marked **DEPRECATED** (README), not deleted from git (audit trail).

### Path hygiene

- `scripts/fix_artifact_paths.py` — rewrites `/home/.../BirdLense/app/` → `/app/` in JSON.
- `scripts/ml_behavior_export_video_openvino.py` — new exports emit `/app/` paths only.

### Config sync

- `.env.example`: `cpu` default; GPU commented.
- `default_config.yaml`: matches CPU; documents mask/motion/quality keys.

---

## Code map

| Module | Role |
|--------|------|
| `detection_quality.py` | Orchestrator (masks → motion → texture → static) |
| `detection_masks.py` | Ignore / interest polygons |
| `static_object_filter.py` | Phantom static geometry + temporal |
| `detection_strategy.py` | Integration post-NMS |
| `scripts/fix_artifact_paths.py` | Repo JSON path repair |

## Metrics in runtime

`last_detect_metrics` now includes:

- `rejected_ignore_mask`, `rejected_interest_zone`
- `rejected_motion_verified`, `rejected_global_static`
- `rejected_texture`, `rejected_static_objects`, `rejected_phantom_boxes`
- `hard_negatives_saved`

---

## Verification commands

```bash
cd app/processor && PYTHONPATH=src python3 -m pytest tests/test_detection_masks.py tests/test_static_object_filter.py -q
python3 scripts/fix_artifact_paths.py --dry-run
python3 scripts/validate_static_object_filter.py  # in birdlense container
```

---

## Next steps (optional)

1. UI editor for ignore masks (export polygon to YAML).
2. Zone-specific FP history → dynamic conf (per grid cell).
3. Retrain NABirds with `data/hard_negatives/` merged into dataset.
