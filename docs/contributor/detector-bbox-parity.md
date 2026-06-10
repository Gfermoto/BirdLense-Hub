# Detector bbox parity gate (Frigate reference, #640)

[Русский](../ru/detector-bbox-parity.ru.md) · [ADR: classifier hints](../strategy/adr-classifier-hints-only.md) · [Testing](./testing.md)

Lightweight **PyTorch ↔ OpenVINO** bbox IoU smoke on Intel iGPU. Same-clip geometry check before trusting OpenVINO on production feeders.

## When it runs

| Context | Behavior |
|---------|----------|
| **CI** (`openapi-contract`) | `test_compare_detector_bboxes_gate.py` + `test_classifier_hints.py` — always green, no weights |
| **Optional heavy** | `scripts/detector_bbox_parity_smoke.py` when `DETECTOR_PARITY_VIDEO` + `best.pt` + `best_openvino_model` exist |
| **Deploy** | Not wired to `make deploy` by default (lightweight PR gate only) |

## Skip policy (no false red)

Smoke exits **0** with `status: skipped` when any prerequisite is missing:

- Golden mp4 (`DETECTOR_PARITY_VIDEO`, `SOTA_GOLDEN_CLIP_1819`, or `benchmarks/fixtures/clip_1819.mp4`)
- `app/processor/models/detection/weights/best.pt`
- `app/processor/models/detection/weights/best_openvino_model/*.xml`

Set `SKIP_DETECTOR_BBOX_PARITY=1` to force skip locally.

## Local repro (Intel iGPU)

```bash
# Help
make compare-detector-bboxes-help

# Full parity (requires weights + mp4)
export BIRDLENSE_INFERENCE_DEVICE=intel:gpu
export DETECTOR_PARITY_VIDEO=/path/to/clip.mp4
python3 scripts/detector_bbox_parity_smoke.py --min-median-iou 0.45 --clip-id 1819

# Direct script (same gate)
python3 scripts/compare_detector_bboxes.py \
  --video "$DETECTOR_PARITY_VIDEO" \
  --model-a app/processor/models/detection/weights/best.pt \
  --model-b app/processor/models/detection/weights/best_openvino_model \
  --bird-class-ids-a 0 --bird-class-ids-b 0 \
  --device intel:gpu --frame-step 4 --conf 0.2 \
  --min-median-iou 0.45 --clip-id 1819
```

Gate failure prints `clip_id`, `median_iou`, `min_median_iou`, and `delta` on stderr.

## Threshold

Start conservative: **median IoU ≥ 0.45** when both backends see a bird on sampled frames. Tighten after golden pack stabilizes (#640 / plan §12).

## Rollout order (#642)

Enable layers only after bbox SLO green:

```text
motion → record → detect/track → classify → (DINOv2 re-id) → (behavior video)
```

When `bbox_slo_ok=false` in `/api/ui/readiness`, DINOv2 re-id and behavior video layers are skipped with log reason `bbox_slo gate red`.

## Per-camera detect/main URL audit (#636)

Checklist per camera in `video.cameras[]`:

1. `detect_url` (or go2rtc detect role) resolves to lores substream (e.g. 704×576 BirdBox).
2. `main_url` / record stream matches playback MP4 geometry (e.g. 1920×1080).
3. `inference_lores_wh` matches native detect aspect (no square forcing).
4. After deploy: `bbox_parity_roundtrip_iou_p50` gauge ≥ 0.45 in processor heartbeat.

## Related tests

- `app/processor/tests/test_bbox_iou_gate.py` — overlay geometry remap
- `app/processor/tests/test_yolo_golden_clips_gate.py` — track recall on clip 1819
- `app/processor/tests/test_yolo_geometry_native.py` — native 704×576 letterbox skip
- `app/processor/tests/test_dual_stream_timeline.py` — detect↔record offset
