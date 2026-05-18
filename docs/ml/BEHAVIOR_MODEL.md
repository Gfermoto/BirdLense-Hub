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

**Наблюдения:** meta_v1 (logistic) vs video_v1 (RGB-логистика на синтетике) часто расходятся на реальных треках — ожидаемо до переобучения на Hub+WetlandBirds. Решения в проде остаются за **meta_v1**; shadow пишется в `behavior_shadow_*`.

**Патч конфига на сервере:**

```bash
bash scripts/server-apply-user-config-patch.sh scripts/user-config-behavior-canary.partial.yaml --write --restart
```

**Логи расхождений:** `behavior canary discrepancy` в `docker logs birdlense` при finalize; в БД — сравнение `behavior_label` vs `behavior_shadow_label`.
