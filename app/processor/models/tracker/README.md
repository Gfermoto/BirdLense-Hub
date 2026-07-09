# Tracker presets (`tracker/`)

| Файл | Назначение |
| ---- | ---------- |
| `bytetrack_birdlense.yaml` | **Production** ByteTrack (live, regen, night, low-FPS) — adaptive clamp/buffer в runtime |
| `botsort_birdlense.yaml` | BoT-SORT для A/B benchmark (SOTA-12), не дефолт |

Конфиг: `processor.tracker`, `processor.tracker_profiles.night`, `processor.tracker_fps_profiles.*`.

Пресет `bytetrack_birdlense_lowfps` в registry — alias на тот же YAML (backward compat).
