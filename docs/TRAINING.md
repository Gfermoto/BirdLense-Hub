# Training the EU classifier in Google Colab

Step-by-step: bird **classification** on a free **T4 GPU**. Dataset layout and scripts: [DATASETS](./DATASETS.md).

[Русский](./TRAINING.ru.md)

---

## What you are training

Shipped **`best.pt`** is the **EU** model (birds-525 + iNaturalist Europe, ~491 species). **US** (NABirds) backup: `best_US.pt`.

**EU training** (refresh or fine-tune) builds a classifier on European species:

- **birds-525** (Hugging Face) — 525 species in `Scientific (Common)` folder names  
- **iNaturalist Europe** — observations from Europe (`place_id` for Europe)

After merging you get ~490 classes that have images in **both** train and val splits. The US model is trained on **NABirds** (~400 North-American species); the EU set is a better default for European feeders.

The `Scientific (Common)` naming matches **Frigate** and **BirdNET**, which simplifies merging detections in Hub.

**Switching weights:** US → `cp best_US.pt best.pt`. EU → use HF `best.pt` or copy your trained file to `classification/weights/best.pt`.

## Rollout contract

BirdLense rollout candidates are considered valid only if you keep these artifacts together:

- `best.pt` for the detector or classifier slot you trained
- `class_names.txt` for classifier rollouts
- `dataset_info.json` from a `ready_for_train + strict_quality` export
- a validation report from `scripts/validate-processor-weights.py`

Recommended local gate before upload:

```bash
make validate-weights \
  BINARY=app/processor/models/detection/weights/best.pt \
  CLASSIFIER=app/processor/models/classification/weights/best.pt \
  CLASS_NAMES=/path/to/classes.txt \
  DATASET_INFO=/path/to/dataset_info.json \
  OUTPUT=/tmp/processor-weight-validation.json
```

Rollback stays simple: in UI `System -> Processor weights`, reset the custom binary/classifier slot (or both) to return to bundled defaults.

For runtime benchmarking on a fixed regression set before rollout:

```bash
python3 scripts/benchmark-track-regen.py \
  --video /path/to/video1.mp4 \
  --video /path/to/video2.mp4
```

To compare inference backends on the same clips (sets `BIRDLENSE_INFERENCE_BACKEND` for the process; JSON output includes `inference_backend`):

```bash
python3 scripts/benchmark-track-regen.py \
  --inference-backend openvino \
  --video /path/to/video1.mp4
```

Optional **gold labels sidecar** (species-level check vs fused pipeline output, [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372)): JSON with `schema_version` `1` and `gold_by_basename` mapping **video basename** → list of expected species names (same spelling as classifier output). The benchmark prints `label_eval` per video (missing/extra vs gold, `gold_species_recall`) and top-level `labels_sidecar` metadata when `--labels-json` is set. Schema reference: docstring in `scripts/benchmark_regen_labels.py`.

```bash
python3 scripts/benchmark-track-regen.py \
  --video /path/to/clip.mp4 \
  --labels-json /path/to/gold_labels.json
```

Save the same JSON to a file (for CI artifacts or baseline storage) with **`--write-report path.json`**. To compare two reports after a change (requires **`label_eval`** / **`gold_species_recall`** on matching videos):

```bash
python3 scripts/compare_benchmark_reports.py \
  --baseline /path/to/main_report.json \
  --current /path/to/pr_report.json \
  --tolerance 0.02
```

Use **`--match-by-basename`** if video paths differ between machines but filenames match.

**CI:** быстрые проверки скриптов и юнит-тестов отчётов — в общем workflow CI (`benchmark-track-regen --help`, pytest helpers, **`verify_benchmark_report_schema.py --help`**). Полный прогон пайплайна на коротком сгенерированном mp4 — workflow **`benchmark-regen-integration.yml`** (Docker + веса + запись отчёта + **`verify_benchmark_report_schema`** по артефакту при изменениях в `app/processor/**` или скриптах бенчмарка).

Локально сгенерировать такой же клип (требуется **ffmpeg**):

```bash
chmod +x scripts/ci/gen_smoke_benchmark_clip.sh
./scripts/ci/gen_smoke_benchmark_clip.sh .artifacts/smoke_clip.mp4
```

Эталонный отчёт для smoke (**без жёстких метрик recall**, только совместимость и совпадение по basename с эталоном): **`scripts/ci/reference_smoke_report.json`**. Его обновляют в том же PR, если меняется контракт smoke (например осознанно другие счётчики треков после смены весов). Интеграционный workflow вызывает **`compare_benchmark_reports.py --match-by-basename`** после **`verify_benchmark_report_schema`**.

For product-level rates from persisted `decision_trace` logs:

```bash
python3 scripts/report-yolo-product-metrics.py \
  --db app/data/db/birdlense.db \
  --dataset-info /path/to/dataset_info.json
```

---

## Prerequisites

- Google account  
- A `merged_cls` dataset (see [DATASETS](./DATASETS.md))  
- ~2–3 GB free space in Google Drive  

---

## Part 1 — Build the dataset (on your PC)

### 1.1 Create `merged_cls` (if you do not have it)

From the **repository root** (with your datasets venv activated):

```bash
# Example: venv + full pipeline
cd BirdLense-Hub   # repo root (your clone folder name may differ)
.venv-datasets/bin/python scripts/datasets/download_hf_birds.py \
  --dataset 34data/birds-525-species \
  --output datasets/birds_525_cls \
  --format scientific_common

.venv-datasets/bin/python scripts/datasets/download_inaturalist.py \
  --output datasets/inaturalist_europe_cls \
  --max-obs 2000

.venv-datasets/bin/python scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/birds_525_cls datasets/inaturalist_europe_cls \
  --output datasets/merged_cls \
  --val-ratio 0.2
```

Or reuse an existing `datasets/merged_cls` tree.

### 1.2 Zip it

```bash
cd BirdLense-Hub   # repo root
zip -r merged_cls.zip datasets/merged_cls
```

From `datasets/`:

```bash
cd BirdLense-Hub/datasets
zip -r merged_cls.zip merged_cls
```

Expect **`merged_cls.zip`** roughly **500 MB–2 GB** — this is what you upload to Drive.

---

## Part 2 — Upload to Google Drive

1. Open [drive.google.com](https://drive.google.com)  
2. Create a folder, e.g. `BirdLense_Training`  
3. Upload `merged_cls.zip` there  
4. Wait until upload completes  

---

## Part 3 — Colab first run

### 3.1 New notebook

1. [colab.research.google.com](https://colab.research.google.com)  
2. Sign in  
3. **File → New notebook**  

### 3.2 Enable GPU

1. **Runtime → Change runtime type**  
2. Hardware accelerator: **T4 GPU**  
3. Save  

Sanity check: run `!nvidia-smi` in a cell — you should see the T4.

---

## Part 4 — Notebook cells (run in order)

Create code cells and run **top to bottom** (Shift+Enter).

---

### Cell 1 — Mount Google Drive

```python
# Dataset + runs live on Drive
from google.colab import drive
drive.mount('/content/drive')
```

First run opens an auth flow: approve access, paste the token if prompted.

---

### Cell 2 — Paths and unzip

**Edit `DRIVE_FOLDER`** if your Drive folder name differs.

```python
import os
import shutil

# === EDIT THESE ===
DRIVE_FOLDER = "BirdLense_Training"   # folder on Google Drive
ZIP_NAME = "merged_cls.zip"           # zip you uploaded
PROJECT_NAME = "birds_eu_cls_v1"     # run name under runs/
# ==================

DRIVE_ROOT = "/content/drive/MyDrive"
DRIVE_PATH = os.path.join(DRIVE_ROOT, DRIVE_FOLDER)
ZIP_PATH = os.path.join(DRIVE_PATH, ZIP_NAME)
DATASET_DIR = "/content/merged_cls"  # fast local unpack target
PROJECT_ROOT = os.path.join(DRIVE_PATH, "runs")

if not os.path.exists(ZIP_PATH):
    print(f"Missing: {ZIP_PATH}")
    print("Check DRIVE_FOLDER / ZIP_NAME. Drive root listing:")
    if os.path.exists(DRIVE_ROOT):
        for f in os.listdir(DRIVE_ROOT):
            print(f"  - {f}")
else:
    print(f"Found: {ZIP_PATH}")
    # zip built as: zip -r merged_cls.zip datasets/merged_cls
    !unzip -q -o "{ZIP_PATH}" -d /content/
    for p in ["/content/datasets/merged_cls", "/content/merged_cls", "/content/merged_cls/merged_cls"]:
        if os.path.exists(p) and os.path.exists(os.path.join(p, "train")):
            DATASET_DIR = p
            break
    train_path = os.path.join(DATASET_DIR, "train")
    val_path = os.path.join(DATASET_DIR, "val")
    if os.path.exists(train_path):
        def has_images(p):
            return any(f.lower().endswith(('.jpg','.jpeg','.png','.webp')) for f in os.listdir(p))
        train_classes = {d for d in os.listdir(train_path) if os.path.isdir(os.path.join(train_path, d)) and has_images(os.path.join(train_path, d))}
        val_classes = {d for d in os.listdir(val_path) if os.path.isdir(os.path.join(val_path, d)) and has_images(os.path.join(val_path, d))} if os.path.exists(val_path) else set()
        valid = train_classes & val_classes
        for c in list(os.listdir(train_path)):
            if c not in valid and os.path.isdir(os.path.join(train_path, c)):
                shutil.rmtree(os.path.join(train_path, c), ignore_errors=True)
        for c in list(os.listdir(val_path)) if os.path.exists(val_path) else []:
            if c not in valid and os.path.isdir(os.path.join(val_path, c)):
                shutil.rmtree(os.path.join(val_path, c), ignore_errors=True)
        n_classes = len(valid)
        if len(train_classes) != n_classes or len(val_classes) != n_classes:
            print(f"Removed classes missing in both splits. Remaining: {n_classes}")
        print(f"Dataset ready: {DATASET_DIR}, classes: {n_classes}")
    else:
        print("Check layout: need train/ and val/ with per-class folders")
```

Use Colab’s file browser if paths look wrong after unzip.

---

### Cell 3 — Ultralytics

```python
# 8.3.203+ fixes GradScaler issues on resume
!pip install -q -U ultralytics
print("Ultralytics installed")
```

---

### Cell 4 — Train

**T4 15 GB:** start with `batch=64`; drop to 32/16 on OOM.

**Rough timing:** ~2.5 min/epoch on GPU → 100 epochs ≈ 4 h. CPU is 10–20× slower. Colab Free may disconnect — use **resume** (Part 5).

**Match `PROJECT_ROOT`** to your Drive folder.

```python
from ultralytics import YOLO
import os

for p in ["/content/datasets/merged_cls", "/content/merged_cls"]:
    if os.path.exists(p) and os.path.exists(os.path.join(p, "train")):
        DATASET_DIR = p
        break
else:
    DATASET_DIR = "/content/datasets/merged_cls"

PROJECT_ROOT = "/content/drive/MyDrive/BirdLense_Training/runs"  # edit folder name
PROJECT_NAME = "birds_eu_cls_v1"

os.makedirs(PROJECT_ROOT, exist_ok=True)
ckpt_path = os.path.join(PROJECT_ROOT, PROJECT_NAME, "weights", "last.pt")

DEVICE = 0 if __import__('torch').cuda.is_available() else 'cpu'
BATCH = 64 if DEVICE != 'cpu' else 16
EPOCHS = 100  # 80–100 is enough for merged_cls (plateau ~50–60)

if os.path.exists(ckpt_path):
    print("Resuming from checkpoint...")
    model = YOLO(ckpt_path)
    model.train(resume=True, device=DEVICE, epochs=EPOCHS, amp=False)
else:
    print("Training from scratch...")
    model = YOLO("yolo11n-cls.pt")
    model.train(
        data=DATASET_DIR,
        epochs=EPOCHS,
        imgsz=224,
        batch=BATCH,
        patience=30,
        project=PROJECT_ROOT,
        name=PROJECT_NAME,
        exist_ok=True,
        device=DEVICE,
        workers=2,
    )
```

---

### Cell 5 — Copy `best.pt` to Drive root (easy download)

```python
import shutil
import os

DRIVE_FOLDER = "BirdLense_Training"
PROJECT_ROOT = f"/content/drive/MyDrive/{DRIVE_FOLDER}/runs"
PROJECT_NAME = "birds_eu_cls_v1"
DRIVE_PATH = f"/content/drive/MyDrive/{DRIVE_FOLDER}"
source_dir = os.path.join(PROJECT_ROOT, PROJECT_NAME)

if os.path.exists(source_dir):
    best_pt = os.path.join(source_dir, "weights", "best.pt")
    if os.path.exists(best_pt):
        drive_dest = os.path.join(DRIVE_PATH, "best.pt")
        shutil.copy(best_pt, drive_dest)
        print(f"best.pt copied to: {drive_dest}")
        print("Download from Drive UI (right-click → Download)")
    else:
        print("Training still running — best.pt appears when finished")
else:
    print("Run folder not found — check PROJECT_ROOT / PROJECT_NAME")
```

---

## Part 5 — Resume after disconnect

Colab may stop after ~12 h. If training is incomplete:

1. Re-run **cells 1–4**. A new session clears `/content` — you **must** unzip again (cell 2) or you get *no training images found*.  
2. Cell 4 picks up `last.pt` from Drive automatically.  
3. Training continues from the last epoch.

Checkpoints live under `Drive/.../BirdLense_Training/runs/birds_eu_cls_v1/weights/`.

### Training finished but you want “more epochs”

For **merged_cls**, metrics usually **plateau by epoch 50–60**. The shipped **`best.pt` is already the best epoch** — you normally **should not** extend epochs.

If you still need extra training (new experiment) and see *training to N epochs is finished, nothing to resume*, start a **new** run **without** `resume=True` and use a **low LR**:

```python
model = YOLO(".../last.pt")
model.train(
    data=DATASET_DIR,
    epochs=50,
    lr0=0.0001,
    imgsz=224,
    batch=64,
    patience=15,
    project=".../runs",
    name="birds_eu_cls_v1_cont",
    exist_ok=True,
    device=0,
    workers=2,
    amp=False,
)
```

---

## Part 5.1 — What to copy off Drive

To resume elsewhere (another Colab session or machine):

| Path | Why |
|------|-----|
| `.../runs/birds_eu_cls_v1/weights/last.pt` | Resume training |
| `.../runs/birds_eu_cls_v1/weights/best.pt` | Best weights when run completes |
| `.../BirdLense_Training/best.pt` | Convenience copy from cell 5 |
| `merged_cls.zip` | Dataset (or re-download from Hugging Face) |

**Minimum to resume:** `last.pt` + dataset zip + notebook.

**Notebook:** File → Save a copy on Drive, or Download `.ipynb`. You can commit a template under `scripts/` if you want version control.

**New Colab:** upload `last.pt` + zip to a Drive folder, set `DRIVE_FOLDER` in cells 2 and 4, open the `.ipynb`.

---

## Part 6 — Install weights in BirdLense Hub

1. Download `best.pt` from [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (or Drive).  
2. Place at:
   ```
   app/processor/models/classification/weights/best.pt
   ```
   Keep US backup as `best_US.pt` if you switch regions.  
3. If you use **NCNN** (`single_stage`) on **x86/amd64**, export per Ultralytics docs / internal scripts (see [ROADMAP](./ROADMAP.md)). ARM is not a supported target.  
4. Deploy: `make deploy` (or your pipeline).

---

## Part 7 — Fine-tune: add species

Load existing `best.pt` and train on **old + new** classes.

### 7.1 Folder layout (`Scientific (Common)`)

```
datasets/new_species_cls/
├── train/
│   ├── Garrulus glandarius (Eurasian Jay)/
│   ├── Parus major (Great Tit)/
│   └── ...
└── val/
    └── (same classes, ~20% of images)
```

Aim for **20–30** train images per class (and **5+** in val). Merge tools can append to classes that already exist in `merged_cls`.

### 7.2 Merge with base dataset

```bash
python scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/merged_cls datasets/new_species_cls \
  --output datasets/merged_cls_extended \
  --val-ratio 0.2
```

### 7.3 Colab fine-tune (replace cell 4 logic)

Use **`best.pt`**, dataset **`merged_cls_extended`**, fewer epochs, moderate LR:

```python
from ultralytics import YOLO

BEST_PT = "/content/drive/MyDrive/BirdLense_Training/best.pt"
DATASET_DIR = "/content/datasets/merged_cls_extended"

model = YOLO(BEST_PT)
model.train(
    data=DATASET_DIR,
    epochs=30,
    imgsz=224,
    batch=64,
    lr0=0.001,
    patience=10,
    project="/content/drive/MyDrive/BirdLense_Training/runs",
    name="birds_eu_cls_finetune",
    exist_ok=True,
    device=0,
)
```

Unpack `merged_cls_extended.zip` in Colab before training.

### 7.4 Fine-tune from BirdLense export (`birdlense_ready`)

Drive layout:

```
BirdLense_Annotations/
├── birdlense_ready.zip
└── best.pt
```

Cells:

```python
from google.colab import drive
drive.mount('/content/drive')
```

```python
import os
DRIVE_FOLDER = "BirdLense_Annotations"
ZIP_NAME = "birdlense_ready.zip"
DRIVE_PATH = f"/content/drive/MyDrive/{DRIVE_FOLDER}"
ZIP_PATH = os.path.join(DRIVE_PATH, ZIP_NAME)

!unzip -q -o "{ZIP_PATH}" -d /content/
DATASET_DIR = "/content/datasets/birdlense_ready"
if not os.path.exists(os.path.join(DATASET_DIR, "train")):
    DATASET_DIR = "/content/birdlense_ready"
print(f"Dataset: {DATASET_DIR}")
```

```python
!pip install -q -U ultralytics
```

```python
from ultralytics import YOLO

BEST_PT = "/content/drive/MyDrive/BirdLense_Annotations/best.pt"
DATASET_DIR = "/content/datasets/birdlense_ready"

model = YOLO(BEST_PT)
model.train(
    data=DATASET_DIR,
    epochs=30,
    imgsz=224,
    batch=64,
    lr0=0.001,
    patience=10,
    project="/content/drive/MyDrive/BirdLense_Annotations/runs",
    name="birds_finetune",
    exist_ok=True,
    device=0,
    workers=2,
)
```

```python
import shutil, os
best = "/content/drive/MyDrive/BirdLense_Annotations/runs/birds_finetune/weights/best.pt"
if os.path.exists(best):
    shutil.copy(best, "/content/drive/MyDrive/BirdLense_Annotations/best_finetuned.pt")
    print("Saved best_finetuned.pt to Drive")
```

Copy `best_finetuned.pt` → `app/processor/models/classification/weights/best.pt`, then deploy.

---

## Part 8 — Troubleshooting

### Cannot enable GPU

Runtime → Change runtime type → **T4 GPU**. Free tier GPUs can be unavailable — retry later.

### OOM

Lower `batch` in cell 4 (64 → 32 → 16).

### Zip not found

Check `DRIVE_FOLDER` / `ZIP_NAME` and that upload finished.

### Session died / “no training images found”

See [Colab limits](https://research.google.com/colaboratory/faq.html#usage-limits). `/content` is ephemeral — rerun cells **1–4** (unzip + train). `last.pt` on Drive enables resume.

### “training to N epochs is finished, nothing to resume”

Run already finished all epochs. For merged_cls you rarely need more; see **Part 5** if you intentionally start a continuation run.

### “GradScaler state dict is empty” on resume

1. Patch checkpoint (strip empty scaler):

   ```python
   import torch, shutil
   ckpt_path = "/content/drive/MyDrive/BirdLense_Training/runs/birds_eu_cls_v1/weights/last.pt"
   ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
   if "scaler" in ckpt and (ckpt["scaler"] is None or len(ckpt.get("scaler", {})) == 0):
       shutil.copy(ckpt_path, ckpt_path + ".backup")
       del ckpt["scaler"]
       torch.save(ckpt, ckpt_path)
   ```

2. `!pip install -U ultralytics` (≥ 8.3.203).  
3. `model.train(..., resume=True, amp=False)` (already in cell 4).

---

## Checklist

- [ ] `merged_cls` built and zipped  
- [ ] Zip uploaded to Drive  
- [ ] Runtime = T4 GPU  
- [ ] Cells 1–5 executed in order  
- [ ] `best.pt` downloaded / copied  
- [ ] Copied to `classification/weights/best.pt` and deployed  
- [ ] `best_US.pt` kept as backup  

---

## Epoch budget (80–100)

Empirically on merged_cls: plateau **~50–60** epochs (~85% top-1). **80–100** epochs ≈ **3–4 h** on T4. Going to 150+ is usually wasted wall time if `best.pt` already exists.

---

## Hugging Face

**Repos:** [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (dataset), [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (weights), [gfermoto/birdlense-annotations](https://huggingface.co/datasets/gfermoto/birdlense-annotations) (labels).

**Token:** [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → create token → `huggingface-cli login`.

**Upload dataset:** Web UI or `huggingface-cli upload gfermoto/birds-eu-merged merged_cls.zip . --repo-type dataset`. **Download in Colab:** `hf_hub_download(repo_id="gfermoto/birds-eu-merged", filename="merged_cls.zip", repo_type="dataset")`.

**Weights:** `huggingface-cli download gfermoto/birdlense-birds-eu best.pt --local-dir app/processor/models/classification/weights`.

**Model card hints:** `datasets: - gfermoto/birds-eu-merged`, tags `image-classification`, `birds`, `europe`, `birdlense`, `yolo`. Free tier limits apply (dataset/model storage caps).

---

## See also

[DATASETS](./DATASETS.md)
