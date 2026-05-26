# Runbook: «слепой YOLO» (Frigate видит, детектор молчит)

Симптом: в UI есть записи по движению Frigate, но **нет боксов/треков YOLO**, метрика `yolo_frames_with_tracks` = 0, в System Dashboard статус **Blind**.

## Быстрая диагностика (5 минут)

1. **System → YOLO Detector Health**
   - `Healthy` — детектор отвечает в текущей сессии.
   - `Degraded` — подозрение (suspected) или Frigate-only без YOLO.
   - `Blind` — подтверждённая слепота или активен `yolo_blind_alert`.
2. **Detection Quality Dashboard** — `blind_score`, события `yolo_blind_confirmed` / `yolo_blind_recovered`.
3. **Логи процессора** — `recording_session_summary`, `yolo_blind_confirmed`, `FileNotFoundError` (OpenVINO IR).
4. **Gauges** — `data/diagnostics/processor_runtime_stats.json`:
   - `yolo_blind_alert`, `yolo_blind_status`, `yolo_blind_phase_live`
   - `yolo_frames_with_tracks_session`, `session_extended_by_frigate_only_session`
   - `stream_probe_width`, `stream_probe_height`, `stream_probe_fps`

## Чеклист: Backend и конфиг

| Проверка | Где | Ожидание |
|----------|-----|----------|
| `processor.inference_backend` | Settings / `user_config` | `torch` для smoke; `openvino` только при валидном IR |
| `processor.inference_device` | Settings | `cpu` / `intel:gpu` — устройство доступно в контейнере |
| `processor.binary_imgsz` | Settings | Совпадает с экспортом модели (часто **640** для BRG) |
| `processor.models.binary_openvino` | Settings | Каталог с `*.xml` **существует** (не «фантомный» абсолютный путь) |
| `video.lores_wh` | Settings | Согласован с потоком; неверный lores → пустой кадр для YOLO |
| `processor.min_confidence_binary` | Settings | Не завышен в `user_config` (старые 0.22+OV часто «режут» всё) |
| Light gate | `processor.light_gate_*` | При ночных клипах — много `low_light_blocked_frames` |
| Frigate-only | runtime summary | `session_extended_by_frigate_only` >> 0 при `yolo_raw_boxes_total` = 0 |

**Merge:** `default_config.yaml` + `user_config.yaml` — старый `user_config` перекрывает дефолты (torch/cpu, min_conf 0.12). Сверьте фактический merge в Config Audit.

## Чеклист: фильтры после детектора

- `detection_quality` / scoring — отбрасывает слабые боксы (смотрите `yolo_accepted_boxes_total` vs `yolo_raw_boxes_total`).
- `static_object_filter` — может убрать «застывшие» объекты; при нуле raw boxes проблема **до** фильтров.
- Interest zones — `detection_interest_zones_required` отсекает кадры вне ROI.

## Геометрия боксов (letterbox / смещение рамок)

См. **`docs/ru/detection-geometry.ru.md`**: единый `frame_geometry`, IoU gate, parity overlay, `validate_bbox_parity.py`.

## Torch vs OpenVINO (один клип)

```bash
cd /home/gfer/BirdLense
make compare-detector-bboxes-help
# Пример: два прогона PT и OV на одном mp4
python3 scripts/compare_detector_bboxes.py \
  --video /path/to/clip.mp4 \
  --pt app/processor/models/detection/weights/best.pt \
  --openvino app/processor/models/detection/weights/best_openvino_model
```

Если PT даёт боксы, а OV — нет: проблема в IR/imgsz/device, не в Frigate.

## Эталонные клипы (quality gate)

| ID | Роль | Ожидание |
|----|------|----------|
| **1816** | шум / ложные срабатывания | допустимо мало треков |
| **1819** | птицы | **`yolo_frames_with_tracks` > 0** после regen |

```bash
# Локально (нужны веса и путь к mp4):
export YOLO_GOLDEN_CLIP_1819=/path/to/video_1819.mp4
python3 scripts/yolo-golden-clips-gate.py

# Или pytest (логика gate без тяжёлого YOLO):
cd app/processor && PYTHONPATH=src SKIP_HEAVY_PROCESSOR_TESTS=1 \
  python3 -m pytest tests/test_yolo_golden_clips_gate.py tests/test_yolo_blind_monitor.py -q
```

## Автоматическая реакция системы

1. **Live:** `yolo_blind_alert=1` если Frigate-only без YOLO tracks дольше `detection.yolo_blind_alert_seconds` (по умолчанию 30 с).
2. **Сессия:** FSM `none → suspected → confirmed`; quickcheck с пониженным conf (`yolo_blind_quickcheck_*`).
3. **Финализация:** `yolo_blind_confirmed`, событие в `detector_health_events`, active learning / fusion gate.
4. **Self-heal** (если включён): soft_clear / reinit / restart по политике в `recording_finalize`.

## Типичные решения

| Причина | Действие |
|---------|----------|
| Неверный путь OpenVINO | Исправить `binary_openvino` на реальный каталог под `app/processor/` |
| OV на GPU без DRI | `inference_device: cpu` или Intel override в deploy |
| Завышенный confidence | Снизить `min_confidence_binary` / night profile |
| Light gate | Временно ослабить пороги или проверить дневной клип |
| imgsz mismatch | `binary_imgsz` = размер экспорта |
| lores / probe | System Health: probe FPS/size; пересканировать поток |
| Веса отсутствуют | Положить `best.pt` + IR, `make deploy` |

После правок: **пересоздать контейнер** (`docker compose up -d --force-recreate birdlense`), regen треков на 1819, проверить Dashboard.

## API

`GET /api/ui/system/yolo-detector-health?hours=24` — статус для UI и smoke.
