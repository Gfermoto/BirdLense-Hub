# SOTA-09: бенчмарк на golden-клипах 1816 / 1819

Автоматическая регрессия качества детекции: **0 FP** на шуме, **recall** на клипе с птицами.

## Клипы

| ID | Роль | Критерий |
|----|------|----------|
| **1816** | шум / фон | `fused_track_count == 0`, нет принятых боксов |
| **1819** | птицы | `fused_track_count ≥ 1`, `frames_with_tracks ≥ 1`, recall ≥ 90% от baseline |

Пути (по приоритету):

1. `SOTA_GOLDEN_CLIP_1816` / `SOTA_GOLDEN_CLIP_1819` (или legacy `YOLO_GOLDEN_CLIP_*`)
2. `benchmarks/fixtures/clip_1816.mp4`, `clip_1819.mp4`
3. `video_path` из SQLite (`BIRDLENSE_DB`) по `video.id`

```bash
python3 scripts/fetch_golden_clips.py --link-fixtures
```

## Запуск

```bash
export SOTA_GOLDEN_CLIP_1816=/path/to/noise.mp4
export SOTA_GOLDEN_CLIP_1819=/path/to/birds.mp4
python3 scripts/benchmark_sota.py --write-report benchmarks/last_sota_report.json
```

Переменные:

- `SOTA_BENCHMARK_FRAME_STEP` — шаг кадров (по умолчанию 6)
- `SKIP_SOTA_BENCHMARK=1` — пропуск в `check-quality-gates.sh`
- `--skip-if-missing` — не падать, если mp4 нет (локально без фикстур)
- `--smoke` — мягкий baseline для CI smoke-ролика
- `--update-baseline` — записать метрики в `benchmarks/golden_baseline.json` после успешного прогона

## CI

- `scripts/check-quality-gates.sh` вызывает `benchmark_sota.py` (если не `SKIP_SOTA_BENCHMARK=1`)
- workflow `benchmark-regen-integration`: smoke mp4 + `benchmark_sota.py --smoke`
- unit: `app/processor/tests/test_benchmark_sota_gate.py`

## Обновление baseline

После улучшения модели на реальных 1816/1819:

```bash
python3 scripts/benchmark_sota.py --update-baseline --write-report benchmarks/last_sota_report.json
git add benchmarks/golden_baseline.json
```

## Имитация регрессии

Временно завысить `processor.min_confidence_binary_bird` или сломать путь к весам — `1819` должен упасть по recall. На `1816` при «слепом» детекторе с ложными треками — FAIL по FP.
