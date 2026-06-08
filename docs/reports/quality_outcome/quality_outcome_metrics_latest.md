# Quality Outcome Metrics

- generated_at: `2026-06-08T11:05:14Z`
- data_source: `local:app/data/db/birdlense.db`
- gate_ok: `False`
- sessions_total: `13`

## Metrics

- blind_rate: `0.0`
- yolo_frames_with_tracks: `0`
- empty_bbox_rate: `0.0`
- tracks_coverage: `0.0`
- tracks_missing_rate: `1.0`
- bbox_quality_score: `0.0`
- trigger_to_first_bbox_latency_p95_s: `0.3`
- finalize_duration_p95_ms: `7518.808`
- ingest_bbox_contract_pruned_events: `0`
- ingest_bbox_contract_empty_events: `0`
- ingest_bbox_contract_pruned_rows_total: `0`
- ingest_bbox_contract_pruned_frames_total: `0`
- ingest_bbox_contract_pruned_rows_per_session: `0.0`
- ingest_bbox_contract_pruned_rows_per_hour: `0.0`
- ingest_bbox_contract_pruned_rows_per_hour_7d_baseline: `0.0`
- ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d: `0.0`
- trigger_moratorium_events: `0`
- trigger_moratorium_by_source: `{}`
- trigger_moratorium_events_per_hour: `0.0`
- trigger_moratorium_events_per_hour_7d_baseline: `0.0`
- trigger_moratorium_events_per_hour_delta_vs_7d: `0.0`
- frigate_catches_missed_birds_sessions: `0`
- frigate_catches_missed_birds_rate: `0.0`
- frigate_catches_missed_birds_by_trigger_source: `{}`
- frigate_catches_missed_birds_by_trigger_source_rate: `{}`
- frigate_catches_missed_birds_rate_7d_baseline: `0.0`
- frigate_catches_missed_birds_rate_delta_vs_7d: `0.0`

## Thresholds

- max_blind_rate: `0.3`
- min_tracks_coverage: `0.5`
- max_empty_bbox_rate: `0.2`
- min_yolo_frames_with_tracks: `1`
- max_ingest_pruned_rows_per_hour_delta_vs_7d: `0.0`
- max_frigate_catches_missed_birds_rate: `0.0`
- max_frigate_catches_missed_birds_rate_delta_vs_7d: `0.0`

## Errors

- no yolo runtime rows in lookback window
- tracks_coverage=0.0000 < min_tracks_coverage=0.5000
- yolo_frames_with_tracks_sum=0 < min_yolo_frames_with_tracks=1
