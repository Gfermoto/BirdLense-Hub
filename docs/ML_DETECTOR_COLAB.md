# Training the detector (YOLO) in Google Colab

[Русский](./ML_DETECTOR_COLAB.ru.md)

Classifier walkthrough: [TRAINING](./TRAINING.md). This page is **detection** only (`dataset.yaml`). **`brg/`** paths, merges, zip packaging — [DATASETS.md](./DATASETS.md).

**Default (recommended):** fine-tune from the **latest production Hub weights** — the same **`best.pt`** you ship today (YOLO11n **detect**, **Bird / Rodent / Background**). On Drive upload it as **`bl_best.pt`** so it stays separate from **`best.pt`** produced by Ultralytics runs.

**Do not use as the Part A starting point:** COCO-pretrained **`yolo11n.pt`** (80 classes) — Hub contract breaks. Cold start without a checkpoint: see **A1.c** at the end of Part **A**.

---

## Contents

| Part | What |
|------|------|
| **A** | Main path: **`brg` zip + production `best.pt` on Drive as `bl_best.pt`**, two-stage train (`freeze` → full), OpenVINO **640** — through Hub deploy |
| **B** | Optional legacy **binary** HF pipeline (balanced → full, **`yolo11n.pt`**, **960**) |
| **C** | Class contract, pre-production checks |

---

# Part A — Main path (`brg` + production weights)

## A0. Before you open Colab (local + Drive)

1. **Build the dataset zip** (if not already on Drive):

   ```bash
   cd /path/to/BirdLense
   python3 scripts/datasets/pack_brg_for_gdrive.py
   ```

   Output: **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`** (same directory as `binary/` and `yolo/`).

2. **Starting checkpoint (default = best Hub weights):** use the **`best.pt`** that **actually powers** binary detection on the Hub (or the same artefact from your processor tree, e.g. **`app/processor/models/detection/weights/best.pt`**, if that is what you deploy).

   Upload it to Drive as **`bl_best.pt`** (`BASE_WEIGHTS`) so you do not confuse it with **`best.pt`** from a new run.

   Pre-flight checks:

   | Expectation | Why |
   |---------------|-----|
   | **`detect`**, **YOLO11n** compatible with your prod export chain | avoids load/export mismatches |
   | **3** classes, order **Bird → Rodent → Background** aligned with `dataset.yaml` | matches [Part C](#part-c--class-contract--checks) and Hub config |

3. **Upload to Google Drive** into one folder (recommended):

   `My Drive → BirdLense_Detector`

   Minimum files:

   - `BirdLense_detector_brg_<your_UTC>.zip`
   - `bl_best.pt` (**required for the default path**)

4. Leave enough Drive space for Ultralytics runs (**multi‑GB**). **`project=RUNS`** below writes under **`.../BirdLense_Detector/yolo_detector_runs/`**.

---

## A1. Where and how to run Colab

1. Open **[Google Colab](https://colab.research.google.com/)**.
2. **File → New notebook** (or upload a `.ipynb`).
3. Enable GPU: **Runtime → Change runtime type → T4 GPU** (or better) → **Save**.
4. Use **one code cell after another**. **Run cells top to bottom**.

After **`drive.mount`**, complete the browser OAuth for Drive access.

### A1.b — Disconnects and `resume`

If the session drops **after** stage 1 or 2 starts, avoid re-running **`model.train(...)`** with the **same `name`** for a duplicate run — use **`resume=True`** from **`last.pt`**, **or** change **`name`** for a fresh run.

```python
from ultralytics import YOLO

LAST = "/content/drive/MyDrive/BirdLense_Detector/yolo_detector_runs/brg_ft_stage1_freeze10/weights/last.pt"
YOLO(LAST).train(resume=True)  # only `resume=True` — Ultralytics requirement
```

Use the analogous **`last.pt`** path if stage 2 was interrupted.

---

## A1.c — No production `best.pt` (rare cold start for Part A)

Only when **no** three-class Hub checkpoint exists. **`YOLO("yolo11n.pt")`** can build a three-class head from your **`dataset.yaml`**, but convergence is weaker than warm-starting from a trained BRG detector. Still use **`imgsz=640`**, two stages, and the Part **C** class contract. Prefer **`pip install ultralytics>=8.3.203`** for reproducible **`resume`** (see [TRAINING](./TRAINING.md)).

---

## A2. Notebook cells (copy in order)

### Cell 1 — dependencies

**Run:** once per session.

```python
# Stable resume: ultralytics>=8.3.203 (see TRAINING.md)
!pip install -q "ultralytics>=8.3.203" pyyaml
```

### Cell 2 — mount Google Drive

**Run:** once; approve access in the browser.

```python
from google.colab import drive
drive.mount("/content/drive")
```

### Cell 3 — paths and file checks

**Important:** the filename **`BirdLense_detector_brg_20260430_134305Z.zip`** was only a **placeholder** in older docs — it will not exist on your Drive until you upload your own zip.

- Either set the **exact** zip name you uploaded, **or**
- Use **auto-detect** below: newest **`BirdLense_detector_brg_*.zip`** by modification time under **`DRIVE_ROOT`**.

**`BASE_WEIGHTS`** = Hub **`best.pt`** uploaded as **`bl_best.pt`**.

```python
import os
from pathlib import Path

DRIVE_ROOT = "/content/drive/MyDrive/BirdLense_Detector"
assert os.path.isdir(DRIVE_ROOT), f"Missing folder (check path + Drive mounted): {DRIVE_ROOT}"

# --- Option A (recommended): newest BRG zip in folder ---
cands = list(Path(DRIVE_ROOT).glob("BirdLense_detector_brg_*.zip"))
if not cands:
    raise FileNotFoundError(
        f"No BirdLense_detector_brg_*.zip in {DRIVE_ROOT}. "
        "Upload the zip from pack_brg_for_gdrive.py or set ZIP_PATH manually (option B)."
    )
ZIP_PATH = str(max(cands, key=lambda p: p.stat().st_mtime))
print("ZIP (auto):", ZIP_PATH)

# --- Option B: uncomment and set exact Drive filename ---
# ZIP_PATH = os.path.join(DRIVE_ROOT, "BirdLense_detector_brg_20260505_120000Z.zip")

BASE_WEIGHTS = os.path.join(DRIVE_ROOT, "bl_best.pt")
WEIGHTS = BASE_WEIGHTS

assert os.path.isfile(ZIP_PATH), f"Missing zip: {ZIP_PATH}"
assert os.path.isfile(BASE_WEIGHTS), f"Missing base weights: {BASE_WEIGHTS}"
print("OK:", ZIP_PATH, BASE_WEIGHTS)
```

If **`BirdLense_Detector`** is wrong, fix **`DRIVE_ROOT`** (Shared drives / different folder name).

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

names = cfg.get("names") or {}
keys = sorted(names, key=lambda k: int(k))
ordered = [names[k] for k in keys]
assert ordered == ["Bird", "Rodent", "Background"], ordered
```

If this assert fails, fix **`dataset.yaml`**, rebuild the zip, unzip again — do **not** train yet.

### Cell 6 — stage 1: frozen backbone (`freeze=10`)

**Run:** **`YOLO(WEIGHTS)` loads `BASE_WEIGHTS`** (production checkpoint).

After a disconnect — see **A1.b** above (**`resume=True`** from **`last.pt`**); do not re-invoke **`model.train`** with the same **`name`** if you intend to continue the **same** run.

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

Ultralytics 8.x prints the **exact** IR folder in the export log — often **`.../weights/best_openvino_model/`** next to **`best.pt`** (**`best.xml`**, **`best.bin`**, **`metadata.yaml`**). **`metadata.yaml`** should list **3** classes aligned with training.

### A3. After Colab — deploy to Hub

1. **`.../brg_ft_stage2_full/weights/best.pt`** on Drive — new torch detector for Hub / your next **`bl_best.pt`** baseline.
2. Copy the exported OpenVINO directory (often **`best_openvino_model`**) intact — typical Hub/processor layout **`models/detection/weights/best_openvino_model`** under the processor package; **`processor.binary_imgsz: 640`** ([CONFIGURATION](./CONFIGURATION.md)).

### Shortcut (single run instead of cells 6–7)

One long train starting from **`BASE_WEIGHTS`** (**`WEIGHTS`** / **`bl_best.pt`**):

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
