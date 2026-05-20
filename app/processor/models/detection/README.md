# Detection weights (`detection/weights/`)

## Production default (NABirds pivot, 2026-05)

| Артефакт | Путь | Назначение |
|----------|------|------------|
| PyTorch | `weights/best_NABirds.pt` | **Единственный** бинарный детектор птиц (класс `bird` → Bird) |
| OpenVINO | `weights/nabirds_openvino_v1/` | IR после `validate_ov_parity.py` (parity <5%) |
| Архив BRG | `weights/best.pt`, `weights/best_openvino_model/` | **Deprecated** — слепота на рассвете, несовпадение grid OV |

Конфиг: `processor.models.binary`, `processor.models.binary_openvino`, `processor.detector_scope: [Bird]`, `processor.binary_predict_class_allowlist: [0]`.

**Грызуны (Rodent)** больше не детектируются бинарником. EU-классификатор (`classification/weights/best.pt`) — виды птиц.

## Экспорт OpenVINO

```bash
python3 scripts/export_nabirds_to_openvino.py --imgsz 640 --precision fp32
python3 scripts/validate_ov_parity.py --ov-dir app/processor/models/detection/weights/nabirds_openvino_v1
```

См. [`docs/ml/MODEL_EXPORT_GUIDE.md`](../../../docs/ml/MODEL_EXPORT_GUIDE.md).

## Совместимость / диагностика

- **`yolo11n.pt`** + `binary_predict_class_allowlist: [14]` — legacy COCO bird, не прод-дефолт.
- **`compare_detector_bboxes.py`**, **`debug_ov_conversion.py`** — parity и регрессии.

## EU classifier (отдельно)

**`classification/weights/best.pt`** — [HF `gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu).
