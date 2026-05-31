# Quality Outcome Metrics

- generated_at: `2026-05-31T20:38:14Z`
- gate_ok: `False`
- sessions_total: `0`

## Metrics

- blind_rate: `1.0`
- yolo_frames_with_tracks: `0`
- empty_bbox_rate: `0.0`
- tracks_coverage: `0.0`
- trigger_to_first_bbox_latency_p95_s: `None`

## Thresholds

- max_blind_rate: `0.3`
- min_tracks_coverage: `0.5`
- max_empty_bbox_rate: `0.2`
- min_yolo_frames_with_tracks: `1`

## Errors

- no session_runtime_metrics rows in lookback window
- blind_rate=1.0000 > max_blind_rate=0.3000
- tracks_coverage=0.0000 < min_tracks_coverage=0.5000
- yolo_frames_with_tracks_sum=0 < min_yolo_frames_with_tracks=1
