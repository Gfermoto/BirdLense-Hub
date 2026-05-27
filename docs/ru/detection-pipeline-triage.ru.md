# Триаж: OpenCV шум, промах bbox, пустой классификатор

## Симптомы (прод VPS, камера Forest)

| Метрика | Значение |
|---------|----------|
| Записи OpenCV | частые (~17 с) |
| `yolo_raw_boxes_total` | часто > 0 |
| `yolo_accepted_boxes_total` | почти всегда **0** |
| `post_fusion_persisted` | **0** → в UI нет «события» |
| Frigate на Forest | `mqtt_events_in_window: 0` в сессиях |

Классификатор и ReID работают по **crop**; если bbox мимо или отфильтрован — «пустое поле», смысл пайплайна теряется.

## Три независимые проблемы

### 1. Шум OpenCV (лишние записи)

На проде сейчас (проверено в контейнере):

- `triggers.opencv.min_contour_area: **180**` (в репо `user_config` — 360; на сервере агрессивнее)
- `check_every_n_frames: 1`

→ движение ветки/тени даёт клип без птицы, грузит CPU/YOLO.

**Действия:** поднять `min_contour_area` / `day_min_contour_area` (320–360), `check_every_n_frames: 2–3`, проверить маски исключения. См. `app/app_config/user_config.detection-opencv-tune.example.yaml`.

### 2. Промахи / отсутствие accepted bbox

Цепочка отсечения (по логам):

1. **ByteTrack без `track_id`** при наличии raw boxes → предупреждение в логах; fallback IoU включён (`iou_id_fallback_live_enabled`).
2. **Порог conf** `min_confidence_binary_bird: 0.28` — сырые боксы ниже порога не попадают в accepted.
3. **`rejected_detector_below_store_floor`** — редкие кадры с треком, но без записи в БД.
4. **Геометрия:** `detect_use_native_resolution: true` + `binary_imgsz: 704` — детектор на native 1280×720, внутренний letterbox модели; при сбое unmap bbox в UI «уезжают». Gate `detection.bbox_iou_gate_action: warn` (не reject).

**Диагностика:**

```bash
docker cp scripts/diagnose_detection_funnel.py birdlense:/tmp/
docker exec birdlense python /tmp/diagnose_detection_funnel.py \
  --video /app/data/recordings/2026/05/19/151021/video.mp4 \
  --frames 40 --frame-step 3 \
  --write-report /tmp/funnel.json
```

Включить оверлеи (кратко, на 20 кадров):

```yaml
processor:
  bbox_parity_debug_enabled: true
  bbox_parity_debug_max_frames: 20
```

Смотреть `data/diagnostics/bbox_parity/` и API `GET /api/ui/debug/bbox-parity`.

### 3. Cooldown без requeue (пропуск события)

`min_seconds_between_recordings: 8` + OpenCV **без** `mark_pending` → триггер терялся.

**Исправлено в коде:** `OpenCVMotionDetector.mark_pending()` — повторная постановка после defer.

## Порядок работ (параллельно с SOTA-14)

1. Прогнать `diagnose_detection_funnel.py` на golden + проблемный клип.
2. Подкрутить OpenCV на проде (контур 320+, `check_every_n_frames: 2`).
3. Сверить bbox: parity debug или A/B `scripts/compare_detector_bboxes.py` (PT vs OpenVINO).
4. При стабильных accepted > 0 — вернуться к SOTA-14 (каталог 526/526).

## Связанные документы

- [benchmark-golden-clips.ru.md](benchmark-golden-clips.ru.md)
- [tracking-parity.ru.md](tracking-parity.ru.md)
- `docs/user/troubleshooting.md` — Slow frame, Frigate filters
