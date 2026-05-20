# NABirds + OpenVINO — финальная валидация хотфика (2026-05-20)

## Вердикт

| Критерий | Статус |
|----------|--------|
| FP-шум (принятые боксы) | **Снят** — `accepted` упал ~17× при том же OV |
| Конфиг в репо = прод | **Да** — `127016a4`, deploy OK |
| IR на месте после deploy | **Да** — volume + `sync-models` |
| Статичная кормушка (negative) | **Пройден** — offline @0.28 → 0 боксов; live `accepted` ≪ `raw` |
| Реальная птица (positive) | **Ожидание live** — после 08:45 UTC новых визитов в БД ещё нет |

**Принцип:** precision важнее recall; баланс — видеть птицу с conf ≥ 0.28, не забивать БД шумом.

---

## Этап 1 — Code as Config

Зафиксировано в `default_config.yaml` (коммиты `d86abd7b`, `127016a4`):

```yaml
min_confidence_binary: 0.28
min_confidence_binary_bird: 0.28
openvino_min_confidence_binary_bird: 0.28
openvino_binary_bird_score_scale: 1.0      # не 8.5 (legacy BRG)
openvino_binary_track_ultralytics_conf: 0.12
binary_track_max_det: 60
ultra_weak_box_salvage_enabled: false
```

Комментарии + forensic: [`nabirds_fp_forensic_20260520.md`](nabirds_fp_forensic_20260520.md).

Прод `user_config.yaml` (не перезаписывается deploy): те же значения подтверждены после deploy.

---

## Этап 2 — Deploy

- `make sync-models` — OK локально и на VPS  
- `make deploy` — OK, UI http://185.218.111.196:8085  
- Логи после старта (08:45 UTC):

```
detector_backend=openvino
ultralytics_device_label=intel:gpu
binary_path=.../best_NABirds_openvino_model
```

---

## Этап 3 — Метрики «До / После»

Окно: сессии `session_runtime_metrics` с `2026-05-20T08:00` UTC.

| Эра | Сессий | avg `yolo_raw_boxes` | avg `yolo_accepted` | max raw | persisted |
|-----|--------|----------------------|---------------------|---------|-----------|
| **До хотфика** (< 08:35) | 11 | **832** | **832** | 1113 | 11/11 |
| **После** (≥ 08:35) | 3 | 393 | **50** | 524 | 3/3 |

**Кратность по шуму (accepted):** ~**17×** снижение среднего числа принятых боксов.

Пример сессии после хотфика: id **1453** — `raw=524`, **`accepted=9`** (фильтр 0.28 отсекает мусор; `raw` ещё считает низко-conf track @0.12).

### Negative test (статичная кормушка)

Запись `082357/video.mp4`, кадр 10, OV GPU:

| `track(conf)` | Боксов bird |
|---------------|-------------|
| 0.12 | 1–2 |
| **0.28** | **0** |

Порог принятия **0.28** — мусор на статике не должен проходить в визиты.

### Positive test

После полного deploy (08:45+) новых `species_visit` пока нет — нужна 1–2 live-сессии с птицей.  
Критерий успеха: детекция с detector_conf ≥ 0.28, вид ≠ только Unknown.

---

## Почему `yolo_raw_boxes` ещё может быть сотни

`yolo_raw_boxes_total` — **до** per-label фильтра (Ultralytics `track(conf≈0.12)`).  
`yolo_accepted_boxes_total` — **после** порога 0.28 и геометрии — **операционная метрика чистоты**.

Опциональное улучшение (Next): `openvino_binary_track_ultralytics_conf: 0.28` — выровнять track с accept, снизить и `raw`.

---

## Этап 4 — Next Steps

1. **ROI mask** — полигон/прямоугольник статической кормушки; игнор боксов с центром в ROI (конфиг `processor.feeder_static_roi_norm`).
2. **Temporal filter** — учитывать track только если bbox стабилен ≥ N кадров (например N=3 при 7 FPS).
3. **Fine-tuning** — датасет негативов: 500+ кадров кормушки без птиц + hard negatives; дообучение головы NABirds.
4. **Мониторинг** — алерт если `accepted/raw > 0.5` на 3 сессиях подряд при пустой кормушке.

---

## Ссылки

- Forensic: `docs/reports/nabirds_fp_forensic_20260520.md`
- Migration: `docs/reports/migration_final_report.md`, `docs/reports/nabirds_migration_20260520.md`
- Export/parity: `docs/ml/MODEL_EXPORT_GUIDE.md`
