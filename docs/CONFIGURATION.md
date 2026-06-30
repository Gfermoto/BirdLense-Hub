# Конфигурация

Основной конфиг: `app/app_config/user_config.yaml`. Шаблон: `user_config.orin.example.yaml`.

Полный список параметров: `app/app_config/default_config.yaml` (не редактировать — перекрывается user_config).

### Ключевые секции

```yaml
processor:
  inference_backend: onnx            # только ONNX
  inference_device: cuda:0           # CUDA GPU
  models:
    binary_onnx: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
    classifier_onnx: models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx
    reid_onnx: models/reid/ornimetrics/reid_embedder.onnx
    welfare_onnx: models/welfare/ornimetrics/embedder.onnx
    welfare_scorer: models/welfare/ornimetrics/welfare_scorer.npz
  tracker: bot_sort                   # ByteTrack unstick
  gstreamer:                          # NVDEC/NVENC pipeline
```

Через `.env`:

| Переменная | Описание |
|-----------|----------|
| `FLASK_SECRET_KEY` | 32-char hex для сессий |
| `PROCESSOR_SECRET` | 32-char hex для API |
| `MCP_TOKEN` | Bearer token для MCP |
| `BIRDLENSE_ENV` | production |

См. [`user/configuration.md`](user/configuration.md).