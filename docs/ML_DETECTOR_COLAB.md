# Training the detector (YOLO) in Google Colab

[Русский](./ML_DETECTOR_COLAB.ru.md)

Classifier-focused Colab walkthrough: [TRAINING](./TRAINING.md).  
This page is the **detection** counterpart: train a **binary** or **3-class** (`Bird` / `Rodent` / `Background`) detector from a `dataset.yaml` produced under [DATASETS](./DATASETS.md).

---

## Prerequisites

- Google account, ~3-4 GB Drive space for zips + runs  
- Two zipped detector datasets (balanced + full), published at  
  [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)  
- Runtime: **GPU** (T4)

---

## Part 1 — Dataset source (Hugging Face)

Use these files from the dataset repo (upload both to Drive):

- `detector_merged_balanced_20260429.zip` (Stage A, stability)
- `detector_merged_full_20260429.zip` (Stage B, diversity fine-tune)

---

## Part 2 — Colab notebook (Stage A -> Stage B)

1. New notebook → **Runtime → Change runtime type → T4 GPU**  
2. Install Ultralytics + YAML parser:

```python
!pip install -q ultralytics pyyaml
```

3. Mount Drive:

```python
from google.colab import drive
drive.mount('/content/drive')
```

4. Paths (edit folder names):

```python
import os
import shutil
import yaml
DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
ZIP_BALANCED = "detector_merged_balanced_20260429.zip"
ZIP_FULL = "detector_merged_full_20260429.zip"
```

5. Stage A unzip (balanced):

```python
EXTRACT_A = "/content/data_stage_a"
if os.path.exists(EXTRACT_A):
    shutil.rmtree(EXTRACT_A)
os.makedirs(EXTRACT_A, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_BALANCED}" -d "{EXTRACT_A}"
```

6. Fix `dataset.yaml` path for Colab runtime  
(archive has an absolute local path from export machine):

```python
DATA_YAML_A = "/content/data_stage_a/binary/merged_balanced/dataset.yaml"
assert os.path.isfile(DATA_YAML_A), DATA_YAML_A
with open(DATA_YAML_A, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = "/content/data_stage_a/binary/merged_balanced"
with open(DATA_YAML_A, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print(cfg)
```

7. Stage A train (balanced):

```python
from ultralytics import YOLO
model_a = YOLO("yolo11n.pt")  # or yolo11s.pt — heavier
model_a.train(
    data=DATA_YAML_A,
    epochs=80,
    imgsz=960,
    batch=16,
    patience=20,
    project=f"{DRIVE_ROOT}/yolo_detector_runs",
    name="stage_a_balanced",
)
```

8. Stage A best checkpoint:

```python
BEST_A = f"{DRIVE_ROOT}/yolo_detector_runs/stage_a_balanced/weights/best.pt"
print(BEST_A)
```

9. Stage B unzip (full):

```python
EXTRACT_B = "/content/data_stage_b"
if os.path.exists(EXTRACT_B):
    shutil.rmtree(EXTRACT_B)
os.makedirs(EXTRACT_B, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_FULL}" -d "{EXTRACT_B}"
```

10. Fix Stage B `dataset.yaml` path:

```python
DATA_YAML_B = "/content/data_stage_b/binary/merged/dataset.yaml"
assert os.path.isfile(DATA_YAML_B), DATA_YAML_B
with open(DATA_YAML_B, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["path"] = "/content/data_stage_b/binary/merged"
with open(DATA_YAML_B, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
print(cfg)
```

11. Stage B fine-tune (full):

```python
model_b = YOLO(BEST_A)
model_b.train(
    data=DATA_YAML_B,
    epochs=40,
    imgsz=960,
    batch=16,
    lr0=0.003,
    patience=15,
    project=f"{DRIVE_ROOT}/yolo_detector_runs",
    name="stage_b_full_ft",
)
```

12. Stage B best checkpoint:

```python
BEST_B = f"{DRIVE_ROOT}/yolo_detector_runs/stage_b_full_ft/weights/best.pt"
print(BEST_B)
```

13. Optional OpenVINO for Hub (`processor.inference_backend: openvino`):

```python
export_model = YOLO(BEST_B)
export_model.export(format="openvino")
```

Download `BEST_B` (and OpenVINO folder if needed) to your Hub host and set paths in config or **Processor weights** UI.

---

## Contract reminder

- Class names in `dataset.yaml` must match Hub normalization: **Bird**, **Rodent**, **Background** for 3-class (same rules as `normalize_detector_label` in `app/processor/src/detector_labels.py`).  
- `processor.detector_scope` must **not** include `Background` ([CV_ML_PREP](./CV_ML_PREP.md)).  
- Before strict rollout: `processor.detector_weight_contract: enforce` only when `model.names` match expectations ([CONFIGURATION](./CONFIGURATION.md)).

---

## Validate before production

```bash
make validate-weights BINARY=/path/to/best.pt ...
```

Use `scripts/benchmark-track-regen.py` on regression clips ([TRAINING](./TRAINING.md)).
