# Prod rollback points

Зафиксированные «известно рабочие» состояния prod VPS. Использовать при откате после неудачного деплоя или правок `user_config`.

## prod-tg-bbox-20260615

| Поле | Значение |
|------|----------|
| **Дата** | 2026-06-15 |
| **Git tag** | `prod-tg-bbox-20260615` → `cfeeffc6d` (`dev`) |
| **Hub** | https://birdlense.eyera.info/ |
| **VPS** | `ssh -p 2222 root@185.218.111.196` |
| **Рабочая камера** | **Forest** (`camera_2`, `tuning_role: feeder_far`, RTSP `192.168.1.101`, Frigate id `Forest`) |
| **Не подтверждена** | **BirdBox** (`camera_1`, `tuning_role: feeder_close`, RTSP `192.168.1.129`) — Frigate триггерит, YOLO raw есть, acceptance gap → 0 tracks |

### VPS backups (на сервере, не в git)

```
/root/BirdLense/app/app_config/user_config.yaml.bak.20260615_tg_bbox_working
/root/BirdLense/app/app_config/default_config.yaml.bak.20260615_tg_bbox_working
```

Откат конфига:

```bash
ssh -p 2222 root@185.218.111.196
cp -a /root/BirdLense/app/app_config/user_config.yaml.bak.20260615_tg_bbox_working \
      /root/BirdLense/app/app_config/user_config.yaml
cd /root/BirdLense/app && docker compose up -d --force-recreate birdlense
```

### Эталонные сессии (baseline логов)

| Время MSK | Камера | video_path | Воронка |
|-----------|--------|------------|---------|
| 10:54–10:56 | Forest | `data/recordings/2026/06/15/105442/video.mp4` | raw 188 → tracks 167 → accepted 216 → persist 12 (TG OK) |
| 10:56–10:58 | Forest | `data/recordings/2026/06/15/105639/video.mp4` | raw 196 → tracks 166 → accepted 194 → persist 9 |

Команда:

```bash
docker logs birdlense 2>&1 | grep recording_session_summary | grep -E '105442|105639'
```

### Ключи конфига (highlights)

| Ключ | Значение prod |
|------|---------------|
| `detect_stream` RTSP | **`subtype=1`** (704×576 lores), обе камеры |
| `processor.openvino_native_lores_imgsz` | `false` |
| `processor.inference_backend` | `openvino` |
| `processor.inference_device` | `intel:gpu` |
| `processor.binary_imgsz` | `704` |
| `processor.min_confidence_binary` | `0.05` |
| `processor.species_confidence_overrides.Bird` | `0.08` |
| `processor.openvino_binary_track_ultralytics_conf` | `0.025` |
| `feeder_close` / `feeder_far` | role presets в `user_config.processor.camera_tuning_by_role` |

### Frigate (read-only справка)

В окне 10:54–10:58 Forest: opencv-initiated sessions; BirdBox позже (11:04+) — Frigate MQTT score ~0.762, но Hub `yolo_accepted_boxes_total=0`.

## Связанные документы

- [hub-detector-runbook.md](./hub-detector-runbook.md)
- [hub-detection-postmortem-2026-06.md](./hub-detection-postmortem-2026-06.md)
