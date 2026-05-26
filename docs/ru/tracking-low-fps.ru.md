# Трекинг на низком FPS (SOTA-10)

Проблема: на substream **5–10 FPS** ByteTrack теряет объекты между редкими детекциями → новые `track_id`, рваные визиты, ложные «новые» птицы.

## Решение

### 1. Профиль `bytetrack_birdlense_lowfps.yaml`

Базовый трекер в `default_config.yaml`: увеличен `track_buffer` (56), мягче `track_high_thresh` / `new_track_thresh`.

### 2. Адаптивный буфер (`tracker_low_fps.py`)

При `stream_fps ≤ processor.tracker_low_fps_threshold` (по умолчанию 10):

- `track_buffer = round(stream_fps × tracker_remember_seconds)` (clamp 24…120)
- `match_thresh` слегка снижается (−0.08) для более мягкой ассоциации
- YAML материализуется в `models/tracker/.adaptive_tracker_cache/`

Включение: `processor.tracker_adaptive_low_fps_enabled: true`.

Для regen с `frame_step > 1` в контекст передаётся **effective_fps = source_fps / frame_step**.

### 3. Выбор трекера по FPS

`processor.tracker_fps_profiles` — как раньше (`lte_5`, `lte_7`, …), поверх выбранного профиля накладывается адаптивный буфер.

### 4. Метрики стабильности

| Метрика | Где |
|---------|-----|
| `track_id_switches_count` | геометрические смены ID между кадрами (IoU ≥ порога, другой id) |
| `avg_track_duration_sec` | средняя длительность треков по `frames[].t` |
| `id_switch_rate` | legacy: полная смена множества id между кадрами |

Пишутся в `frame_processor.last_run_stats`, `recording_session_summary`, отчёт `benchmark_sota.py`.

Порог IoU: `processor.track_id_switch_iou_threshold` (default 0.25).

## Валидация (SOTA-09)

На клипе **1819** в `benchmarks/golden_baseline.json`:

- `max_track_id_switches` — не больше N
- `min_avg_track_duration_sec` — не ниже порога

```bash
export SOTA_GOLDEN_CLIP_1819=/path/to/birds.mp4
python3 scripts/benchmark_sota.py
```

## Re-ID

Runtime ReID (DINOv2) по-прежнему на этапе **finalize** для слияния визитов, не внутри ByteTrack. Для межкадровой геометрии на low-FPS достаточно увеличенного `track_buffer` + метрик.

## Настройка

| Ключ | Смысл |
|------|--------|
| `tracker_remember_seconds` | сколько секунд «помнить» потерянный трек (× FPS → буфер) |
| `tracker_adaptive_max_buffer` | потолок кадров буфера |
| `tracker_low_fps_threshold` | выше этого FPS адаптация не применяется |

После смены порогов — прогон `benchmark_sota.py` и при улучшении модели `--update-baseline`.
