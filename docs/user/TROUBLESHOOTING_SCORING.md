# Troubleshooting — ScoringEngine (SOTA 2.0)

## System is silent (no birds on the timeline)

1. **Wait for calibration** — first ~60 seconds after RTSP connect the engine learns scene noise. Do not tune YAML during this window.
2. **Check YOLO raw vs accepted** — System → session metrics: `yolo_raw_boxes_total` should be &gt; 0 when birds are visible. If raw is 0, fix detector/RTSP, not scoring.
3. **Black Box** — open latest `data/decision_traces/YYYY/MM/DD/*.jsonl`. Look for `final_decision: reject` and `reject_reason` (e.g. `score_below_low_threshold`).
4. **Debug API** — `GET /api/debug/scoring` with settings password: thresholds, 5‑minute histogram, last 10 decisions.
5. **Frigate-only visits** — ensure `detection.frigate_standalone_when_no_yolo: false` and `processor.scoring_engine_enabled: true` in `user_config.yaml`.

## System spams false birds

1. Let auto-calibration finish; it targets &lt;1% noise on empty frames.
2. If `degradation_alert: true` on `/api/debug/scoring`, review share &gt;20% — scene changed (wind, new object in frame); restart stream or temporarily raise `processor.scoring_default_low_threshold` until recalibration.
3. Inspect reject reasons — phantoms often show `phantom_box_giant_area` or low `motion_score` in trace.
4. Do **not** re-enable legacy `static_object_suppression` or `motion_verified` alongside scoring — use scoring weights only.

## Config checklist (production)

```yaml
processor:
  scoring_engine_enabled: true
  frame_decision_trace_enabled: true
  motion_verified_detection_enabled: false
  background_subtraction_enabled: false
  static_object_suppression_enabled: false
detection:
  frigate_standalone_when_no_yolo: false
```

Apply on server: `python3 scripts/patch_prod_sota20_user_config.py` then `docker compose up -d --force-recreate birdlense`.

## Offline validation

```bash
make validate-pipeline-golden
make stress-test-offline
python3 scripts/stress_test_offline.py --fetch-prod-clips   # optional real mp4 from VPS
```
