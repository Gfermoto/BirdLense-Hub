# Датасеты и модели BirdLense

[English](./DATASETS.md)

---

Справочник: форматы, скрипты, источники, оборудование. **Обучение:** [TRAINING](./TRAINING.ru.md).

---

## 1. Модели

| Компонент | Версия | Дообучено на |
|-----------|--------|--------------|
| **Детектор** | YOLOv8n | NABirds + COCO birds + OIDv4 squirrel (бинарный bird/squirrel) |
| **Классификатор EU** | YOLO11n-cls | birds-525 + iNaturalist (~491 вид) — активна в `best.pt` |
| **Классификатор US** | YOLOv8n-cls | NABirds (~400 видов) — резерв в `best_US.pt` |

Вернуть US: `cp best_US.pt best.pt`.

---

## 2. Формат имён: Scientific (Common)

Единый формат для merge, Frigate, BirdNET, YOLO:

| Источник | Исходный формат | После приведения |
|----------|-----------------|------------------|
| **Frigate** | `Cardinalis cardinalis (Northern Cardinal)` | уже в формате |
| **iNaturalist** | `Columba palumbus` | `Columba palumbus (Common Wood Pigeon)` |
| **birds-525** | `GOLDEN_EAGLE` | `Aquila chrysaetos (Golden Eagle)` |

**YOLO classification:** `train/Parus major (Great Tit)/img.jpg`, `val/` — те же классы.

---

## 3. Скрипты (`scripts/datasets/`)

### EU-классификатор (birds-525 + iNaturalist)

| Скрипт | Назначение |
|--------|------------|
| `download_hf_birds.py` | Hugging Face → YOLO cls (`--format scientific_common`) |
| `download_inaturalist.py` | iNaturalist Europe → YOLO cls |
| `merge_classification_datasets.py` | Объединить датасеты |
| `download_and_merge_all.sh` | Полный пайплайн → merged_cls |

### Детектор (legacy)

| Скрипт | Назначение |
|--------|------------|
| `convert_nabirds_to_yolo.py` | NABirds → YOLO |
| `download_coco_birds.py` | COCO birds — для binary |
| `merge_datasets_binary.py` | NABirds + COCO → binary |

### Модели (`app/processor/models/`)

| Путь | Роль |
|------|------|
| `classification/weights/best.pt` | EU-классификатор (активна) |
| `classification/weights/best_US.pt` | Резерв US |
| `detection/weights/best.pt` | Бинарный детектор |

---

## 4. Источники датасетов

### Для EU (приоритет)

| Датасет | Видов | Ссылка |
|---------|-------|--------|
| **[34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species)** | 525 | Hugging Face |
| **iNaturalist Europe** | Тысячи | [API](https://api.inaturalist.org/v1/docs/), `place_id=96372` |

### Северная Америка (не дают улучшения по EU)

| Датасет | Видов |
|---------|-------|
| NABirds | ~400 |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 |

---

## 5. Оборудование

| Платформа | GPU | Цена |
|-----------|-----|------|
| **Google Colab** | T4 (15 GB) | Бесплатно |
| **RunPod** | RTX 4090, A100 | ~$0.40–0.80/ч |
| **Локально** | Своя видеокарта | — |

**Рекомендация:** Colab Free (T4) — [TRAINING](./TRAINING.ru.md).

---

## 6. Пайплайн: сбор → обучение

```
BirdLense (записи) → export_birdlense_to_yolo.py (планируется) → YOLO dataset
                                                                    ↓
birds-525 + iNaturalist → merge_classification_datasets.py → merged_cls
                                                                    ↓
                                              TRAINING.md (Colab) → best.pt
```

---

## 7. Платформы для публикации

| Платформа | Назначение |
|-----------|------------|
| **Hugging Face** | [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged), [birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) — см. [TRAINING](./TRAINING.ru.md) |
| **Zenodo** | DOI для статей, снапшоты |

---

См. также: [TRAINING](./TRAINING.ru.md).
