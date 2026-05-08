# Training the detector (YOLO) in Google Colab

[Русский](./ML_DETECTOR_COLAB.ru.md)

Classifier walkthrough: [TRAINING](./TRAINING.md). This page is **detection** only (`dataset.yaml`). **`brg/`** paths, merges, zip packaging — [DATASETS.md](./DATASETS.md).

---

## Training plan (checklist)

**Google Drive folder for this playbook:** **`3step_detector`** with:

| File | Role |
|------|------|
| **`BirdLense_detector_brg.zip`** | BRG dataset (YOLO detect). If you keep the UTC name from **`pack_brg_for_gdrive.py`**, rename to this or leave **`BirdLense_detector_brg_*.zip`** — cell 3 resolves it. |
| **`nabirds_yolo11n_binary.zip`** | Starting detector weights; after unzip Colab picks **`best.pt`** (or the only **`*.pt`**) recursively. |

**Steps:** (1) Local merge/pack → upload dataset zip; (2) upload **`nabirds_yolo11n_binary.zip`**; (3) Colab GPU + deps + **`drive.mount`**; (4) Unzip dataset → set absolute **`path`** in **`brg/dataset.yaml`** → assert **`Bird`, `Rodent`, `Background`**; (5) Unzip weights → **`WEIGHTS`** → checkpoint validation cell; (6) Stage 1 **`freeze=10`**; (7) Stage 2 **`lr0=0.001`**; (8) OpenVINO **`imgsz=640`**; (9) **`make validate-weights`** and optional track regression → deploy.

**Risks:** The archive must yield a **`detect`** **`.pt`** with **3** BRG names ([Part C](#part-c-contract-and-validation)). Raw COCO **`yolo11n.pt`** (80 classes) is not a drop-in Hub baseline. **A1.c** only if no three-class checkpoint exists.

**Optional:** place **`bl_best.pt`** (current Hub detector) in **`3step_detector`** and set **`USE_HUB_BASE = True`** in cell 3 to skip the weights zip.

---

## Contents

| Part | What |
|------|------|
| **A** | **`3step_detector`**: **`BirdLense_detector_brg.zip`** + **`nabirds_yolo11n_binary.zip`**, two-stage train (`freeze` → full), OpenVINO **640** |
| **B** | Optional legacy **binary** HF pipeline (balanced → full, **`yolo11n.pt`**, **960**) |
| **C** | Class contract, pre-production checks |

---

# Part A — Main path (`3step_detector` + BRG zip + weights zip)

## A0. Before you open Colab (local + Drive)

1. **Dataset zip.** Locally:

   ```bash
   cd /path/to/BirdLense
   python3 scripts/datasets/pack_brg_for_gdrive.py
   ```

   Output: **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`**. On Drive use **`BirdLense_detector_brg.zip`** or keep the UTC filename.

2. **Weights zip:** **`nabirds_yolo11n_binary.zip`** in **`MyDrive/3step_detector`**. Internal layout is not fixed in-repo; cell 3 searches for **`best.pt`**.

3. **`My Drive → 3step_detector`** must include the dataset zip and **`nabirds_yolo11n_binary.zip`** (unless **`USE_HUB_BASE`** + **`bl_best.pt`**).

4. Runs write to **`.../3step_detector/yolo_detector_runs/`** — reserve **multi‑GB**.

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

LAST = "/content/drive/MyDrive/3step_detector/yolo_detector_runs/brg_ft_stage1_freeze10/weights/last.pt"
YOLO(LAST).train(resume=True)  # only `resume=True` — Ultralytics requirement
```

Use the analogous **`last.pt`** path if stage 2 was interrupted.

---

## A1.c — Cold start without a suitable `.pt`

Only when **neither** **`nabirds_yolo11n_binary.zip`** **nor** **`bl_best.pt`** nor any other **three-class detect** checkpoint is available. **`YOLO("yolo11n.pt")`** reshapes the head for **3** classes from **`dataset.yaml`**; still use **`imgsz=640`**, two stages, and Part **C**. Prefer **`pip install ultralytics>=8.3.203`** (see [TRAINING](./TRAINING.md)).

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

### Cell 3 — Drive folder, dataset zip, unzip **`nabirds_yolo11n_binary.zip`**

**Canonical:** **`MyDrive/3step_detector`** holds **`BirdLense_detector_brg.zip`** (or **`BirdLense_detector_brg_*.zip`**) and **`nabirds_yolo11n_binary.zip`**.

If **`bl_best.pt`** (Hub detector) is present and you want to start from it only, set **`USE_HUB_BASE = True`** — skip the weights zip.

```python
import os
import shutil
from pathlib import Path

DRIVE_ROOT = "/content/drive/MyDrive/3step_detector"
assert os.path.isdir(DRIVE_ROOT), f"Missing folder (check path + Drive mounted): {DRIVE_ROOT}"

ZIP_DATA = os.path.join(DRIVE_ROOT, "BirdLense_detector_brg.zip")
if not os.path.isfile(ZIP_DATA):
    cands = sorted(
        Path(DRIVE_ROOT).glob("BirdLense_detector_brg_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError(
            f"No BirdLense_detector_brg.zip nor BirdLense_detector_brg_*.zip in {DRIVE_ROOT}"
        )
    ZIP_DATA = str(cands[0])
print("Dataset zip:", ZIP_DATA)

ZIP_WEIGHTS = os.path.join(DRIVE_ROOT, "nabirds_yolo11n_binary.zip")
ALT_HUB_PT = os.path.join(DRIVE_ROOT, "bl_best.pt")
USE_HUB_BASE = False  # True — use only bl_best.pt, skip nabirds zip

if USE_HUB_BASE:
    assert os.path.isfile(ALT_HUB_PT), f"USE_HUB_BASE=True but missing {ALT_HUB_PT}"
    WEIGHTS = ALT_HUB_PT
    print("Start from Hub bl_best.pt:", WEIGHTS)
else:
    assert os.path.isfile(ZIP_WEIGHTS), f"Missing weights zip: {ZIP_WEIGHTS}"
    WT_EXTRACT = "/content/nabirds_binary_weights_unzip"
    if os.path.exists(WT_EXTRACT):
        shutil.rmtree(WT_EXTRACT)
    os.makedirs(WT_EXTRACT, exist_ok=True)
    !unzip -q "{ZIP_WEIGHTS}" -d "{WT_EXTRACT}"

    root = Path(WT_EXTRACT)
    best_cands = sorted(root.rglob("best.pt"), key=lambda p: len(str(p)))
    all_pt = sorted(root.rglob("*.pt"))
    if best_cands:
        WEIGHTS = str(best_cands[0])
    elif len(all_pt) == 1:
        WEIGHTS = str(all_pt[0])
    else:
        raise FileNotFoundError(
            "No unique best.pt inside weights zip; list .pt paths manually. Found: "
            + ", ".join(str(p) for p in all_pt[:20])
        )
    print("Start from .pt inside nabirds zip:", WEIGHTS)

assert os.path.isfile(ZIP_DATA), ZIP_DATA
assert os.path.isfile(WEIGHTS), WEIGHTS
print("OK:", ZIP_DATA, WEIGHTS)
```

Adjust **`DRIVE_ROOT`** for Shared drives or a different account layout.

### Cell 4 — unzip dataset

```python
import shutil

EXTRACT = "/content/brg_dataset"
if os.path.exists(EXTRACT):
    shutil.rmtree(EXTRACT)
os.makedirs(EXTRACT, exist_ok=True)

!unzip -q "{ZIP_DATA}" -d "{EXTRACT}"
```

Expect **`/content/brg_dataset/brg/dataset.yaml`**. If layout differs, set **`DATA_YAML`** manually in the next cell.

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

If this assert fails, fix **`dataset.yaml`** and reload the zip — do **not** train yet.

### Cell 5a — checkpoint sanity (before train)

```python
from ultralytics import YOLO

m = YOLO(WEIGHTS)
task = getattr(m, "task", None)
if str(task or "").lower() != "detect":
    raise ValueError(f"Expected task=detect, got {task!r}; {WEIGHTS!r} is not a detector checkpoint.")
names_obj = m.names if m.names is not None else {}
if isinstance(names_obj, dict):
    labels = [names_obj[k] for k in sorted(names_obj.keys(), key=lambda x: int(x))]
else:
    labels = list(names_obj)
print("Model class names (id order):", labels)
if len(labels) != 3:
    raise ValueError(f"Expected 3 BRG classes, got {len(labels)}: {labels}")
assert labels == ["Bird", "Rodent", "Background"], labels
```

### Cell 6 — stage 1: frozen backbone (`freeze=10`)

**Run:** **`YOLO(WEIGHTS)`** from cell 3 ( **`nabirds` unzip or `bl_best.pt`**).

After a disconnect — **A1.b** (**`resume=True`** from **`last.pt`**).

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

One long train from **`WEIGHTS`** (cell 3):

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
