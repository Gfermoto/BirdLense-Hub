# Runtime Pipeline Profile

- generated_at: `2026-06-03T13:35:29Z`
- window_hours: `24`
- bottleneck_stage_p95: `finalize_duration_ms`
- ok: `True`

## Profile

`{'trigger_to_first_bbox_latency_s': {'n': 47, 'p50': 0.939981, 'p95': 5.45805, 'max': 46.381388, 'mean': 2.604631}, 'trigger_to_first_bbox_wall_s': {'n': 47, 'p50': 0.939981, 'p95': 5.45805, 'max': 46.381388, 'mean': 2.604631}, 'trigger_to_first_track_wall_s': {'n': 47, 'p50': 1.301457, 'p95': 9.10509, 'max': 46.381391, 'mean': 3.880359}, 'finalize_duration_ms': {'n': 47, 'p50': 1870.554, 'p95': 37343.035, 'max': 95904.424, 'mean': 10147.382681}, 'finalize_duration_ms_kpi_excl_legacy': {'n': 47, 'p50': 1870.554, 'p95': 37343.035, 'max': 95904.424, 'mean': 10147.382681}, 'finalize_critical_path_ms': {'n': 47, 'p50': 1862.515, 'p95': 37296.254, 'max': 95868.272, 'mean': 10128.648213}, 'pre_fusion_duration_ms': {'n': 47, 'p50': 1.955, 'p95': 41.905, 'max': 52.247, 'mean': 10.232021}, 'fusion_duration_ms': {'n': 47, 'p50': 322.016, 'p95': 1455.856, 'max': 37244.697, 'mean': 2177.526191}, 'persist_duration_ms': {'n': 47, 'p50': 456.246, 'p95': 28575.517, 'max': 95215.767, 'mean': 7713.52634}, 'create_video_duration_ms': {'n': 47, 'p50': 32.588, 'p95': 98.208, 'max': 1301.134, 'mean': 88.677234}, 'create_video_ingest_visit_processor_ms': {'n': 47, 'p50': 13.916, 'p95': 80.214, 'max': 1288.132, 'mean': 69.803681}, 'create_video_ingest_commit_ms': {'n': 47, 'p50': 0.768, 'p95': 1.774, 'max': 5.83, 'mean': 1.015}, 'create_video_ingest_weather_ms': {'n': 47, 'p50': 0.296, 'p95': 7.511, 'max': 19.762, 'mean': 1.565426}, 'behavior_duration_ms': {'n': 47, 'p50': 2.111, 'p95': 7.287, 'max': 15.159, 'mean': 3.211489}, 'scales_duration_ms': {'n': 47, 'p50': 42.234, 'p95': 90.507, 'max': 208.396, 'mean': 52.986021}, 'dataset_crops_duration_ms': {'n': 47, 'p50': 1.063, 'p95': 10.433, 'max': 532.701, 'mean': 26.468553}}`

## By slot (finalize_duration_ms)

`{'camera_1': {'n': 36, 'p50': 1280.714, 'p95': 37343.035, 'max': 94518.523, 'mean': 9067.102611}, 'camera_2': {'n': 11, 'p50': 2705.288, 'p95': 20009.214, 'max': 95904.424, 'mean': 13682.844727}}`

## Warnings

- finalize_duration_p95 37343.04ms > 8000.00ms
- finalize tail dominated by persist (77% of critical_path p95 37296ms; #586/I12)

## KPI (#579 wall first-bbox)

`{'first_bbox_wall_p95_s': 5.45805, 'first_bbox_fail_threshold_s': None, 'first_bbox_warn_threshold_s': 8.0, 'source': 'wall_clock', 'ok': None, 'create_video_p95_ms': 98.208, 'create_video_fail_threshold_ms': None, 'create_video_warn_threshold_ms': 30000.0, 'create_video_ok': None, 'finalize_critical_path_p95_ms': 37296.254, 'persist_p95_ms': 28575.517, 'finalize_tail_dominant': 'persist'}`

## Failures

- none
