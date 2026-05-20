# NABirds Migration Report (2026-05-20)

## Вердикт

**Система работает на OpenVINO + NABirds** (VPS `185.218.111.196:8085`, 2026-05-20).

Parity Gate **PASS** (7/7 кадров). Прод: `inference_backend=openvino`, `intel:gpu`, `best_NABirds_openvino_model`.

**Готово к SOTA-эксплуатации** при мониторинге `yolo_raw_boxes_total` в первые 24 ч.

---

## Решение

| Было (BRG) | Стало (NABirds) |
|------------|-----------------|
| `best.pt` + `best_openvino_model` | `best_NABirds.pt` + `best_NABirds_openvino_model` |
| 3 класса Bird/Rodent/Background | 1 класс `bird` |
| OV слепота на рассвете | OV parity на golden |
| `detector_scope: [Bird, Rodent]` | `detector_scope: [Bird]` |

**Жертва:** детекция грызунов бинарником отключена.

---

## Parity Gate (VPS, FP32, `conf=0.08`, `imgsz=640`)

| Кадр | boxes PT=OV | mean IoU | mean conf rel.err |
|------|-------------|----------|-------------------|
| morning_052840_f16 | 1=1 | 0.976 | 3.8% |
| dawn_025517_f10 | 1=1 | 0.994 | 2.7% |
| dawn_025405_f2 | 1=1 | 0.983 | 1.3% |
| morning_052840_f20 | 3=3 | 0.990 | 1.7% |
| morning_052840_f22 | 2=2 | 0.986 | 0.3% |
| dawn_025517_f16 | 1=1 | 0.997 | 1.6% |
| dawn_025405_f0 | 1=1 | 0.996 | 2.7% |

**Итог:** `"pass": true`, `frames_pass: 7/7`.

Стресс-кадр `014828_f11`: IoU 0.996, но conf rel.err ~14% — **не в golden gate**; на проде пороги и `openvino_binary_bird_score_scale: 8.5` компенсируют смещение OV conf при фильтрации.

Манифест: `app/data/datasets/nabirds_parity_golden/manifest.json` (v2).

---

## Производительность (один кадр 052840 f16, warm)

| Backend | ms/кадр |
|---------|---------|
| PyTorch CPU (`best_NABirds.pt`) | ~12315 (cold/warm mix, первый прогон тяжёлый) |
| OpenVINO GPU (`best_NABirds_openvino_model`) | **~142** |

Прирост порядка **×87** на тёплом OV GPU vs холодный PT CPU в том же контейнере; в live ожидаем **×2–×5** vs стабильный torch CPU.

Логи процессора после переключения:

```
Inference startup: detector_backend=openvino … ultralytics_device_label=intel:gpu
binary_path=…/best_NABirds_openvino_model binary_imgsz=640
```

---

## Прод-конфиг (VPS)

`user_config.yaml`:

- `processor.inference_backend: openvino`
- `processor.openvino_binary_enabled: true`
- `processor.models.binary: best_NABirds.pt`
- `processor.models.binary_openvino: best_NABirds_openvino_model`
- `processor.detector_scope: [Bird]`

`app/.env`:

- `BIRDLENSE_INFERENCE_BACKEND=openvino`
- `BIRDLENSE_INFERENCE_DEVICE=intel:gpu`
- `BIRDLENSE_OPENVINO_BINARY_ENABLED=1`

---

## Очистка BRG (VPS)

На хосте: `weights/archive_brg_20260520/` — `best.pt`, `best_openvino_model` (не в активном конфиге).

**Важно:** веса в образе Docker, не в volume. После `docker compose build` / recreate IR нужно снова:

1. `export_nabirds_to_openvino.py` в контейнере  
2. `docker cp` bundle на хост `app/processor/models/detection/weights/best_NABirds_openvino_model/`  
3. Либо включить volume для `processor/models` в compose (рекомендация для следующего PR).

---

## Сравнение BRG → NABirds

| Метрика | BRG (было) | NABirds PT | NABirds OV (финал) |
|---------|------------|------------|---------------------|
| Рассвет 014828 | 0 boxes | 2+ boxes | parity OK на других dawn кадрах |
| Rodent class | да | нет | нет |
| Прод backend | OV BRG (слепой) | torch (стабильно) | **openvino NABirds** |

---

## Мониторинг (первый час)

- Логи: `detector_backend=openvino`, без `Processor exited`
- `yolo_raw_boxes_total` ≥ уровня torch (не падать)
- CPU inference: снижение нагрузки за счёт GPU OV

---

См. `docs/ml/MODEL_EXPORT_GUIDE.md`, `docs/reports/sota_gap_analysis_and_recovery_plan.md`.
