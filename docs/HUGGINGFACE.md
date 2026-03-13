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

**Dataset card** → **Edit** → вставьте шаблон из [dataset-card-readme.md](./dataset-card-readme.md) — или скопируйте из [birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged).

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

См. также: [TRAINING.md](./TRAINING.md), [DATASETS.md](./DATASETS.md).
