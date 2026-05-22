# Fully Autonomous Trapper Deploy Report

**Статус: СИСТЕМА ГОТОВА К РАБОТЕ**

Дата: 2026-05-22T10:26:00+00:00  
Модель: **TrapperAI v02.2024** (OpenVINO FP16, вход **704×704**)  
Прод-хост: http://185.218.111.196:8085/ (`185.218.111.196:2222`, `/root/BirdLense`)

## Подтверждения

| Проверка | Результат |
|----------|-----------|
| Локальный IR `metadata.yaml` imgsz **704** | OK |
| SHA256 `best.bin` + `metadata.yaml` + `.pt` local == VPS | OK (совпадение полное) |
| Smoke dummy (OpenVINO, imgsz 704) | OK |
| Smoke GPU на VPS (`intel:gpu`, GPU.0) | OK |
| Video smoke (`2026/05/19/151021`, кадр 50) | OK — 1 детекция Bird conf **0.6494** |
| `patch_prod_trapper_user_config.py` → активный `user_config.yaml` | OK (без ручного rename) |
| Исправлен конфликт `binary_imgsz` night profile 640→704 | OK |
| `docker compose` birdlense | **healthy** |
| `verify-stack` (health + readiness + processor heartbeat) | **PASS** |
| Processor: `TwoStageStrategy` openvino + trapper paths | OK в логах |
| OpenVINO mismatch crash loop | устранён |

## Конфиг (применён автоматически на VPS)

- `processor.models.binary` / `binary_openvino`: `trapper_ai_v02_2024.pt` / `trapper_ai_v02_2024_openvino_model`
- `processor.inference_backend`: `openvino`
- `processor.inference_device`: `intel:gpu`
- `processor.binary_imgsz`: **704** (включая `adaptive_profiles.night.overrides`)
- `processor.inference_lores_wh`: `[704, 576]`
- `processor.detector_scope`: `["Bird", "Eurasian Red Squirrel"]`
- `processor.binary_predict_class_allowlist`: `[0, 5]`
- `processor.min_confidence_binary` / bird / openvino: **0.25**
- `processor.shadow_ensemble_enabled`: `false`

## Метрики (ожидание по showdown / quick bench)

| Параметр | Значение |
|----------|----------|
| Substream detect | 704×576, без даунскейла в 640² |
| IR letterbox | 704×704 |
| OpenVINO iGPU infer | ~7–10 FPS (оценка quick) |
| Стартовый conf | 0.25 (video smoke: Bird @0.65 на тестовом кадре) |

## Артефакты и автоматизация

- Веса: `app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/`
- Скрипты: `scripts/sync_trapper_weights.sh`, `scripts/trapper_ov_smoke_test.py`, `scripts/patch_prod_trapper_user_config.py`, `scripts/fully_autonomous_trapper_deploy.sh`
- Лог последнего прогона: `docs/reports/fully_autonomous_deploy.log`

## SHA256 (справочно)

```
best.bin:     29e52009c548b809b2a9cc4eb934241f8ed85c7da8a005042828b0152d946529
metadata.yaml: 156b13f3fad667f3f0d725f6329679f33d830980c001959a98ac537a0fd69778
trapper.pt:   3197239e7f2cd28773f99d29785a71a5682b88f4cac2487df81b75615d4d3109
```

Повторный полный цикл: `bash scripts/fully_autonomous_trapper_deploy.sh`
