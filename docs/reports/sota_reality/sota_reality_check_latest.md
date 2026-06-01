# SOTA Reality Check (weekly)

- generated_at: `2026-06-01T09:38:22Z`
- decision: `hold`
- acceptance_blocked: `True`

## Gates

- error_budget_ok: `True`
- golden_set_ok: `True`
- outcome_ok: `False`

## Outcome metrics

- blind_rate: `1.0`
- yolo_frames_with_tracks: `0`
- empty_bbox_rate: `0.0`
- tracks_coverage: `0.0`
- trigger_to_first_bbox_latency_p95_s: `None`
- finalize_duration_p95_ms: `None`
- ingest_bbox_contract_pruned_events: `0`
- ingest_bbox_contract_empty_events: `0`
- ingest_bbox_contract_pruned_rows_per_session: `None`
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

## Critical issues

- #517 [[EPIC][P0→P2] BirdLense > Frigate: программа превосходства качества](https://github.com/Gfermoto/BirdLense-Hub/issues/517) — `OPEN`
- #555 [[P0][release-blocker] Восстановить корректное ТЗ пайплайна: триггеры, арбитраж, bbox/tracks, perf](https://github.com/Gfermoto/BirdLense-Hub/issues/555) — `OPEN`
- #556 [[P0][release-blocker] Регрессии UI/данных: orphan visit, лишние фильтры, источники=триггеры, пустой список птиц](https://github.com/Gfermoto/BirdLense-Hub/issues/556) — `OPEN`
- #557 [[EPIC][P0] Консилиум: доменные датасеты + дообучение на домене (detector/classifier/behavior/ReID)](https://github.com/Gfermoto/BirdLense-Hub/issues/557) — `OPEN`
