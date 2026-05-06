# Детектор (binary): три источника перед merge

Рядом со скриптами в `scripts/datasets/` каталог **`binary/`** задаёт единую точку входа:

| Подпапка | Назначение |
|----------|------------|
| **`birds/`** | **COCO bird**, **Open Images Bird** (`bootstrap_detector_yolo.py`), **CUB-200-2011** (`make dataset-import-cub`), **Roboflow YOLOv11** кормушка ([Bird-Feeder v3](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11): `make dataset-import-roboflow-bird-feeder`). |
| **`rodent/`** | Один класс «грызун» (исторически белка/OID → метка Hub **Rodent**). |
| **`background/`** | Фон: пустые `.txt` или боксы класса Background. |

После заполнения: из корня репозитория **`make dataset-merge-three-class`** → результат в **`binary/merged/`** (`dataset.yaml`: Bird / Rodent / Background).

Сами изображения и разметка в подпапках **не коммитятся** (см. `.gitignore`). Из‑за этого **дерево файлов в Cursor / VS Code может не показывать** `birds/`, `rodent/`, `background/` — проверьте в терминале: `ls birds/train/images | head`.

Подробнее: структура каталогов, bootstrap и качество — [DETECTOR_DATASET_QUALITY.md](../DETECTOR_DATASET_QUALITY.md).
