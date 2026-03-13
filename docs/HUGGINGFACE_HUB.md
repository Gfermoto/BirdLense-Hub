# Hugging Face Hub — создание, установка, работа

Руководство по работе с [Hugging Face Hub](https://huggingface.co) для хранения датасетов, моделей и артефактов BirdLense Hub.

---

## 1. Регистрация и токен

### Регистрация

1. Перейдите на [huggingface.co/join](https://huggingface.co/join)
2. Заполните форму, подтвердите email

### Токен доступа

Токен нужен для загрузки и скачивания через CLI и Python.

1. [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. **New token** → имя (например, `birdlense`) → права **Read** или **Write**
3. Скопируйте токен (показывается один раз)

```bash
# Сохранить в app/.env (не коммитится) или переменную окружения
# HF_TOKEN=hf_xxxxxxxxxxxx
export HF_TOKEN="hf_xxxxxxxxxxxx"
```

**Безопасность:** токен не должен попадать в Git. Используйте `app/.env` (в .gitignore) или переменные окружения.

---

## 2. Создание репозитория

### Типы репозиториев

| Тип | Назначение | URL создания |
|-----|------------|--------------|
| **Dataset** | Датасеты (изображения, аннотации, YOLO) | [huggingface.co/new-dataset](https://huggingface.co/new-dataset) |
| **Model** | Модели (веса YOLO, PyTorch) | [huggingface.co/new](https://huggingface.co/new) |
| **Space** | Веб-приложения, демо | [huggingface.co/spaces/new](https://huggingface.co/spaces/new) |

### Создание датасета через Web UI

1. Войдите в аккаунт
2. Аватар (правый верхний угол) → **New Dataset**
3. Или напрямую: [huggingface.co/new-dataset](https://huggingface.co/new-dataset)
4. Укажите имя, видимость (Public/Private), лицензию
5. **Create repository**

### Создание через CLI

```bash
# Логин (один раз)
huggingface-cli login

# Датасет
huggingface-cli repo create birdlense-annotations --type dataset

# Модель
huggingface-cli repo create birdlense-yolo --type model
```

### Создание через Python

```python
from huggingface_hub import create_repo

create_repo("gfermoto/birdlense-annotations", repo_type="dataset", private=False)
```

---

## 3. Установка

### huggingface_hub (CLI + Python)

```bash
pip install huggingface_hub
```

### datasets (для загрузки датасетов)

```bash
pip install datasets
```

### Логин

```bash
huggingface-cli login
# Вставьте токен при запросе
```

Или через переменную окружения:

```bash
export HF_TOKEN="hf_xxxxxxxxxxxx"
```

---

## 4. Загрузка файлов

### Web UI (drag-and-drop)

1. Откройте репозиторий → вкладка **Files and versions**
2. **Add file** → загрузите файлы или перетащите папку
3. Поддерживаются: изображения (.jpg, .png), CSV, JSON, Parquet, YAML и др.

### Git

Репозитории Hub — это Git-репозитории:

```bash
# Клонирование
git clone https://huggingface.co/datasets/gfermoto/birdlense-annotations
cd birdlense-annotations

# Добавление файлов
mkdir -p train/images train/labels
cp /path/to/images/* train/images/
cp /path/to/labels/* train/labels/
cp data.yaml .

git add .
git commit -m "Add YOLO dataset"
git push
```

### Python (huggingface_hub)

```python
from huggingface_hub import HfApi

api = HfApi()

# Загрузить папку
api.upload_folder(
    folder_path="./local_dataset",
    repo_id="gfermoto/birdlense-annotations",
    repo_type="dataset",
)

# Загрузить один файл
api.upload_file(
    path_or_fileobj="./data.yaml",
    path_in_repo="data.yaml",
    repo_id="gfermoto/birdlense-annotations",
    repo_type="dataset",
)
```

### CLI

```bash
huggingface-cli upload gfermoto/birdlense-annotations ./local_folder/ . --repo-type dataset
```

---

## 5. Скачивание и использование

### Загрузка датасета (datasets)

```python
from datasets import load_dataset

ds = load_dataset("gfermoto/birdlense-annotations", split="train")
# или для image folder
ds = load_dataset("imagefolder", data_dir="path/to/images")
```

### Скачивание репозитория целиком

```bash
huggingface-cli download gfermoto/birdlense-annotations --repo-type dataset --local-dir ./birdlense-data
```

### Python

```python
from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="gfermoto/birdlense-annotations",
    repo_type="dataset",
    local_dir="./birdlense-data",
)
```

---

## 6. Dataset card (README.md)

README.md в корне репозитория — описание датасета для сообщества.

**Шаблон:** [dataset-card-readme.md](./dataset-card-readme.md) — готовый README с YAML-метаданными для страницы датасета на Hugging Face. Скопируйте в Dataset card → Edit.

В Web UI: вкладка **Dataset card** → **Edit** → шаблон можно импортировать.

---

## 7. Репозитории BirdLense

| Репозиторий | Назначение |
|-------------|------------|
| [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged) | EU-датасет (birds-525 + iNaturalist, ~491 вид) |
| [gfermoto/birdlense-birds-eu](https://huggingface.co/models/gfermoto/birdlense-birds-eu) | Веса EU-модели (best.pt) |
| [gfermoto/birdlense-annotations](https://huggingface.co/datasets/gfermoto/birdlense-annotations) | Датасет разметки (YOLO) |

---

## 8. Ограничения и лимиты

- **Бесплатный аккаунт:** 50 GB для датасетов, 10 GB для моделей
- **Файлы:** до 5 GB на файл (через Web UI). Крупные — через Git LFS или `huggingface_hub`
- **Private:** бесплатно для личных репозиториев

Подробнее: [Storage limits](https://huggingface.co/docs/hub/en/storage-limits)

---

См. также: [DATASET_SOURCES.md](./DATASET_SOURCES.md), [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md), [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md), [dataset-card-readme.md](./dataset-card-readme.md).
