# Training the detector (YOLO) in Google Colab

[Русский](./ML_DETECTOR_COLAB.ru.md)

Classifier-focused Colab walkthrough: [TRAINING](./TRAINING.md).  
This page is the **detection** counterpart: train a **binary** or **3-class** (`Bird` / `Rodent` / `Background`) detector from a `dataset.yaml` produced under [DATASETS](./DATASETS.md).

---

## Prerequisites

- Google account, ~2 GB Drive space for zip + runs  
- A zipped dataset whose root contains **`dataset.yaml`** (e.g. `binary/merged/` after `merge_datasets_three_class`)  
- Runtime: **GPU** (T4)

---

## Part 1 — Zip the dataset locally

From your PC (after `make dataset-merge-three-class` or equivalent):

```bash
cd scripts/datasets   # or parent of binary/merged
zip -r ~/BirdLense_detector_dataset.zip binary/merged/
```

Upload **`BirdLense_detector_dataset.zip`** to Google Drive (e.g. `BirdLense_Training/`).

---

## Part 2 — Colab notebook (minimal)

1. New notebook → **Runtime → Change runtime type → T4 GPU**  
2. Install Ultralytics:

```python
!pip install -q ultralytics
```

3. Mount Drive:

```python
from google.colab import drive
drive.mount('/content/drive')
```

4. Paths (edit folder names):

```python
import os
DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Training"
ZIP_NAME = "BirdLense_detector_dataset.zip"
EXTRACT_DIR = "/content/detector_data"
os.makedirs(EXTRACT_DIR, exist_ok=True)
```

5. Unzip:

```python
!unzip -q "{DRIVE_ROOT}/{ZIP_NAME}" -d "{EXTRACT_DIR}"
```

Find `dataset.yaml` (adjust `DATA_YAML` if nested):

```python
DATA_YAML = "/content/detector_data/binary/merged/dataset.yaml"
assert os.path.isfile(DATA_YAML), DATA_YAML
```

6. Train:

```python
from ultralytics import YOLO
model = YOLO("yolo11n.pt")  # or yolo11s.pt — heavier
model.train(
    data=DATA_YAML,
    epochs=100,
    imgsz=640,
    patience=20,
    project=f"{DRIVE_ROOT}/yolo_detector_runs",
    name="hub_detector_v1",
)
```

7. Best weights path (Ultralytics default):

```python
best_pt = f"{DRIVE_ROOT}/yolo_detector_runs/hub_detector_v1/weights/best.pt"
print(best_pt)
```

8. Optional OpenVINO for Hub (`processor.inference_backend: openvino`):

```python
export_model = YOLO(best_pt)
export_model.export(format="openvino")
```

Download `best.pt` (and OpenVINO folder if needed) to your Hub host and set paths in config or **Processor weights** UI.

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
