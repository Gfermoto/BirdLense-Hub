# Конфигурация BirdLense Hub

## Основной файл

`app/app_config/user_config.yaml` — переопределяет `default_config.yaml`.

Шаблон: `app/app_config/user_config.orin.example.yaml`.

## Ключевые параметры (Orin)

```yaml
processor:
  inference_backend: onnxruntime
  inference_device: cuda:0
  classifier_engine: birder_eu
  classifier_inference_backend: onnxruntime
  classifier_inference_device: cuda:0
  binary_imgsz: 704
  min_confidence_binary: 0.12
  models:
    binary: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
    classifier: models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx
    reid_embedder: models/reid/ornimetrics/reid_embedder.onnx
  tracker: models/tracker/bytetrack_birdlense.yaml
  reid:
    device: cuda:0
    inference_backend: onnxruntime

video:
  encoding: jetson          # NVENC/NVDEC
  capture_backend: auto     # ffmpeg_nvmpi или opencv
  record_hw_encode: false  # false = libx264 для MP4; true = аппаратная запись (NVENC)
```

Модели welfare (`embedder.onnx`, `welfare_scorer.npz`) монтируются в контейнер и обрабатываются в finalize (`welfare_runtime.py`) после ReID. Порог скрининга: `processor.welfare.distance_review_threshold`. См. [OVERVIEW](../OVERVIEW.md).

## Через .env

| Переменная | Назначение |
|-----------|-----------|
| `FLASK_SECRET_KEY` | 32-char hex для Flask сессий |
| `PROCESSOR_SECRET` | 32-char hex для API между web и processor |
| `MCP_TOKEN` | Bearer token для MCP доступа |
| `BIRDLENSE_ENV` | `production` для продакшн режима |
| `BIRDLENSE_STRICT_API_AUTH` | `1` — строгая аутентификация |
| `BIRDLENSE_INFERENCE_BACKEND` | `onnxruntime` (дефолт на Orin) |
| `BIRDLENSE_REID_BACKEND` | `onnxruntime` |
| `BIRDLENSE_WELFARE_RUNTIME_ENABLED` | `1` / `true` — включить welfare в finalize |
| `BIRDLENSE_WELFARE_DEVICE` | `cuda:0` — устройство для welfare embedder |

## Восстановление

```bash
make restore-config   # восстановить user_config.yaml из бэкапа
```

См. [`recovery-config.md`](recovery-config.md) и [`scenarios.md`](scenarios.md).
