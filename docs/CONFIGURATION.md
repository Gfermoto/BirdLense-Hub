# Конфигурация

Основной конфиг: `app/app_config/user_config.yaml`. Шаблон: `user_config.orin.example.yaml`.

Полный список параметров: `app/app_config/default_config.yaml` (не редактировать — перекрывается user_config).

### Ключевые секции (Orin)

```yaml
processor:
  inference_backend: onnxruntime
  inference_device: cuda:0
  classifier_engine: birder_eu
  models:
    binary: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
    classifier: models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx
    reid_embedder: models/reid/ornimetrics/reid_embedder.onnx
  tracker: models/tracker/bytetrack_birdlense.yaml
  reid:
    device: cuda:0
    inference_backend: onnxruntime

video:
  encoding: jetson
  capture_backend: auto
```

Через `.env`:

| Переменная | Описание |
|-----------|----------|
| `FLASK_SECRET_KEY` | 32-char hex для сессий |
| `PROCESSOR_SECRET` | 32-char hex для API |
| `MCP_TOKEN` | Bearer token для MCP |
| `BIRDLENSE_ENV` | production |

См. [`user/configuration.md`](user/configuration.md).
