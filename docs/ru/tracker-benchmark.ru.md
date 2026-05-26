# Бенчмарк трекеров ByteTrack vs BoT-SORT (SOTA-12)

## Реестр пресетов

`app/processor/src/tracker_registry.py`:

| id | Ultralytics type | YAML |
|----|------------------|------|
| `bytetrack_birdlense` | bytetrack | `models/tracker/bytetrack_birdlense.yaml` |
| `bytetrack_birdlense_lowfps` | bytetrack | `models/tracker/bytetrack_birdlense_lowfps.yaml` |
| `botsort_birdlense` | botsort | `models/tracker/botsort_birdlense.yaml` |

Конфиг: `processor.tracker` или `processor.tracker_preset` (пресет имеет приоритет при резолве через `tracking_policy`).

## OC-SORT

В Ultralytics 8.x нет нативного `ocsort.yaml`. Оценка OC-SORT — отдельная интеграция (вне scope SOTA-12); до появления backend остаёмся на ByteTrack/BoT-SORT.

## Прогон на golden-клипе

```bash
python3 scripts/benchmark_trackers.py \
  --clip "$SOTA_GOLDEN_CLIP_1819" \
  --presets bytetrack_birdlense,botsort_birdlense \
  --frame-step 6 \
  --write-report .artifacts/tracker_benchmark_1819.json
```

Метрики: `fused_track_count`, `track_id_switches_count`, `avg_track_duration_sec`, `recall_ratio_vs_bytetrack`.

## Критерий выбора

Переключать дефолт с ByteTrack только если на 1816/1819 выигрыш по стабильности/recall **≥5%** без роста FP на 1816.
