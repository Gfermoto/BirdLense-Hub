# Паритет bbox детектора (Frigate, #640)

[English](../contributor/detector-bbox-parity.md) · [Тестирование](../contributor/testing.md)

Лёгкий smoke **PyTorch ↔ OpenVINO** по IoU боксов на **Intel iGPU**. Проверка геометрии на одном ролике перед продакшеном на OpenVINO.

## Пропуск без красного CI

Скрипт `scripts/detector_bbox_parity_smoke.py` выходит с **0** и `status: skipped`, если нет mp4, `best.pt` или каталога OpenVINO IR. Переменная `SKIP_DETECTOR_BBOX_PARITY=1` — принудительный пропуск.

## Локально

```bash
export BIRDLENSE_INFERENCE_DEVICE=intel:gpu
export DETECTOR_PARITY_VIDEO=/path/to/clip.mp4
python3 scripts/detector_bbox_parity_smoke.py --min-median-iou 0.45 --clip-id 1819
```

Справка: `make compare-detector-bboxes-help`.

## Порог

Медианный IoU ≥ **0.45** на кадрах, где оба бэкенда видят птицу.
