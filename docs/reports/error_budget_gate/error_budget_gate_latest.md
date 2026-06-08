# Error Budget Gate

- generated_at: `2026-06-08T11:08:41Z`
- state: `warning`
- consumed_pct: `85`
- remaining_pct: `15`
- gate_ok: `True`

## Inputs

- critical_breaches: `1`
- warning_breaches: `0`
- slo_dashboard_not_ok: `True`
- per_camera_warn_count_24h: `2`
- recording_artifact_failures: `True`

## Costs

- critical_breaches: `45`
- warning_breaches: `0`
- dashboard_not_ok: `20`
- per_camera_warn_count: `10`
- recording_artifact_failures: `10`

## Gate

- override_used: `True`
- override_reason: `dual-stream bbox timeline sync + BirdBox frigate-assist (#608)`
- block_release: `False`
