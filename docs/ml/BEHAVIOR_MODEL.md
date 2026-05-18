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
