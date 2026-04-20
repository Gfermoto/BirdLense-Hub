# Processor performance (resolution, VA-API, thresholds)

[Русский](./PROCESSOR_PERFORMANCE.ru.md)

Guidance for **two-stage** detection when video is heavy (high resolution, VA-API). Goal: align expectations with hardware — slow frames are often **capacity**, not a random bug.

## Levers

| Knob | Role |
|------|------|
| `processor.binary_imgsz` | Downscale before binary detector; smaller → faster, less detail. |
| `processor.frame_processing_warn_ms` | Log threshold for “slow frame”; raising it reduces **noise** in logs without speeding up work. |
| GPU / VA-API | If VA-API or GPU path is broken or missing, CPU fallback is slower — verify drivers (`vainfo`, `intel_gpu_top`) per [RUNBOOKS](./RUNBOOKS.md). |
| Light gate / night profiles | Frequent “no YOLO tracks” can interact with exposure — tune profiles before blaming YOLO. |

## Qualitative table (not a SLA)

Exact ms depend on CPU, iGPU, driver, and concurrent load. Use this as **relative** guidance:

| Input resolution (example) | `binary_imgsz` | Expectation |
|------------------------------|------------------|---------------|
| ≤ 1280×720 | 640–960 | Usually comfortable on modest x86. |
| 1920×1080 | 960–1280 | Watch slow-frame logs; tune if sustained warnings. |
| ≥ 2560×1440 | Lower `binary_imgsz` or accept fewer FPS | Often needs strong iGPU/dGPU or aggressive downscale. |

## `frame_processing_warn_ms`

- **Lower** threshold → more warnings; good while **profiling** a new machine.
- **Raise** when warnings are steady but operator accepts latency (avoid “cry wolf” in logs).
- Pair with **config audit** hints from `processor_runtime_stats.json` (see [RUNBOOKS](./RUNBOOKS.md) slow-frame section).

## Code changes

Dynamic throttling / log aggregation for slow frames is **not** implemented here — open a focused issue if product wants it.

Tracking: [BirdLense-Hub#328](https://github.com/Gfermoto/BirdLense-Hub/issues/328).
