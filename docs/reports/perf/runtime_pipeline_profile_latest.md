# Runtime Pipeline Profile

- generated_at: `2026-06-01T19:14:41Z`
- window_hours: `48`
- bottleneck_stage_p95: `finalize_duration_ms`
- ok: `True`

## Profile

Baseline **pre-Epic-D deploy** (spectrogram removed on prod 2026-06-01). Wall-clock first_bbox + persist sub-stages ship in next deploy.

`{'trigger_to_first_bbox_latency_s': {'n': 29, 'p50': 0.02, 'p95': 8.51, 'max': 27.74}, 'finalize_duration_ms': {'n': 155, 'p50': 545.543, 'p95': 24067.507, 'max': 82139.605}, 'fusion_duration_ms': {'n': 155, 'p50': 62.132, 'p95': 783.702}, 'persist_duration_ms': {'n': 151, 'p50': 0.001, 'p95': 2236.843, 'max': 64493.241}}`

## Warnings

- finalize_duration_p95 24067.51ms > 5000.00ms (spectrogram tail in 48h window)
- first_bbox_latency_p95 8.510s > 5.000s (legacy video-offset metric)

## Tomorrow validation

1. `make runtime-pipeline-profile` on prod DB after bird sessions
2. Expect finalize p95 ≤ 5000 ms (#578)
3. Expect trigger_to_first_bbox p95 ≤ 2.0 s with wall-clock metric (#579)
