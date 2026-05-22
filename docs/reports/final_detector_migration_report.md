# Миграция детектора — TrapperAI v02.2024 (прод)

## Вердикт (2026-05-22)

| Кандидат | Решение |
|----------|---------|
| **TrapperAI v02.2024** | **Прод** — все 18 классов, native labels, 704×576 |
| **Deepfaune v1.3** | **Удалён** из репо (animal-only, не bird/squirrel) |
| **CTDR Species v3** | Не прод (слабый recall на 1819) |

Подробности: [`european_detector_showdown_final.md`](european_detector_showdown_final.md), bbox: `showdown_viz/trapper/`.

## Конфиг

- `default_config.yaml`: Trapper PT + OV @704, `detector_scope: []` (все классы), `detector_native_class_labels: true`
- VPS: `user_config.trapper-production.example.yaml` — iGPU, **binary_imgsz: 704**, `inference_lores_wh: [704, 576]`

## Веса (2026-05-22)

- Локально: OpenVINO **704×704**, `metadata.yaml` imgsz 704, predict OK
- VPS `185.218.111.196`: rsync в `trapper_ai_v02_2024_openvino_model/` (совпадает с локалью)
- Повтор: `make export-trapper-openvino` → `bash scripts/sync_trapper_weights.sh --check --rsync-vps`

## Деплой

1. `user_config.yaml` на VPS — фрагмент из `user_config.trapper-production.example.yaml` (Trapper paths, не `best.pt`)
2. `make deploy` — код + recreate контейнера
3. Smoke: regen 1816/1819 → `yolo_frames_with_tracks` > 0
