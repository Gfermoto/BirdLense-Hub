# Emergency fixes after nightly marathon — 2026-05-19

## P0 Canary persist

**Root cause:** OpenVINO IR for binary `video_v2` outputs **1 logit**, labels are **2** (`feeding`, `flying`). `_predict_video_openvino` rejected `1 != 2` → `shadow_label=None`. Meta path worked → only `behavior_label=feeding` in DB.

**Not the cause:** SQL/ORM — `processor_routes` and `api.create_video` persist shadow when non-null.

**Fix:** `behavior_video_runtime.py` — sigmoid mapping for `logits.shape==(1,) && len(labels)==2`.

**Verify video 1803:** `shadow=feeding` conf≈0.755 (was null).

**Backfill:** `backfill_behavior_canary_shadow.py` — updated 1803–1805; 1806 skipped (no tracklet frames for OV).

## P1 YOLO blind suspected

**Root cause:** `blind_suspected = score >= threshold*0.5` even when `yolo_raw_boxes_total > 0` or tracks present. Short sessions without boxes in-window still scored high → 221/221 suspected.

**Fix:** `recording_finalize.py` — `blind_suspected=False` if `yolo_raw_now > 0` OR `yolo_frames_with_tracks > 0`.

**Note:** Applies to **new** sessions after deploy/restart. Historical log counts unchanged.

## P2 Monitor

**Root cause:** `docker logs --since 30s` each probe.

**Fix:** `monitor_long_run.py` — since = elapsed time since last probe (~30m); empty window → `"note": "No logs"`.

## Manual harvest

- Path: `app/data/nightly_marathon/manual_crops/` (11 files, 1 tracklet v1804, class **feeding**)
- **0 flying** in night batch (meta+shadow agree feeding)

## Disk

- Truncated oversized Docker json logs (~14G freed)
- `/` usage: **87% → 81%** (~44G free)

## Ready for 1–2h re-test?

| Check | Status |
|-------|--------|
| Canary writes shadow on new video | Yes (code + backfill) |
| Monitor interval | Fixed (not deployed to long runner until next start) |
| Blind gate on new sessions | Fixed after restart |
| Flying crops | No — need more activity / lower priority / longer window |

**Recommendation:** Short canary watch (1–2h) with `monitor_long_run.py --duration 2h --interval 15m`, then check `behavior_shadow_label` on new videos and `discrepancy_rate`.
