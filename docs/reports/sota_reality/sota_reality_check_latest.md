# SOTA Reality Check (weekly)

- generated_at: `2026-06-02T08:14:14Z`
- decision: `hold`
- acceptance_blocked: `True`

## Gates

- error_budget_ok: `True`
- golden_set_ok: `True`
- outcome_ok: `False`

## Outcome metrics

- blind_rate: `0.0`
- yolo_frames_with_tracks: `22485`
- empty_bbox_rate: `0.0`
- tracks_coverage: `0.847087`
- trigger_to_first_bbox_latency_p95_s: `27.74`
- finalize_duration_p95_ms: `63742.574`
- ingest_bbox_contract_pruned_events: `8`
- ingest_bbox_contract_empty_events: `0`
- ingest_bbox_contract_pruned_rows_per_session: `0.029126`
- ingest_bbox_contract_pruned_rows_per_hour: `0.5`
- ingest_bbox_contract_pruned_rows_per_hour_7d_baseline: `0.071429`
- ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d: `0.428571`
- trigger_moratorium_events: `2`
- trigger_moratorium_by_source: `{'frigate': 1, 'opencv': 1}`
- trigger_moratorium_events_per_hour: `0.083333`
- trigger_moratorium_events_per_hour_7d_baseline: `0.011905`
- trigger_moratorium_events_per_hour_delta_vs_7d: `0.071429`
- frigate_catches_missed_birds_sessions: `6`
- frigate_catches_missed_birds_rate: `0.014563`
- frigate_catches_missed_birds_by_trigger_source: `{'frigate': 2, 'opencv': 4}`
- frigate_catches_missed_birds_by_trigger_source_rate: `{'frigate': 0.333333, 'opencv': 0.666667}`
- frigate_catches_missed_birds_rate_7d_baseline: `0.005245`
- frigate_catches_missed_birds_rate_delta_vs_7d: `0.009318`

## Critical issues

- #517 [[EPIC][P0→P2] BirdLense > Frigate: программа превосходства качества](https://github.com/Gfermoto/BirdLense-Hub/issues/517) — `CLOSED`
- #555 [[P0][release-blocker] Восстановить корректное ТЗ пайплайна: триггеры, арбитраж, bbox/tracks, perf](https://github.com/Gfermoto/BirdLense-Hub/issues/555) — `CLOSED`
- #556 [[P0][release-blocker] Регрессии UI/данных: orphan visit, лишние фильтры, источники=триггеры, пустой список птиц](https://github.com/Gfermoto/BirdLense-Hub/issues/556) — `CLOSED`
- #557 [[EPIC][P0] Консилиум: доменные датасеты + дообучение на домене (detector/classifier/behavior/ReID)](https://github.com/Gfermoto/BirdLense-Hub/issues/557) — `CLOSED`
