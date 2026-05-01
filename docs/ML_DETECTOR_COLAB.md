# Training the detector (YOLO) in Google Colab

[Русский](./ML_DETECTOR_COLAB.ru.md)

Classifier walkthrough: [TRAINING](./TRAINING.md). This page is **detection** only (`dataset.yaml`). **`brg/`** paths, merges, zip packaging — [DATASETS.md](./DATASETS.md).

---

## Contents

| Part | What |
|------|------|
| **A** | Main path: **`brg` zip + `bl_best.pt`**, two-stage train (`freeze` → full), OpenVINO **640** — **end-to-end including Hub handoff** |
| **B** | Optional legacy **binary** HF pipeline (balanced → full, **`yolo11n.pt`**, **960**) |
| **C** | Class contract, pre-production checks |

---

# Part A — Main path (`brg` + `bl_best.pt`)

## A0. Before you open Colab (local + Drive)

1. **Build the dataset zip** (if not already on Drive):

   ```bash
   cd /path/to/BirdLense
   python3 scripts/datasets/pack_brg_for_gdrive.py
   ```

   Output: **`datasets/BirdLense_detector_brg_<UTC>.zip`** (`datasets/` is gitignored).

2. **Checkpoint for fine-tuning:** copy your Hub **YOLO11n** detector **`best.pt`** and upload to Drive as **`bl_best.pt`** so it is not confused with new runs.

3. **Upload to Google Drive** into one folder (recommended):

   `My Drive → BirdLense_Detector`

   Minimum files:

   - `BirdLense_detector_brg_<your_UTC>.zip`
   - `bl_best.pt`

4. Leave enough Drive space for Ultralytics runs (often multi‑GB). **`project=RUNS`** below writes under **`.../BirdLense_Detector/yolo_detector_runs/`**.

---

## A1. Where and how to run Colab

1. Open **[Google Colab](https://colab.research.google.com/)**.
2. **File → New notebook** (or upload a `.ipynb`).
3. Enable GPU: **Runtime → Change runtime type → T4 GPU** (or better) → **Save**.
4. Use **one code cell after another**. For each cell: **Shift+Enter** or the **▶ Run** button on the left. **Run cells top to bottom** (otherwise `os`, `DRIVE_ROOT`, `DATA_YAML` will be missing).

After **`drive.mount`**, complete the browser OAuth for Drive access.

---

## A2. Notebook cells (copy in order)

### Cell 1 — dependencies

**Run:** once per session.

```python
!pip install -q ultralytics pyyaml
```

### Cell 2 — mount Google Drive

**Run:** once; approve access in the browser.

```python
from google.colab import drive
drive.mount("/content/drive")
```

### Cell 3 — paths and file checks

**Run:** set **`ZIP_NAME`** to your Drive zip filename.

```python
import os

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
ZIP_NAME = "BirdLense_detector_brg_20260430_134305Z.zip"  # <-- yours
ZIP_PATH = os.path.join(DRIVE_ROOT, ZIP_NAME)
WEIGHTS = os.path.join(DRIVE_ROOT, "bl_best.pt")

assert os.path.isfile(ZIP_PATH), f"Missing zip: {ZIP_PATH}"
assert os.path.isfile(WEIGHTS), f"Missing weights: {WEIGHTS}"
print("OK:", ZIP_PATH, WEIGHTS)
```

### Cell 4 — unzip dataset

```python
import shutil

EXTRACT = "/content/brg_dataset"
if os.path.exists(EXTRACT):
    shutil.rmtree(EXTRACT)
os.makedirs(EXTRACT, exist_ok=True)

!unzip -q "{ZIP_PATH}" -d "{EXTRACT}"
```

Expect **`/content/brg_dataset/brg/dataset.yaml`**. If your layout differs, set **`DATA_YAML`** manually in the next cell.

### Cell 5 — fix `path` in `dataset.yaml` for Colab

```python
import yaml

DATA_YAML = "/content/brg_dataset/brg/dataset.yaml"
assert os.path.isfile(DATA_YAML), DATA_YAML

with open(DATA_YAML, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

cfg["path"] = "/content/brg_dataset/brg"

with open(DATA_YAML, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

print(cfg)
```

Confirm **`names`**: Bird, Rodent, Background.

### Cell 6 — stage 1: frozen backbone (`freeze=10`)

**Run:** long (tens of minutes+). If the session disconnects, remount Drive and continue from the next cell if the run folder already exists.

```python
from ultralytics import YOLO

RUNS = os.path.join(DRIVE_ROOT, "yolo_detector_runs")
os.makedirs(RUNS, exist_ok=True)

model = YOLO(WEIGHTS)
model.train(
    data=DATA_YAML,
    epochs=40,
    imgsz=640,
    batch=16,
    freeze=10,
    patience=20,
    cache="disk",
    project=RUNS,
    name="brg_ft_stage1_freeze10",
)
```

If VRAM is tight, lower **`batch`** (e.g. **8**). Tune **`freeze`** (**5**–**10**) if needed.

### Cell 7 — stage 2: full net, lower `lr0`

```python
STAGE1_BEST = os.path.join(RUNS, "brg_ft_stage1_freeze10", "weights", "best.pt")
assert os.path.isfile(STAGE1_BEST), STAGE1_BEST

model2 = YOLO(STAGE1_BEST)
model2.train(
    data=DATA_YAML,
    epochs=60,
    imgsz=640,
    batch=16,
    lr0=0.001,
    patience=25,
    cache="disk",
    project=RUNS,
    name="brg_ft_stage2_full",
)
```

Do **not** pass **`freeze`** here — all layers train by default.

### Cell 8 — final `best.pt` + OpenVINO **640×640**

```python
BEST_FINAL = os.path.join(RUNS, "brg_ft_stage2_full", "weights", "best.pt")
assert os.path.isfile(BEST_FINAL), BEST_FINAL
print("YOLO best:", BEST_FINAL)

export_model = YOLO(BEST_FINAL)
export_model.export(format="openvino", imgsz=640)
```

OpenVINO output appears **next to** the weights run (Ultralytics prints the folder — often a **`*_openvino`** subfolder). You need **`.xml`**, **`.bin`**, **`metadata.yaml`**.

### A3. After Colab — deploy to Hub

1. On **Drive**: **`BirdLense_Detector/yolo_detector_runs/brg_ft_stage2_full/weights/best.pt`** — download as the new detector.
2. Copy the **OpenVINO** folder from that run; set **`processor.binary_imgsz: 640`** and processor paths ([CONFIGURATION](./CONFIGURATION.md)).

### Shortcut (single run instead of cells 6–7)

One long train from **`bl_best.pt`**:

```python
model = YOLO(WEIGHTS)
model.train(
    data=DATA_YAML,
    epochs=80,
    imgsz=640,
    batch=16,
    freeze=10,
    patience=30,
    cache="disk",
    project=RUNS,
    name="brg_ft_single_freeze10",
)
```

Then in the export cell use **`.../brg_ft_single_freeze10/weights/best.pt`**.

---

# Part B — Optional: HF binary balanced → full

Separate flow for **`detector_merged_balanced_*.zip`** + **`detector_merged_full_*.zip`** from [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main). Uses **`imgsz=960`** and **`YOLO("yolo11n.pt")`** (Ultralytics download). Do **not** mix casually with Part **A** paths / input size.

**Where to run:** same Colab rules (GPU → cells in order).

### B1. Drive prep

Upload both zips to **`MyDrive/BirdLense_Detector/`** and note filenames.

### B2. Cells

**Cell B-a — deps + Drive** (same as Part A: `pip`, `drive.mount`).

**Cell B-b — constants**

```python
import os
import shutil
import yaml

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
ZIP_BALANCED = "detector_merged_balanced_20260429.zip"  # your filename
ZIP_FULL = "detector_merged_full_20260429.zip"
```

**Cell B-c — Stage A unzip balanced**

```python
EXTRACT_A = "/content/data_stage_a"
if os.path.exists(EXTRACT_A):
    shutil.rmtree(EXTRACT_A)
os.makedirs(EXTRACT_A, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_BALANCED}" -d "{EXTRACT_A}"
```

**Cell B-d — Stage A `dataset.yaml`**

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

**Cell B-e — Stage A train**

```python
from ultralytics import YOLO

model_a = YOLO("yolo11n.pt")
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

**Cell B-f — Stage A best path**

```python
BEST_A = f"{DRIVE_ROOT}/yolo_detector_runs/stage_a_balanced/weights/best.pt"
print(BEST_A)
```

**Cell B-g — Stage B unzip full**

```python
EXTRACT_B = "/content/data_stage_b"
if os.path.exists(EXTRACT_B):
    shutil.rmtree(EXTRACT_B)
os.makedirs(EXTRACT_B, exist_ok=True)
!unzip -q "{DRIVE_ROOT}/{ZIP_FULL}" -d "{EXTRACT_B}"
```

**Cell B-h — Stage B `dataset.yaml`**

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

**Cell B-i — Stage B fine-tune**

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

**Cell B-j — OpenVINO (must match training `imgsz`)**

```python
BEST_B = f"{DRIVE_ROOT}/yolo_detector_runs/stage_b_full_ft/weights/best.pt"
export_model = YOLO(BEST_B)
export_model.export(format="openvino", imgsz=960)
```

Hub **`processor.binary_imgsz`** must be **960** for this export.

Published **`weights-*-001.zip`** from HF can be deployed without this pipeline — [CONFIGURATION](./CONFIGURATION.md).

---

# Part C — Contract and validation

- Class names in `dataset.yaml` must match Hub normalization: **Bird**, **Rodent**, **Background** for 3-class (`normalize_detector_label` in `app/processor/src/detector_labels.py`).  
- `processor.detector_scope` must **not** include `Background` ([CV_ML_PREP](./CV_ML_PREP.md)).  
- Before strict rollout: `processor.detector_weight_contract: enforce` only when `model.names` match expectations ([CONFIGURATION](./CONFIGURATION.md)).

```bash
make validate-weights BINARY=/path/to/best.pt ...
```

Regression clips: `scripts/benchmark-track-regen.py` ([TRAINING](./TRAINING.md)).
