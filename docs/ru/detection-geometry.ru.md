# Геометрия детектора: letterbox, live/regen parity, IoU gate

Единый модуль: `app/processor/src/frame_geometry.py` (реэкспорт в `yolo_geometry.py` для совместимости).

## Letterbox vs native

| Режим | Конфиг | Поведение |
|-------|--------|-----------|
| **Letterbox** | `processor.inference_lores_wh` / `inference_lores_px` | Сохранение aspect ratio, pad 114 BGR |
| **Native** | `processor.detect_use_native_resolution: true` | Кадр без letterbox (только enhance) |

Целевой canvas для **live** и **regen** совпадает, если не задан явный override:

- `processor.track_regen_lores_wh` / `track_regen_lores_px` — только для regen.

## API подготовки кадра

```python
from frame_geometry import prepare_detector_pipeline_frame

det_bgr, det_hw, overlay_hw, meta = prepare_detector_pipeline_frame(
    source_bgr,
    app_config,
    mode="live",  # или "regen"
)
```

- `det_*` — тензор для YOLO.
- `overlay_hw` — координаты для UI/записи (исходный кадр).
- `meta` — scale/pad для `unpad_boxes` / `pad_boxes`.

## Unmap боксов

```python
from frame_geometry import unpad_boxes

overlay_norm = unpad_boxes(
    bbox_norm_on_detector,
    source_shape_hw=overlay_hw,
    letterbox_shape_hw=det_hw,
)
```

## IoU Gate

Проверка **roundtrip** геометрии: bbox на letterbox-канвасе → unmap на source → pad обратно → IoU с исходным.

| Ключ | По умолчанию |
|------|----------------|
| `detection.bbox_iou_gate_enabled` | `true` |
| `detection.bbox_iou_gate_min` | `0.85` |
| `detection.bbox_iou_gate_action` | `warn` (`reject` — отбрасывать боксы) |

Метрики: `bbox_iou_gate_rejected_total`, gauge `bbox_parity_roundtrip_iou_p50`.

## Parity overlay (debug)

| Ключ | Описание |
|------|----------|
| `processor.bbox_parity_debug_enabled` | Сохранять кадры с боксами |
| `processor.bbox_parity_debug_max_frames` | Лимит кадров на сессию |

Каталог: `data/diagnostics/bbox_parity/<session_id>/` — зелёный = raw, красный = accepted.

API: `GET /api/debug/bbox-parity?session_id=...` (пароль настроек).

## Проверка

```bash
cd app/processor && PYTHONPATH=src python3 -m pytest tests/test_frame_geometry.py tests/test_yolo_geometry.py -q
python3 scripts/validate_bbox_parity.py --video /path/to/clip.mp4
```

Golden clips **1816** (шум) / **1819** (птицы): тот же `validate_bbox_parity.py` + `yolo-golden-clips-gate.py` после regen.

## Runbook «слепой YOLO»

При смещённых рамках сначала проверьте geometry (этот документ), затем `docs/ru/yolo-blind-runbook.ru.md`.
