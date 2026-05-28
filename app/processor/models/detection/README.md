# Detection weights (`detection/weights/`)

## Production (2026-05)

| Артефакт | Путь | Назначение |
| -------- | ---- | ---------- |
| **TrapperAI PyTorch** | `weights/trapper_ai_v02_2024.pt` | Бинарный детектор (Bird + Eurasian Red Squirrel) |
| **TrapperAI OpenVINO** | `weights/trapper_ai_v02_2024_openvino_model/` | IR FP16 @640 для VPS iGPU |

Конфиг: `processor.models.binary`, `processor.models.binary_openvino`, `binary_imgsz: 704`. Классы — из `class_maps/trapper_ai_v02_2024.yaml` (allowlist `[0,5]`, scope Bird + Eurasian Red Squirrel); при старте пайплайна карта применяется в `detector_class_map.apply_class_map_to_config`.

**Грызуны (Rodent)** не детектируются бинарником. EU-классификатор — см. [`classification/README.md`](../classification/README.md).

## Архив (не прод)

| Артефакт | Путь | Примечание |
| -------- | ---- | ---------- |
| CTDR Species v3 | `weights/ctdr_species_v3.pt`, `ctdr_species_v3_openvino_model/` | Отклонён после showdown; оставлен для экспериментов |

## Экспорт OpenVINO

```bash
python3 scripts/export_trapper_to_openvino.py --imgsz 640 --precision fp16
```

См. [`docs/ml/MODEL_EXPORT_GUIDE.md`](../../../docs/ml/MODEL_EXPORT_GUIDE.md).

## Совместимость / диагностика

- **`compare_detector_bboxes.py`**, **`debug_ov_conversion.py`** — parity и регрессии.
- **`app/scripts/verify-detector-weights.sh`** — sha256 Trapper PT + OV IR.

## EU classifier (отдельно)

**`classification/weights/convnext_v2_tiny_eu-common256px.pt`** — Birder eu-common 707 (#516).
