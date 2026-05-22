# European detector showdown — итог

**Дата:** 2026-05-22  
**Решение:** в прод — **TrapperAI v02.2024** (OpenVINO FP16 @704, detect substream **704×576** без даунскейла в 640²).

## Результаты (быстрый прогон VPS iGPU, conf=0.25)

| Модель | Статус | Комментарий |
|--------|--------|-------------|
| **TrapperAI** | **Победитель → прод** | Чёткие bbox на 1819; на 1816 визуально без ложных (см. `showdown_viz/trapper/`) |
| **Deepfaune v1.3** | **Удалён из проекта** | YOLO только `animal` — шум на тишине, не bird/squirrel |
| **CTDR Species v3** | Архив / не прод | Слабо на 1819 (синица); мало срабатываний |

## Прод-конфиг (уже в `default_config.yaml`)

- `processor.models.binary` → `trapper_ai_v02_2024.pt`
- `processor.models.binary_openvino` → `trapper_ai_v02_2024_openvino_model`
- `detector_scope`: `[]` — все 18 классов Trapper
- `detector_native_class_labels`: `true`
- `binary_predict_class_allowlist`: `null`
- `inference_lores_wh`: **[704, 576]**
- `binary_imgsz`: **704** (OV IR после `export_trapper_to_openvino.py --imgsz 704`)

## Деплой

1. Переэкспорт OV: `python3 scripts/export_trapper_to_openvino.py --skip-download --imgsz 704 --precision fp16`
2. VPS: `trapper_ai_v02_2024.pt` + `trapper_ai_v02_2024_openvino_model/` (metadata `imgsz: 704`)
3. `user_config.yaml` — см. `app/app_config/user_config.trapper-production.example.yaml`
4. Go2RTC detect substream: **704×576**; `make deploy`

## Артефакты сравнения

- Bbox: `docs/reports/showdown_viz/trapper/{065638,151021}/`
- Метрики: `docs/reports/showdown_quick_trapper.json`
