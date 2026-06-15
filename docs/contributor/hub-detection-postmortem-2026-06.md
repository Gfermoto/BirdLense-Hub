# Postmortem: детекция Hub VPS (июнь 2026)

Краткая хронология инцидента «Frigate видит, Hub/TG молчит» и первого подтверждённого успеха с bbox в Telegram (2026-06-15).

## Итог 2026-06-15

- **Работает:** Forest (`feeder_far`, `192.168.1.101`) — TG с корректными bbox, `db_persist_success=true`.
- **Не работает:** BirdBox (`feeder_close`, `192.168.1.129`) — Frigate триггерит (score ~0.76), YOLO видит raw boxes, но **`detection_acceptance_gap`** → 0 accepted → 0 tracks.
- **Rollback:** tag `prod-tg-bbox-20260615`, бэкапы на VPS — см. [prod-rollback-points.md](./prod-rollback-points.md).

## Timeline failure modes

| Период | Симптом | Первопричина (установлено) |
|--------|---------|---------------------------|
| Ранний июнь | Processor читает тестовый файл вместо RTSP | Test-file / dev path leak в runtime |
| Неделя до фикса | `yolo_raw_boxes_total=0` при живом Frigate | Каскад порогов: global 0.12 + user 0.22 + species Bird **0.32** |
| После порогов | raw > 0, tracks = 0 | ByteTrack `track_high_thresh` / OV `ultralytics_conf` clamp — боксы ниже track gate |
| Деплой subtype=0 | Пустой detect на main stream 2688p | **subtype=0 vs subtype=1** — Hub ingest ≠ Frigate detect canvas |
| OpenVINO на iGPU | raw иногда есть, tracks нет | `openvino_native_lores_imgsz: true` + square 704² на 704×576 lores |
| VA-API record path | `video_file_ok=false`, пустые клипы | Letterbox/encode mismatch, `moov` errors в ffmpeg |
| UI «слепой» при merge | Agent правит пороги → снова слепой после deploy | **user_config drift** перекрывает `default_config` |
| 2026-06-15 утро | Forest OK, BirdBox gap | Не stream parity — **post-detector acceptance** на `feeder_close` (см. ниже) |

## Что зафиксировалось (fixes that stuck)

1. **`default_config.yaml` в репо** — канон: `subtype=1`, `openvino_native_lores_imgsz: false`, role floors `feeder_close`/`feeder_far`, Bird override `0.08`.
2. **`scripts/verify-prod-detector-smoke.sh`** + CI drift gate (`verify_merged_detector_config.py`, `test_threshold_resolution.py`).
3. **Коммит `af4cf592e`** — lock detect RTSP `subtype=1` для Trapper VPS.
4. **Role-aware CONFIDENCE_FLOORS** — global → role → camera hierarchy; `feeder_far` weak-box acceptance (`9ac370932`).
5. **Detection acceptance gap fix** для feeder cameras (`5fc408ea9`) — частично; BirdBox всё ещё gap на prod.

## Baseline: рабочая сессия Forest (2026-06-15)

```
10:56:59 recording_session_summary triggered_camera=Forest
  yolo_frames_with_raw_boxes=188  yolo_frames_with_tracks=167
  yolo_accepted_boxes_total=216  post_fusion_persisted=12 (trigger_graph)
  db_persist_success=true  video=data/recordings/2026/06/15/105442/video.mp4
  mqtt_events_in_window=6
```

Сравнение воронки:

| Источник | Forest 10:54–10:56 | BirdBox 11:04–11:05 |
|----------|-------------------|---------------------|
| Frigate MQTT | 0–6 events | **19 events**, score 0.762 |
| YOLO raw frames | 188 | 64 |
| YOLO accepted | 216 | **0** |
| Tracks | 167 | **0** |
| Persist | 12 | **0** |
| `detection_acceptance_gap` | false | **true** |

## Почему BirdBox не работает (гипотезы по приоритету)

1. **`scoring_moving_roi_min_motion_score: 0.3`** только на `feeder_close` — близкая кормушка, птицы сидят неподвижно → scoring отбрасывает все raw boxes (подтверждает `quality_reject_counts: {}` при gap — отсев до quality layer или на binary accept).
2. **Разный RTSP endpoint** (`192.168.1.129` vs `.101`) — возможны таймауты Frigate go2rtc (`i/o timeout` в логах 2026-06-13); Hub всё же получает 64 raw boxes → stream частично жив.
3. **Нет per-camera override** в prod `user_config` — только role presets; Forest дополнительно выигрывает от `feeder_far.min_center_dist`.
4. **Frigate-only extension** на BirdBox (`session_extended_by_frigate_only=98`) — длинная сессия без YOLO tracks, типичный FP-empty pattern.

**Действие:** диагностика в отчёте; prod config **не меняли** (кроме rollback-бэкапа). Следующий шаг — parity checklist + сравнение acceptance trace на клипе BirdBox vs Forest.

## Открытые пункты

| Пункт | Статус |
|-------|--------|
| BirdBox parity | Открыт — acceptance gap |
| Disk VPS | **90%** (197G/232G) — риск для record/persist |
| Deploy gates WSL | `DEPLOY_URL` localhost vs `https://birdlense.eyera.info` — smoke с WSL не эквивалентен prod HTTPS |
| TG proxy | Intermittent SSL/ConnectionError; retry через socks5 proxy |
| Persist latency | `persist_duration_ms` 53s на Forest — critical breach, но TG ушёл |

## Actionable improvements

### Per-camera parity checklist

Перед «чинить пороги» на prod:

- [ ] `detect_stream` URL = Frigate detect, **`subtype=1`**
- [ ] `recording_session_summary` на **каждой** камере: raw → accepted → tracks → persist
- [ ] Сравнить `tuning_role` preset с `default_config` (merged, не UI-only)
- [ ] Один эталонный клип per camera в `data/recordings/` + offline regen
- [ ] Frigate MQTT count vs Hub `mqtt_events_in_window` в том же окне

### Скрипт compare (идея)

```bash
# scripts/compare_camera_funnel.py — парсит docker logs recording_session_summary
# группирует по triggered_camera, выводит median raw/accepted/tracks/persist за 24h
```

Интеграция: `make verify-prod-detector-smoke` warn если любая enabled camera имеет `accepted=0` при `raw>10` за последние N сессий.

### CI / repo

- Держать долгоживущие фиксы в `default_config.yaml`, не в prod `user_config`.
- PR с изменением `camera_tuning_by_role` → обязательный `test_camera_tuning_role.py` + drift gate.

## Ссылки

- [prod-rollback-points.md](./prod-rollback-points.md)
- [hub-detector-runbook.md](./hub-detector-runbook.md)
- [yolo-blind-runbook.ru.md](../ru/yolo-blind-runbook.ru.md)
- [intel_igpu_inference_guide.md](../strategy/intel_igpu_inference_guide.md)
