# Behavior v2 — video model

## Артефакты

| Путь | Назначение |
|------|------------|
| `app/processor/models/behavior_v1_openvino/behavior_video_model.xml` | OpenVINO IR (FP16) |
| `app/processor/models/behavior_v1_openvino/behavior_video_model.bin` | Веса IR |
| `app/processor/models/behavior_v1_openvino/behavior_video_export.json` | Метки + coef/intercept (`behavior_video_export@v1`) |
| `data/datasets/behavior_crops/` | Кропы треклетов (jpg + `mean_rgb.npy`) |

## Переобучение (host)

```bash
pip install -r scripts/requirements-ml-behavior.txt

# Синтетика / CI (если нет WetlandBirds):
python3 scripts/ml_behavior_bootstrap_synthetic.py \
  --out-root app/data/datasets/behavior_v2_synthetic

# Или Hub DB + WetlandBirds:
# make ml-extract-behavior-tracklets DB=... OUT=... CROPS_DIR=data/datasets/behavior_crops EXTRACT_CROPS=1
# make ml-import-wetlandbirds ANNOTATIONS_ROOT=... OUT=... CROPS_DIR=data/datasets/behavior_crops

MANIFEST=app/data/datasets/behavior_v2_synthetic/behavior_tracklet_merged.json \
OUT_DIR=app/data/datasets/behavior_v2_artifacts \
make ml-train-behavior-video

VIDEO_EXPORT=app/data/datasets/behavior_v2_artifacts/behavior_video_export@*.json \
OUT_DIR=app/processor/models/behavior_v1_openvino \
make ml-export-behavior-video-openvino
```

Holdout Macro-F1 ≥ 0.7 — gate в `behavior_train_report@v2` (`ok: true`).

## Runtime

`processor.behavior_recognition`:

- `engine: meta` — только meta_v1 (по умолчанию)
- `engine: canary` — решения meta_v1, video_v1 в shadow + лог расхождений
- `engine: video` / `auto` — переключение на video при достаточной уверенности

`video_openvino_path`, `video_weights_path` — каталог IR и JSON export.

## Метрики

- Holdout: `scripts/ml_behavior_eval_harness.py` (train/holdout 80/20 по `tracklet_id`)
- Canary offline: `make ml-behavior-canary-gate` (поддержка `behavior_train_report@v2`)

## Production Canary Status

**Дата:** 2026-05-18 (VPS `185.218.111.196:8085`)

| Параметр | Значение |
|----------|----------|
| Деплой | `make deploy` + патч `scripts/user-config-behavior-canary.partial.yaml` |
| `engine` | `canary` (`enabled: true`) |
| IR на сервере | `/app/processor/models/behavior_v1_openvino/behavior_video_model.xml` |
| verify-stack | PASS (health + readiness GREEN) |
| OpenVINO infer (warm, GPU.0) | ~1–3 ms / forward (192-d input) |
| Backfill 12 клипов (≥3 кадра/трек) | 12× `video_v1`, расхождения **7/12 (58%)**, согласие **5/12** |

**Наблюдения (v1, синтетика):** meta_v1 vs video_v1 — ~58% расхождений на 12 клипах (rule-fallback / неверная таксономия).

### Retrain v2 (prod crops, 2026-05-18)

| Метрика | Значение |
|---------|----------|
| Датасет | 44 tracklet (Hub: approved AL + conf≥0.85), feeding=40, flying=4 |
| Holdout Macro-F1 | 0.44 (мало flying в выборке) |
| Canary replay (13 клипов с треками) | **30.8%** discrepancy (было 58%) |
| Типичная ошибка | meta `flying` → video `feeding` |
| IR | `app/processor/models/behavior_v2_openvino/` |
| Конфиг | `video_model_kind: video_v2`, `engine: canary` |

**Сбор prod-кропов на VPS:**

```bash
docker exec birdlense bash -lc 'cd /app && PYTHONPATH=/app/scripts:/app \
  python3 scripts/ml_behavior_extract_prod_labeled.py \
  --db /app/data/db/birdlense.db \
  --out /app/data/datasets/behavior_prod_v2/manifest.json \
  --crops-dir /app/data/datasets/behavior_prod_v2/crops \
  --repo-root /app --min-confidence 0.85 --min-blur-score 4'
```

**Обучение + OpenVINO + патч:**

```bash
python3 scripts/ml_behavior_train_video.py --manifest ... --augment-copies 4
python3 scripts/ml_behavior_export_video_openvino.py --video-export ... --out-dir app/processor/models/behavior_v2_openvino
bash scripts/server-apply-user-config-patch.sh scripts/user-config-behavior-canary-v2.partial.yaml --write --restart
```

**Переход в `engine: auto`:** только после ≥48 ч Canary с discrepancy **<20%** на ≥30 клипах и без роста blind-gate. Откат auto → `engine: canary` при discrepancy **>25%** за 24 ч.

### v2.1 Production Release (2026-05-19)

| Параметр | Значение |
|----------|----------|
| Датасет | Hub relaxed (46) + **Visual WetlandBirds** (1469) → merged **1515** tracklets, **flying=100** |
| Holdout Macro-F1 | **0.37** (8 классов; flying holdout **9/9** correct) |
| Canary replay (23 видео с треками) | discrepancy **39.1%**; video `flying` **6** клипов (v2: ~31% на 13 клипах, flying почти не предсказывался) |
| IR | `app/processor/models/behavior_v2_1_openvino/` |
| Конфиг | `video_model_kind: video_v2_1`, **`engine: auto`** (VPS 2026-05-19) |
| Патч | `scripts/user-config-behavior-auto-v2_1.partial.yaml` |

**WetlandBirds:** Zenodo [10.5281/zenodo.15696105](https://doi.org/10.5281/zenodo.15696105) — `scripts/download_wetlandbirds_zenodo.sh`, `scripts/convert_wetlandbirds_zenodo_crops.py`. Отчёт: `docs/reports/wetlandbirds_integration_report.md`.

**Откат:** `scripts/user-config-behavior-canary-v2_1.partial.yaml` + restart.

**Регулярное переобучение:** еженедельно `ml-extract-behavior-prod-labeled` + train + export v2; не использовать синтетику в финальном blend.

**Патч конфига на сервере:**

```bash
bash scripts/server-apply-user-config-patch.sh scripts/user-config-behavior-canary.partial.yaml --write --restart
```

**Логи расхождений:** `behavior canary discrepancy` в `docker logs birdlense` при finalize; в БД — сравнение `behavior_label` vs `behavior_shadow_label`.
