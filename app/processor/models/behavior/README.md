# Behavior baseline weights (`behavior_logistic_export@v1`)

## Bundled starter file

`behavior_logistic_export@v1.json` in this directory is a **small valid export** so the processor can load weights and you can verify `processor.behavior_recognition.weights_path` end-to-end. It is **not** tuned on your cameras; replace it after you train on your data.

## Train on your annotations

1. **Install** (on the machine where you run training): `pip install scikit-learn`
2. **Build a manifest** from a folder of annotation CSVs (see `scripts/ml_behavior_dataset_manifest.py` for column layout):

   ```bash
   cd /path/to/BirdLense
   ANNOTATIONS_ROOT=/path/to/annotations OUT=/tmp/behavior_dataset_manifest.v1.json \
     make ml-build-behavior-dataset
   ```

3. **Train + export** weights + predictions:

   ```bash
   MANIFEST=/tmp/behavior_dataset_manifest.v1.json \
   EXPORT=/tmp/behavior_logistic_export@v1.json \
   PRED=/tmp/behavior_predictions.v1.json \
     make ml-train-behavior-baseline
   ```

4. Copy `EXPORT` JSON onto the hub host under `app/processor/` (e.g. `models/behavior/my_export.json`), set **Settings → Processor → Behavior recognition → Weights path** to that **relative** path (relative to the processor package root, e.g. `models/behavior/my_export.json`), enable the toggle, **save**, restart the processor container.

5. Optional report: `make ml-build-behavior-train-report` (see `Makefile`).

## Hub settings keys

YAML / API mirror: `processor.behavior_recognition.enabled`, `weights_path`, `confidence_store_min`, `confidence_review_threshold`.
