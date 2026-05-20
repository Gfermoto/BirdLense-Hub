# Model Export Guide (PyTorch → OpenVINO)

Руководство по экспорту бинарного детектора и классификатора BirdLense в OpenVINO IR через Ultralytics, с обязательной проверкой parity перед продом.

**Прод-дефолт (2026-05):** бинарник **`best_NABirds.pt`** (класс `bird` → Bird). BRG `best.pt` / `best_openvino_model` — **архив**, не использовать. Rodent detection **отключён**.

---

## Успешный кейс NABirds (2026-05)

### Экспорт

```bash
make export-nabirds-openvino
# или:
python3 scripts/export_nabirds_to_openvino.py --imgsz 640 --precision fp32
```

Артефакт: `app/processor/models/detection/weights/best_NABirds_openvino_model/`  
Обязательно: каталог оканчивается на **`_openvino_model`**, внутри **`best.xml`** + **`best.bin`** (скрипт копирует из `best_NABirds.xml`).

### Parity gate (обязателен до `inference_backend: openvino`)

```bash
python3 scripts/validate_ov_parity.py \
  --manifest app/data/datasets/nabirds_parity_golden/manifest.json \
  --data-root app/data \
  --pt app/processor/models/detection/weights/best_NABirds.pt \
  --ov-dir app/processor/models/detection/weights/best_NABirds_openvino_model
```

Критерии: IoU ≥ 0.95, conf rel.err ≤ 5%, число bird-боксов совпадает.  
Golden frames: рассветные `recordings/2026/05/20/*` (см. manifest).

### Персистентность при деплое

- IR и PT лежат в `app/processor/models/detection/weights/` (в git: `best_NABirds_openvino_model/best.xml`, `best.bin`, `metadata.yaml`).
- `docker-compose.yml` монтирует этот каталог в контейнер — `force-recreate` не удаляет IR.
- Перед деплоем: **`make sync-models`** (проверка наличия файлов; в `deploy.sh` шаг 1.1).

### Почему отказались от BRG

| Модель | Рассветный кадр | Rodent |
|--------|-----------------|--------|
| BRG `best.pt` | 0 боксов | 3-class (не используется) |
| **NABirds `best_NABirds.pt`** | детекция есть | нет (только птицы) |

BRG OpenVINO был экспортом **другой** модели; parity NABirds требует **отдельного** IR.

---

## Быстрый чеклист перед продом

1. **Parity-скрипт** на реальном кадре с птицей (не нулевой тензор):

   ```bash
   docker exec birdlense python3 /app/scripts/debug_ov_conversion.py \
     --image /app/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4 \
     --frame-index 11 \
     --pt /app/processor/models/detection/weights/best.pt \
     --ov /app/processor/models/detection/weights/best_openvino_model \
     --imgsz 640 --conf 0.001
   ```

2. **Правило выпуска:** `max_abs_diff` pre-NMS logits **< 5%** относительно L2-norm PT **и** `box_count` post-NMS совпадает ±1 на контрольном клипе. Иначе IR **брак**.

3. **`metadata.yaml`:** `half: false`, `imgsz` = `processor.binary_imgsz`, `nms: false` (NMS в Ultralytics, не в IR).

4. **Конфиг:** `processor.binary_imgsz` = export `imgsz`. Несовпадение → падение при старте или слепота.

---

## Экспорт бинарного детектора

### CLI (рекомендуется)

```bash
python3 scripts/train_detector_brg.py \
  --export-openvino-only app/processor/models/detection/weights/best.pt \
  --imgsz 640
```

Или вручную:

```python
from ultralytics import YOLO
YOLO("best.pt").export(format="openvino", imgsz=640, simplify=True)
# → weights/best_openvino_model/ (best.xml, best.bin, metadata.yaml)
```

### Параметры, влияющие на качество

| Параметр | Рекомендация | Риск при ошибке |
|----------|--------------|-----------------|
| `imgsz` | 640 (как `processor.binary_imgsz`) | Масштаб объектов, 0 боксов |
| `half` / FP16 | **false** для первого IR | Потеря мелких птиц |
| `int8` | не использовать без калибровки | Слепота |
| `simplify` | true (ONNX simplify) | Редко ломает граф; проверять parity |
| `dynamic` | false для edge | Несовпадение batch/shape |

### Пути в конфиге

```yaml
processor:
  models:
    binary: models/detection/weights/best.pt
    binary_openvino: models/detection/weights/best_openvino_model
  inference_backend: openvino   # только после parity
  inference_device: intel:gpu
  binary_imgsz: 640
```

Env перекрывает yaml: `BIRDLENSE_INFERENCE_BACKEND`, `BIRDLENSE_BINARY_OPENVINO_PATH`.

---

## Стабилизация на PyTorch (экстренный режим)

Пока OV parity не подтверждён:

```yaml
processor:
  inference_backend: torch
  inference_device: cpu
  openvino_binary_enabled: false
```

```bash
# app/.env
BIRDLENSE_INFERENCE_BACKEND=torch
BIRDLENSE_OPENVINO_BINARY_ENABLED=0
# Опционально: не душить CPU
OMP_NUM_THREADS=4
```

`openvino_binary_enabled: false` и `BIRDLENSE_OPENVINO_BINARY_ENABLED=0` **блокируют** выбор IR при `auto`/`openvino` — всегда `.pt`.

Классификатор может оставаться на OpenVINO отдельно (`classifier_inference_backend`).

После `docker compose up -d --force-recreate birdlense` в логах:

`Inference startup: detector_backend=torch ... binary_path=.../best_NABirds.pt` (или ваш `.pt`).

---

## Troubleshooting OV Degradation

### Симптом: 0 боксов в OV, PT видит птиц

**Шаг 1 — разделить PT vs IR vs веса**

```bash
python3 /app/scripts/debug_ov_conversion.py --image <clip> --pt best.pt --ov best_openvino_model
```

| `diagnosis_hint` | Причина | Действие |
|------------------|---------|----------|
| `logits_diverge_export_or_quantization` | Граф/квантование/версии | FP32 export, обновить ultralytics/openvino, переэкспорт |
| `logits_match_post_nms_differs` | NMS/conf/device в Ultralytics | Сверить `conf`, `imgsz`, OV device |
| `both_blind_check_pt_weights` | **Сами PT-веса слепы** на кадре | Сменить веса (BRG vs NABirds), дообучение BRG v2 |

**Инцидент 2026-05-20:** `best.pt` (BRG) = 0 боксов на рассветном клипе; `best_NABirds.pt` = десятки боксов; `best_openvino_model` (экспорт BRG) = 0. Проблема **не только OV**, но и **BRG PT**. OpenVINO воспроизводил слепоту BRG.

### Симптом: процессор падает при dual-stream

`ValueError: truth value of an array is ambiguous` на `classification_frame or frame` — исправлено: явная проверка `is None` в `detection_strategy.py`.

### Симптом: yaml=torch, а грузится OpenVINO

`BIRDLENSE_INFERENCE_BACKEND=openvino` в `app/.env` **перебивает** yaml. Проверить env после recreate.

### Симптом: auto снова выбрал OV

Задать `processor.openvino_binary_enabled: false` или env `BIRDLENSE_OPENVINO_BINARY_ENABLED=0`.

### Pre-processing (BGR, letterbox)

Ultralytics `YOLO.predict` / `track` для torch и openvino использует **один** predictor pipeline (letterbox + RGB). BirdLense передаёт **BGR** `uint8` кадры; конвертация внутри Ultralytics.

Отдельный letterbox для детектора — в `go2rtc_stream_source` (lores 640). Классификатор может брать `classification_frame` (full-res) — не путать с входом детектора.

Проверка: один и тот же `bgr` в `debug_ov_conversion.py` для PT и OV.

### Версии

Зафиксировать в отчёте экспорта: `ultralytics`, `openvino`, `onnx` (из `metadata.yaml` → `version`). Обновление Ultralytics без переэкспорта IR — частая причина drift.

---

## BRG v2 — правило CI/CD для моделей

1. Обучение → `best.pt`
2. `debug_ov_conversion.py` на golden + dawn clip
3. Если parity OK → `export format=openvino` → повтор скрипта
4. `compare_detector_bboxes.py` на mp4 (геометрия)
5. `make test` / `test_model_recall_on_golden` ≥ 90%
6. Только then: `openvino_binary_enabled: true`, `inference_backend: openvino`

**Active Learning:** кейсы «NABirds видит, BRG нет» → hard examples в датасет BRG v2 (рассвет, дальние мелкие объекты).

---

## Сравнение геометрии (bbox IoU)

```bash
python3 scripts/compare_detector_bboxes.py \
  --video /path/video.mp4 \
  --model-a weights/best.pt \
  --model-b weights/best_openvino_model \
  --bird-class-ids-a 0 --bird-class-ids-b 0 \
  --imgsz 640 --conf 0.08
```

---

## Ссылки

- Веса: `app/processor/models/detection/README.md`
- Инцидент и recovery: `docs/reports/sota_gap_analysis_and_recovery_plan.md`
- OpenVINO Intel: `app/app_config/user_config.openvino-intel.example.yaml`
- UI export: `app/web/services/openvino_weight_export_service.py`
