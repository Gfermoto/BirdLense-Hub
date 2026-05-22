# TrapperAI v02.2024 — Performance & Quality Report

- **Video ID:** 1952
- **File:** `/app/data/recordings/2026/05/22/021545/video.mp4`
- **Model:** OpenVINO `trapper_ai_v02_2024_openvino_model` @704
- **Device:** `intel:gpu`
- **Target stream rate:** 7 FPS (simulated)

## Performance

| Metric | Value |
|--------|-------|
| Processed frames | 100 |
| Avg inference (ms) | 111.00 |
| Min inference (ms) | 104.38 |
| Max inference (ms) | 153.14 |
| Avg frame total (ms) | 112.43 |
| Avg processing FPS (wall) | 7.75 |
| **Avg infer FPS (steady)** | **9.01** |
| Avg inference steady (ms) | 111.00 |
| **Status** | **MARGINAL** |

## Detections (conf > 0.25)

| Class | Count |
|-------|-------|
| Bird | 25 |
| Squirrel | 0 |
| Frames with any target | 25 |

## Artifacts

- Visual frames: `/tmp/trapper_test_1952/results_visual/`
- Collage (top 10): `/tmp/trapper_test_1952/results_visual/collage_top10.jpg`
- JSON metrics: `/tmp/trapper_test_1952/report.json`

## Quality (automated heuristics)

- Доля кадров с Bird/Squirrel: **25.0%** (25/100)
- Ложные на фоне (эвристика): низкая
- Пропуски (эвристика): явных пропусков по выборке не видно
- Коллаж: 10 кадров с наибольшим числом детекций → `results_visual/collage_top10.jpg`

## Verdict

**Требуется оптимизация (производительность или качество детекции)**
