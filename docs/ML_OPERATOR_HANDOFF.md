# ML roadmap — repository complete vs your work

[Русский](./ML_OPERATOR_HANDOFF.ru.md)

This page closes the **repository-side** ML Phase‑1 track as documented in [CV_ML_ROADMAP_PHASES](./CV_ML_ROADMAP_PHASES.md). Training always happens **outside** the Hub (Colab, local GPU, Runpod, etc.) — that is expected.

---

## What is already finished **in the repo** (branch `ML`)

- Inference stack: torch / OpenVINO binary detector paths, weight contract, benchmarks, CI smoke, docs.
- Dataset **merge** helpers for a **3-class** detector layout (`Bird` / `Rodent` / `Background`): [DATASETS](./DATASETS.md) § three-class.
- Operator docs for decode benchmarks, active-learning manifest stubs, Re-ID / federated **roadmaps** (not product features by themselves).
- Offline **DINOv2 crop embeddings** CLI: [`embed_dinov2_crop.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_dinov2_crop.py), [`embed_cosine_report.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_cosine_report.py), [`export_crops_from_sqlite.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/export_crops_from_sqlite.py), [`README`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/README.md) — outside Docker ([#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383)).

Nothing here replaces **your** labeled images, GPU time, or rollout decisions.

---

## What only **you** can do (by design)

| Step | Where |
|------|--------|
| Curate images / exports from Hub disk | Library export, `scripts/datasets/*`, or manual folders |
| Train YOLO **classifier** | [TRAINING](./TRAINING.md) (Google Colab walkthrough) |
| Train YOLO **detector** (binary or 3-class) | [ML_DETECTOR_COLAB](./ML_DETECTOR_COLAB.md) + Ultralytics outside Hub |
| Validate rollout | `make validate-weights` ([TRAINING](./TRAINING.md) rollout contract) |
| Deploy code | `make deploy` when you switch from `dev` to a validated `ML` / `main` image |

### When new weights land (3-class detector + rodent in classifier)

1. Place detector/classifier `best.pt` under `app/processor/models/…` or point `user_config.yaml` at your paths.
2. Align YOLO class names with `processor.detector_scope` and optionally enable `processor.detector_weight_contract: enforce` ([DATASETS](./DATASETS.md), [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)).
3. Run `make validate-weights`, smoke-test on hub, then `make deploy`.
4. After classifier fine-tune including rodents, refresh allowlist / `class_names.txt` ([TRAINING](./TRAINING.md)).

Detector training artifacts for this flow are published as zips at
[gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)
(`merged_balanced` for Stage A, `merged` full for Stage B fine-tune).

---

## Suggested order when you have accumulated data

1. **Decide target:** refresh **classifier only**, or also a new **detector** (2-class vs 3-class — see [CV_ML_PREP](./CV_ML_PREP.md)).
2. **Classifier path:** export train-ready ZIP from Hub → merge scripts per [DATASETS](./DATASETS.md) → [TRAINING](./TRAINING.md) Colab cells.
3. **Detector path:** build `dataset.yaml` (e.g. `make dataset-merge-three-class` after preparing folders) → zip → [ML_DETECTOR_COLAB](./ML_DETECTOR_COLAB.md).
4. **Rollout:** copy `best.pt` (and OpenVINO export if used), run validation, deploy, benchmark clips if needed.

---

## Related notebooks in repo

- `scripts/birds_train_cls.ipynb` — classification-oriented workflow you can adapt.
- `scripts/birds_train.ipynb` — detection-oriented cells (historically tuned for Runpod-style paths); mirror into Colab using [ML_DETECTOR_COLAB](./ML_DETECTOR_COLAB.md).

---

## Epic link

Parent tracker: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367). Closing the **GitHub epic** is a product decision after your weights and deploy criteria are met — the codebase handoff is **documentation + scripts above**.
