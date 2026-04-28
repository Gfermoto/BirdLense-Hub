# Детектор (binary): три источника перед merge

Рядом со скриптами в `scripts/datasets/` каталог **`binary/`** задаёт единую точку входа:

| Подпапка | Назначение |
|----------|------------|
| **`birds/`** | Один класс «птица» (YOLO `train|val/images` + `labels`). |
| **`rodent/`** | Один класс «грызун» (исторически белка/OID → метка Hub **Rodent**). |
| **`background/`** | Фон: пустые `.txt` или боксы класса Background. |

После заполнения: из корня репозитория **`make dataset-merge-three-class`** → результат в **`binary/merged/`** (`dataset.yaml`: Bird / Rodent / Background).

Сами изображения и разметка в подпапках **не коммитятся** (см. `.gitignore`). Подробнее: [DETECTOR_DATA_LAYOUT.md](../DETECTOR_DATA_LAYOUT.md).
