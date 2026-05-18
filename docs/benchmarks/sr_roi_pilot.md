# ROI Super-Resolution Pilot

- Samples: **1200** synthetic low-contrast crops (balanced labels).
- Models: **fsrcnn_x2**, **realesrgan_x2**.

| model | native loaded | recall baseline | recall sr | recall gain | fpr delta | p95 overhead (ms) |
|---|---:|---:|---:|---:|---:|---:|
| fsrcnn_x2 | false | 0.7267 | 0.4850 | -0.2417 | 0.2367 | 0.181 |
| realesrgan_x2 | false | 0.7267 | 0.5833 | -0.1433 | 0.3650 | 0.181 |

## Decision
- Best candidate: **realesrgan_x2**
- Rule: recall gain > 0.05 and p95 overhead < 20ms
- Verdict: **NO-GO**

## Suggested production config
```yaml
experimental:
  sr_enabled: false
  sr_model: "realesrgan_x2"
  sr_scale: 2
  sr_min_crop_px: 10
  sr_max_crop_px: 96
  sr_max_latency_ms: 20
```
