# Detection weights (`detection/weights/`)

## Production (2026-05)

| Артефакт | Путь | Назначение |
| -------- | ---- | ---------- |
| **TrapperAI PyTorch** | `weights/trapper_ai_v02_2024.pt` | Бинарный детектор (Bird + Eurasian Red Squirrel) |
| **TrapperAI OpenVINO** | `weights/trapper_ai_v02_2024_openvino_model/` | IR FP16 @640 для VPS iGPU |

Конфиг: `processor.models.binary`, `processor.models.binary_openvino`, `detector_scope: []` (все классы), `detector_native_class_labels: true`, `binary_imgsz: 704`.

**Грызуны (Rodent)** не детектируются бинарником. EU-классификатор — `classification/weights/best.pt`.

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

**`classification/weights/best.pt`** — [HF `gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu).
