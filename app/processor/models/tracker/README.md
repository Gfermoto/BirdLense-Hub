# ByteTrack profiles (`models/tracker/`)

Ultralytics `YOLO.track(..., tracker=<path>)`. Пути резолвятся в `tracker_paths.resolve_tracker_config_path`.

## Прод (Trapper @7 FPS)

| Файл | Когда |
|------|--------|
| `bytetrack_birdlense_lowfps.yaml` | День, основной `processor.tracker` |
| `bytetrack_birdlense_night.yaml` | Ночь (`processor.tracker_profiles.night`) |

## Аварийный unstick (опционально)

Только при `processor.auto_unstick_enabled: true` и N кадров без `track_id`:

| Файл | Когда |
|------|--------|
| `bytetrack_birdlense_unstick.yaml` | День |
| `bytetrack_birdlense_night_unstick.yaml` | Ночь |

## Согласование с детектором

1. `openvino_binary_track_ultralytics_conf` — conf в `track()` (ниже порога Bird в `_collect_valid_boxes`).
2. `track_high_thresh` / `new_track_thresh` в YAML — **строго ниже** п.1, иначе ByteTrack не выдаёт id (см. лог `no track ids after retry`).
3. `min_confidence_binary_bird` — отсекает боксы после трека.

Пример: `track(conf)=0.30`, YAML `track_high: 0.10`, пост-фильтр Bird `0.35`.

## Удалено

- `bytetrack_night.yaml` — устаревший жёсткий пресет (0.45); заменён на `bytetrack_birdlense_night.yaml`.
