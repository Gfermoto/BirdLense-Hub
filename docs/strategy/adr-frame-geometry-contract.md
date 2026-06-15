# ADR: Frame geometry contract (WxH vs H×W)

**Status:** accepted  
**Date:** 2026-06-15  
**Issues:** [#636](https://github.com/Gfermoto/BirdLense-Hub/issues/636)  
**Related:** `app/shared/frame_shape.py`, `frame_geometry.py`, `playback_geometry.py`, `record_hires_crop.py`

---

## Context

BirdLense uses **two coordinate spaces**:

1. **Detect substream** — low-res RTSP, letterbox canvas, YOLO/ByteTrack.
2. **Main/record stream** — hires MP4, playback UI, TG preview crops.

Width and height order differs across surfaces:

| Surface | Order | Example 1920×1080 |
|---------|-------|-------------------|
| Config `main_size`, `inference_lores_wh`, OpenAPI `video_width`×`video_height` | **W×H** | `[1920, 1080]` |
| Metadata `*_shape_hw`, OpenCV `frame.shape`, persisted bbox norm | **H×W** | `[1080, 1920]` |
| ffprobe `StreamCapabilities.main_size` | **W×H** | `(1920, 1080)` |

Swapping W/H silently breaks bbox remap (record_hires, overlay, classifier crop).

---

## Decision

1. **Single parser module:** `app/shared/frame_shape.py` — `parse_config_wh`, `parse_metadata_hw`, `numpy_hw`, `probe_wh`, `metadata_hw_list`, `wh_to_hw` / `hw_to_wh`.
2. **Persisted bbox space:** normalized xyxy on **playback/main** frame when `playback_shape_hw` metadata is present and matches MP4 `frame.shape`.
3. **Legacy remap:** rows without `playback_shape_hw` still remap detect→main via `remap_norm_bbox_for_crop` (single path in `frame_geometry`).
4. **Validation:** on finalize/enrich and `apply_playback_shape_to_strategy`, assert metadata `[H,W]` matches `main_size (W,H)` or ffprobe MP4; mismatch → `geometry_metadata_invalid_total`.
5. **No hardcoded camera resolutions** in geometry code or tests (parametrize arbitrary W×H pairs).

---

## Consequences

- `inference_lores.parse_inference_lores_wh` delegates to `parse_config_wh` (+ clamp).
- `record_hires_crop` drops duplicate `_shape_hw_*` helpers; trusts playback metadata when present.
- Operators set detect size as **ширина×высота** in Settings; DB/API metadata remains `[height, width]`.

---

## Verification

- `cd app && make test-processor-light`
- `test_frame_shape.py`, `test_frame_geometry.py` (parametrized roundtrip IoU)
- Metric `geometry_metadata_invalid_total` in `processor_runtime_stats.json`
