# Birder EU classifier PoC (#516)

**Date:** 2026-05-27  
**Issue:** https://github.com/Gfermoto/BirdLense-Hub/issues/516

## Выбор модели

| Модель | Классов | EU | Eurasian jay | Вес | Latency CPU (256²) |
|--------|---------|----|--------------|-----|------------------|
| **convnext_v2_tiny_eu-common256px** (primary PoC) | 707 | Collins / eu-common | id 232 `Eurasian jay` | ~108 MB | **~159 ms/crop** |
| rope_vit_reg4_b14_capi-intermediate-eu-common | 707 | да | да | ~346 MB | не бенчмаркали (Wave B) |
| dennisjooo EfficientNetB2 | 525 | нет | нет | — | отклонён |
| gfermoto/birdlense-birds-eu (YOLO) | ~491 | да | да | — | legacy, не целевой SOTA |

**Рекомендация prod (после Wave B):** `birder_eu` + `convnext_v2_tiny_eu-common256px` OpenVINO; при нехватке FPS — тот же стек 384px или `uniformer_s_eu-common256px`.

## Артефакты в репо

```
app/processor/models/classification/weights/
  birder_convnext_v2_tiny_eu_common256px/
    *.pt, *.json, class_labels.txt, birdlense_manifest.json
  birder_convnext_v2_tiny_eu_common256px_openvino/
    openvino_model.xml (+ .bin), class_labels.txt
```

Скрипты:

- `scripts/download_birder_classifier.py`
- `scripts/export_birder_classifier_to_openvino.py`
- `scripts/test_birder_classifier_smoke.py`

## Интеграция (Wave A, в коде)

- `processor.classifier_engine: birder_eu` (новый default в `default_config.yaml`)
- `app/processor/src/inference/birder_eu_classifier.py`
- `detection_strategy.py` — crop path как у EfficientNet
- Каталог allowlist: 707 меток из `class_labels.txt`
- Класс Birder `Unknown` (id 638) → hub `Unknown Bird`

## Smoke

```bash
. .venv-birder/bin/activate
python scripts/download_birder_classifier.py
python scripts/export_birder_classifier_to_openvino.py --benchmark
python scripts/test_birder_classifier_smoke.py --backend openvino
python scripts/test_birder_classifier_smoke.py --backend torch
```

`storm_bird` frame 50: модель выдала класс `Unknown` (в таксономии Birder), не конкретный вид — ожидаемо для сложного кропа без дообучения на кормушке.

## Следующие шаги (Wave B–D)

1. Docker: optional `birder` pip или только OpenVINO bundle в образе.
2. Бенчмарк на 10–20 ваших mp4 + сравнение с Frigate/BirdNET.
3. Один reconcile mapping Collins → eBird common names.
4. `make deploy` после `user_config`: `classifier_engine: birder_eu`.
