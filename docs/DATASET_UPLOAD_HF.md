# Загрузка merged_cls на Hugging Face

Пошаговая инструкция: как выложить датасет EU-птиц (birds-525 + iNaturalist) на Hugging Face.

---

## Шаг 1: Создать репозиторий

1. Перейдите на [huggingface.co/new-dataset](https://huggingface.co/new-dataset)
2. **Owner:** ваш аккаунт (например `gfermoto`)
3. **Dataset name:** `birds-eu-merged` (или другое имя)
4. **License:** выберите лицензию (например `cc-by-nc-4.0` — учтите лицензии iNaturalist)
5. **Create repository**

---

## Шаг 2: Dataset card (README)

В репозитории откройте **Dataset card** → **Edit**. Скопируйте **весь блок ниже** (от --- до конца) и вставьте:

````
---
license: cc-by-nc-4.0
task_categories:
  - image-classification
tags:
  - birds
  - europe
  - birdlense
  - yolo
  - scientific-name
---

# Birds EU Merged

European bird species classification dataset for [BirdLense Hub](https://github.com/Gfermoto/BirdLense-Hub). ~490 species, format `Scientific (Common)` — совместим с Frigate и BirdNET.

## Sources

- [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species) — Hugging Face
- [iNaturalist](https://www.inaturalist.org/) — Europe (place_id=96372), API

## Structure

```
merged_cls/
├── train/           # ~17 800 images
│   ├── Parus major (Great Tit)/
│   ├── Garrulus glandarius (Eurasian Jay)/
│   └── ...          # 491 classes
└── val/             # ~4 600 images
    └── (same classes)
```

## Usage

### Download and unzip

```bash
huggingface-cli download gfermoto/birds-eu-merged merged_cls.zip --repo-type dataset --local-dir .
unzip merged_cls.zip
```

### Python

```python
from huggingface_hub import hf_hub_download
import zipfile
path = hf_hub_download(repo_id="gfermoto/birds-eu-merged", filename="merged_cls.zip", repo_type="dataset")
with zipfile.ZipFile(path) as z:
    z.extractall(".")
```

### Training (Ultralytics YOLO)

```python
from ultralytics import YOLO
model = YOLO("yolo11n-cls.pt")
model.train(data="datasets/merged_cls", epochs=150, imgsz=224)
```

## License

CC BY-NC 4.0. Sources: birds-525, iNaturalist (see their respective licenses).
````

Сохраните (Commit).

---

## Шаг 3: Загрузить ZIP

### Вариант A: Web UI

1. В репозитории → **Files and versions** → **Add file** → **Upload files**
2. Перетащите `merged_cls.zip` (~500 MB)
3. В поле **Commit message** введите:
   ```
   Add merged_cls.zip — birds-525 + iNaturalist Europe, ~491 species, train/val
   ```
4. Дождитесь окончания загрузки

**Ограничение:** файлы до 5 GB поддерживаются. 500 MB — ок.

### Вариант B: CLI

```bash
cd /home/gfer/BirdLense

# Логин (если ещё не)
huggingface-cli login

# Загрузка (commit message — описание коммита)
huggingface-cli upload gfermoto/birds-eu-merged merged_cls.zip . --repo-type dataset --commit-message "Add merged_cls.zip — birds-525 + iNaturalist Europe, ~491 species, train/val"
```

### Вариант C: Python

```python
from huggingface_hub import HfApi

api = HfApi()
api.upload_file(
    path_or_fileobj="merged_cls.zip",
    path_in_repo="merged_cls.zip",
    repo_id="gfermoto/birds-eu-merged",
    repo_type="dataset",
    commit_message="Add merged_cls.zip — birds-525 + iNaturalist Europe, ~491 species, train/val",
)
```

---

## Шаг 4: Альтернатива — загрузить папку (без ZIP)

Если хотите выложить структуру `train/` и `val/` напрямую (без архива):

```python
from huggingface_hub import HfApi

api = HfApi()
api.upload_folder(
    folder_path="datasets/merged_cls",
    repo_id="gfermoto/birds-eu-merged",
    repo_type="dataset",
    path_in_repo=".",
)
```

Для большого числа файлов (~22k) лучше `upload_large_folder` — устойчивее к обрывам:

```python
api.upload_large_folder(
    folder_path="datasets/merged_cls",
    repo_id="gfermoto/birds-eu-merged",
    repo_type="dataset",
)
```

---

## Шаг 5: Проверка

1. Откройте [huggingface.co/datasets/gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged)
2. Убедитесь, что `merged_cls.zip` (или `train/`, `val/`) на месте
3. Dataset card отображается корректно

---

## Использование в COLAB_TRAINING

После загрузки можно изменить ячейку 2 в Colab — качать с HF вместо Drive:

```python
# Вместо unzip из Drive — скачать с Hugging Face
from huggingface_hub import hf_hub_download
import zipfile
import os

path = hf_hub_download(repo_id="gfermoto/birds-eu-merged", filename="merged_cls.zip", repo_type="dataset")
os.makedirs("/content", exist_ok=True)
with zipfile.ZipFile(path) as z:
    z.extractall("/content")
# Путь: /content/datasets/merged_cls
```

---

## Загрузка весов модели (best.pt)

После обучения EU-модели в Colab веса можно выложить на Hugging Face.

### Создать репозиторий Model

1. [huggingface.co/new](https://huggingface.co/new) → **Model**
2. **Model name:** `birdlense-birds-eu` (или `birds-eu-yolo`)
3. **Create repository**

### Загрузить best.pt

```bash
huggingface-cli login
huggingface-cli upload gfermoto/birdlense-birds-eu best.pt . --commit-message "Add best.pt — YOLO11n-cls, EU birds (~491 species), trained on birds-eu-merged"
```

### Model card (README)

В репозитории → **Model card** → **Edit**. Укажите: архитектура (YOLO11n-cls), датасет ([gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged)), метрики.

### Скачать в BirdLense

```bash
huggingface-cli download gfermoto/birdlense-birds-eu best.pt --local-dir app/processor/models/classification/weights
```

---

См. также: [HUGGINGFACE_HUB.md](./HUGGINGFACE_HUB.md), [COLAB_TRAINING.md](./COLAB_TRAINING.md).
