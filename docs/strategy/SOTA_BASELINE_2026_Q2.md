# SOTA Baseline v1.0 Stable — 2026 Q2

**Статус:** утверждённый базовый уровень после Wave 1 (кризис) и Wave 2 (стабилизация).  
**Дата фиксации:** 2026-05-20  
**Ветка:** `dev` → прод VPS `http://185.218.111.196:8085`  
**Связанные отчёты:** [`sota_quality_leap_report.md`](../reports/sota_quality_leap_report.md), [`nabirds_final_validation.md`](../reports/nabirds_final_validation.md), [`fine_tuning_contrastive_analysis.md`](../reports/fine_tuning_contrastive_analysis.md)

---

## 1. Резюме для руководства

Система переведена из режима «выживание» в режим **операционной стабильности**:

- Ложные срабатывания на статике кормушки снижены с **сотен–тысяч принятых боксов/сессию** до **единиц–десятков** (≈17× по `yolo_accepted`, плюс слой NVR-фильтров).
- Репозиторий и артефакты: одна активная behavior-модель (`video_v1`), переносимые пути `/app/`, deprecations v2/v2_1.
- Прод: OpenVINO NABirds на Intel GPU, health/deploy gates зелёные.

**От этой точки** начинается Wave 3 — планомерное превосходство (active learning, ReID, UX), а не починка регрессий.

---

## 2. Метрики Baseline v1.0 (точка отсчёта)

> Метрики зафиксированы на реальных роликах и `session_runtime_metrics` VPS; не являются COCO mAP — это **операционная чистота** BirdLense Hub.

### 2.1 Прод-сессии (2026-05-20, после хотфика 0.28)

| Показатель | До (эра < 08:35 UTC) | После (≥ 08:35 UTC) | Комментарий |
|------------|----------------------|---------------------|-------------|
| Сессий в выборке | 11 | 3 | окно UTC |
| avg `yolo_raw_boxes` | 832 | 393 | до per-label accept |
| avg **`yolo_accepted`** | **832** | **50** | **~17× снижение шума** |
| max raw / сессию | 1113 | 524 | |
| Negative static clip @0.28 | — | **0 боксов** | `082357` кадр 10, OV GPU |
| Пример сессии | raw≈accepted | raw=524, **accepted=9** | id 1453 |

### 2.2 Офлайн-валидация DetectionQualityPipeline (@ min_conf 0.28)

| Ролик | accepted до | accepted после | Bird proxy retained |
|-------|-------------|----------------|---------------------|
| `094147` (корм FP) | 25 | **7** | **7/7** (100%) |
| `093950` (гигант FP) | 5 | **0** | — |
| `050815` (птица) | 37 | **37** | **36/36** (100%) |

### 2.3 Целевые SLO (Wave 3 измеряет улучшение от baseline)

| SLO | Baseline v1.0 | Wave 3 target (ориентир) |
|-----|---------------|---------------------------|
| FP rate (пустая кормушка, accepted/мин) | единицы | < 0.1 |
| Bird recall (якорные ролики) | ~100% @0.28 | ≥ 98% при INT8 |
| Inference latency (binary, GPU) | prod nominal | −20% INT8 |
| Config drift (repo vs prod) | синхронизировано | CI gate |
| Artifact path portability | `/app/` | 100% JSON |

### 2.4 Runtime-метрики качества (новый контракт)

В `last_detect_metrics` / логах процессора:

- `rejected_ignore_mask`, `rejected_interest_zone`
- `rejected_motion_verified`, `rejected_global_static`
- `rejected_texture`, `rejected_static_objects`, `rejected_phantom_boxes`
- `hard_negatives_saved`, `yolo_accepted`

---

## 3. Архитектурный стандарт (утверждённый стек)

```
RTSP / Frigate → recordings → Processor (YOLO binary + species head)
                              ↓
                    DetectionQualityPipeline
                      1. Ignore masks / interest zones
                      2. Motion-verified (global + ROI)
                      3. Texture (Laplacian)
                      4. StaticObjectFilter (geometry + 8s temporal)
                      5. Hard negatives → data/hard_negatives/
                              ↓
                    SQLite visits + Web UI + MCP
```

| Слой | Стандарт v1.0 |
|------|----------------|
| **Binary detector** | `best_NABirds.pt` + `best_NABirds_openvino_model/` |
| **Inference** | `processor.inference_backend: openvino`, `intel:gpu` (VPS) |
| **Scope** | `detector_scope: [Bird]` |
| **Пороги** | `min_confidence_binary_bird: 0.28`, `openvino_binary_bird_score_scale: 1.0` |
| **Трекер** | ByteTrack, IoU fallback live/regen, unstick |
| **Behavior** | `behavior.active_video_model: video_v1` → `behavior_v1_openvino/` |
| **Конфиг** | `default_config.yaml` + `user_config.yaml` (deploy не затирает user) |
| **Надёжность** | track watchdog, predict fallback, processor health |

### Конфиг-якоря (копировать в аудит)

```yaml
processor:
  inference_backend: openvino
  min_confidence_binary_bird: 0.28
  openvino_binary_bird_score_scale: 1.0
  static_object_suppression_enabled: true
  motion_verified_detection_enabled: true
  detection_ignore_masks: []   # user polygons 0–1
behavior:
  active_video_model: video_v1
  video_openvino_path: models/behavior_v1_openvino
```

---

## 4. Извлечённые уроки (анти-паттерны)

| # | Анти-паттерн | Последствие | Правило Wave 3+ |
|---|--------------|-------------|-----------------|
| 1 | BRG `best.pt` + `openvino_binary_bird_score_scale: 8.5` | Массовый FP, завышенный conf | Только NABirds IR; scale **1.0**; parity gate перед продом |
| 2 | Деплой OV без `validate_ov_parity.py` | «Слепой» детектор, Frigate видит — мы нет | Parity <5% на golden clips; CI smoke |
| 3 | `track(conf)=0.12` при `accept=0.28` | `yolo_raw` сотни, путаница в метриках | Документировать raw vs accepted; опционально выровнять conf |
| 4 | Абсолютные пути `/home/gfer/...` в JSON | Битый перенос, цикл падений процессора | `/app/` + `fix_artifact_paths.py` |
| 5 | Несколько behavior v1/v2/v2_1 без `active_*` | Хаос версий | Одна `active_video_model`; остальное DEPRECATED |
| 6 | Порог 0.08–0.12 «для recall» на статике | Тысячи FP в БД | Precision-first; контрастная калибровка на FP-роликах |
| 7 | Имена `max_aspect` / `min_aspect` как диапазон | Неверная интерпретация OR-логики | `vertical_max_aspect` / `horizontal_min_aspect` |
| 8 | Смена весов без snapshot | Невозможен откат | `make snapshot-detector-weights` |

---

## 5. Wave 1 & 2 — закрытие scope

### Wave 1 — Crisis (выполнено)

- [x] Диагностика FP, forensic, contrastive analysis
- [x] Порог 0.28, отказ от BRG scale 8.5
- [x] NABirds + OpenVINO migration, parity gate
- [x] StaticObjectFilter, giant phantom reject

### Wave 2 — Stabilization (выполнено)

- [x] DetectionQualityPipeline (masks, motion, texture, temporal 8s)
- [x] Hard negatives directory
- [x] Artifact path hygiene, single behavior v1
- [x] Dockerfile script contract test
- [x] Deploy + health gates

### Вне baseline (перенос в Wave 3)

- [ ] UI mask editor
- [ ] Weekly hard-negative retrain loop
- [ ] Zone-adaptive thresholds
- [ ] INT8 quantization study

---

## 6. Ссылки

| Документ | Назначение |
|----------|------------|
| [`SOTA_WAVE3_ROADMAP_2026.md`](SOTA_WAVE3_ROADMAP_2026.md) | План превосходства |
| [`../reports/sota_quality_leap_report.md`](../reports/sota_quality_leap_report.md) | Детали quality leap |
| [`../ml/MODEL_EXPORT_GUIDE.md`](../ml/MODEL_EXPORT_GUIDE.md) | OV export / parity |
| [`../../AGENTS.md`](../../AGENTS.md) | Команды CI/deploy для агентов |

---

*Baseline пересматривается только через PR с метриками «до/после» на якорных роликах и фрагменте prod `session_runtime_metrics`.*
