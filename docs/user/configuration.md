# Конфигурация BirdLense Hub

## Основной файл

`app/app_config/user_config.yaml` — переопределяет `default_config.yaml`.

Шаблон: `app/app_config/user_config.orin.example.yaml`.

## Ключевые параметры

```yaml
processor:
  inference_backend: onnx            # только ONNX
  inference_device: cuda:0           # GPU

  binary_onnx: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
  classifier_onnx: models/classification/chriamue_bird_species_classifier/model.onnx
  reid_onnx: models/reid/ornimetrics/reid_embedder.onnx
  welfare_onnx: models/welfare/ornimetrics/embedder.onnx
  welfare_scorer: models/welfare/ornimetrics/welfare_scorer.npz

  binary_imgsz: 640
  min_confidence_binary: 0.12
  tracker: bot_sort
  gstreamer:
    input_pipeline: "rtspsrc location={url} ... nvdec ! nvvidconv ! video/x-raw"
```

## Через .env

| Переменная | Назначение |
|-----------|-----------|
| `FLASK_SECRET_KEY` | 32-char hex для Flask сессий |
| `PROCESSOR_SECRET` | 32-char hex для API между web и processor |
| `MCP_TOKEN` | Bearer token для MCP доступа |
| `BIRDLENSE_ENV` | `production` для продакшн режима |
| `BIRDLENSE_STRICT_API_AUTH` | 1 — строгая аутентификация |

## Восстановление

```bash
make restore-config   # восстановить user_config.yaml из бэкапа
```

См. [`recovery-config.md`](recovery-config.md) и [`scenarios.md`](scenarios.md).