# Hugging Face — датасеты и модели BirdLense

Руководство по работе с [Hugging Face Hub](https://huggingface.co): датасет merged_cls, веса EU-модели, базовые операции.

---

## Репозитории BirdLense

| Репозиторий | Назначение |
|-------------|------------|
| [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged) | EU-датасет (birds-525 + iNaturalist, ~491 вид) |
| [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) | Веса EU-модели (best.pt) |
| [gfermoto/birdlense-annotations](https://huggingface.co/datasets/gfermoto/birdlense-annotations) | Датасет разметки (YOLO) |

---

## 1. Токен и логин

1. [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → **New token** → права **Write**
2. `pip install huggingface_hub` → `huggingface-cli login` → вставьте токен

---

## 2. Загрузка датасета merged_cls

### Создать репозиторий

[huggingface.co/new-dataset](https://huggingface.co/new-dataset) → **Dataset name:** `birds-eu-merged` → **License:** `cc-by-nc-4.0` → Create

### Dataset card

**Dataset card** → **Edit** → скопируйте из [birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged) или адаптируйте под формат classification (`train/ClassName/img.jpg`).

### Загрузить ZIP

**Web:** Files and versions → Add file → Upload files → перетащить `merged_cls.zip` (~500 MB)

**CLI:**
```bash
huggingface-cli upload gfermoto/birds-eu-merged merged_cls.zip . --repo-type dataset --commit-message "Add merged_cls.zip — birds-525 + iNaturalist Europe, ~491 species, train/val"
```

### Скачать в Colab

```python
from huggingface_hub import hf_hub_download
import zipfile
path = hf_hub_download(repo_id="gfermoto/birds-eu-merged", filename="merged_cls.zip", repo_type="dataset")
with zipfile.ZipFile(path) as z:
    z.extractall("/content")
# Путь: /content/datasets/merged_cls
```

---

## 3. Загрузка модели best.pt

### Создать репозиторий Model

[huggingface.co/new](https://huggingface.co/new) → **Model** → **Model name:** `birdlense-birds-eu` → **License:** `cc-by-nc-4.0` → Create

### Загрузить best.pt

**Web:** [birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) → Files and versions → Add file → Upload files → перетащить `best.pt`.

**CLI:**
```bash
huggingface-cli upload gfermoto/birdlense-birds-eu app/processor/models/classification/weights/best.pt . --commit-message "Add best.pt — YOLO11n-cls, EU birds (~491 species), trained on birds-eu-merged"
```

### Model card (связь с датасетом)

**Model card** → **Edit** → в YAML обязательно:

```yaml
---
license: cc-by-nc-4.0
datasets:
  - gfermoto/birds-eu-merged
tags:
  - image-classification
  - birds
  - europe
  - birdlense
  - yolo
  - ultralytics
pipeline_tag: image-classification
library_name: ultralytics
---
```

Полный шаблон: [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu).

### Обратная ссылка в датасете

В Dataset card датасета добавьте секцию **Trained models**:

```markdown
## Trained models

- [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) — YOLO11n-cls, ~85% top1 val
```

### Скачать в BirdLense

```bash
huggingface-cli download gfermoto/birdlense-birds-eu best.pt --local-dir app/processor/models/classification/weights
```

---

## 4. Ограничения

- **Бесплатный аккаунт:** 50 GB датасеты, 10 GB модели
- **Файлы:** до 5 GB на файл (Web UI). Крупные — через Git LFS или `huggingface_hub`

---

## 5. Шаблон Dataset card (birdlense-annotations)

Для датасета разметки в формате YOLO detection ([gfermoto/birdlense-annotations](https://huggingface.co/datasets/gfermoto/birdlense-annotations)):

```markdown
---
license: cc-by-nc-nd-4.0
task_categories:
  - object-detection
  - image-classification
tags:
  - birds
  - bird-feeder
  - yolo
  - birdlense
  - wildlife
language:
  - en
size_categories:
  - n<1K
  - 1K<n<10K
  - 10K<n<100K
---

# BirdLense Annotations

Dataset of bird annotations from feeders for the [BirdLense Hub](https://github.com/Gfermoto/BirdLense-Hub) project — a bird feeder monitoring system with detection (YOLO, BirdNET).

## Description

Images of birds and squirrels captured by BirdLense cameras at feeders. Annotations in YOLO format (bounding boxes) for training and fine-tuning detection models. Data is collected by community members through confirming and correcting automatic detections.

## Dataset Structure

    train/
      images/     # Training images
      labels/     # YOLO annotations (.txt)
    val/
      images/
      labels/
    data.yaml     # Class configuration and paths

## Classes

Species list is defined in `data.yaml`. Typical categories: birds (tits, sparrows, woodpeckers, etc.), squirrels, mice.

## Usage

### Download

    from huggingface_hub import snapshot_download

    path = snapshot_download(
        repo_id="gfermoto/birdlense-annotations",
        repo_type="dataset",
        local_dir="./birdlense-data",
    )

### YOLO Training

    yolo detect train data=./birdlense-data/data.yaml model=yolov8n.pt epochs=100

## Data Source

- **BirdLense Hub** — open-source bird feeder monitoring system
- Detection: YOLO + BirdNET
- Labeling: user confirmation/correction in the UI

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — attribution required, non-commercial, no derivatives without permission.

## Links

- [BirdLense Hub](https://github.com/Gfermoto/BirdLense-Hub)
- [BirdLense Documentation](https://github.com/Gfermoto/BirdLense-Hub/tree/main/docs)
```

---

См. также: [TRAINING.md](./TRAINING.md), [DATASETS.md](./DATASETS.md).
