# Detection (`detection/trapper_ai_v02_2024/`)

| Артефакт | Путь | Назначение |
| -------- | ---- | ---------- |
| **TrapperAI ONNX** | `trapper_ai_v02_2024/trapper_ai_v02_2024.onnx` | Бинарный детектор (Bird + Eurasian Red Squirrel), CUDA EP |
| **Class map** | `class_maps/trapper_ai_v02_2024.yaml` | allowlist `[0,5]` |

Конфиг: `processor.models.binary`, `binary_imgsz: 704`.

```bash
bash scripts/fetch-processor-models-orin.sh
# или: scripts/fetch_trapper_jetson.sh + scripts/export_trapper_detector_onnx.sh
```

Классификатор — [`classification/README.md`](../classification/README.md).
