# Источники датасетов и платформы для сообщества

Датасеты птиц, похожие на NABirds, и платформы для размещения данных от участников BirdLense Hub (Hugging Face, Zenodo).

---

## 1. Датасеты птиц (аналоги NABirds)

### На Hugging Face

| Датасет | Видов | Изображений | Особенности |
|---------|-------|-------------|-------------|
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 | ~50k | Северная Америка, bbox, part labels (клюв, крылья) |
| [chriamue/bird-species-dataset](https://huggingface.co/datasets/chriamue/bird-species-dataset) | — | — | Классификация видов |
| [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species) | 525 | ~90k | Kaggle, 224×224 JPG |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 | ~12k | CUB-200-2011, bbox, атрибуты |
| [cassiekang/cub200_dataset](https://huggingface.co/datasets/cassiekang/cub200_dataset) | 200 | ~12k | CUB + текстовые описания |

### Классические (вне HF)

| Датасет | Видов | Описание |
|---------|-------|----------|
| **NABirds** | 400 (700 категорий) | [dl.allaboutbirds.org](https://dl.allaboutbirds.org/nabirds), Cornell Lab, citizen science |
| **CUB-200-2011** | 200 | [Caltech](https://www.vision.caltech.edu/datasets/cub_200_2011/), 15 part markers, 312 атрибутов |
| **iNaturalist** | Тысячи | [inaturalist.org](https://www.inaturalist.org) — API, фильтр `iconic_taxa[]=Aves` |

### Загрузка с Hugging Face

```python
from datasets import load_dataset
ds = load_dataset("sasha/birdsnap", split="train")
# или
ds = load_dataset("randall-lab/cub200", split="train", trust_remote_code=True)
```

---

## 2. Hugging Face для сообщества BirdLense Hub

### Плюсы
- Бесплатно для публичных датасетов
- Версионирование (git)
- `datasets` — удобная загрузка
- Поиск по тегам (birds, object-detection, yolo)
- Dataset card (README) — описание, лицензия, цитирование

### Структура для YOLO
```
birdlense-community/
  train/images/
  train/labels/
  val/images/
  val/labels/
  data.yaml
  README.md  # Dataset card
```

### Загрузка
- **Web:** drag-and-drop в Files and versions
- **CLI:** `huggingface-cli upload org/birdlense-detections ./export/`
- **Python:** `huggingface_hub.upload_file()`

### Пример организации
- Репозиторий: `birdlense/community-detections` или `Gfermoto/birdlense-labeled`
- Версии: v1, v2 при накоплении данных
- Лицензия: CC BY 4.0 (для науки)

---

## 3. Zenodo для сообщества BirdLense Hub

### Плюсы
- **DOI** — цитирование в статьях
- Исследовательская платформа (EU, CERN)
- До 50 GB, до 100 файлов
- Бесплатно
- Версии с новым DOI (v1, v2)

### Ограничения
- После публикации файлы нельзя менять (только новая версия)
- Меньше гибкости, чем HF

### Когда выбирать Zenodo
- Научная статья — нужен DOI для датасета
- Разовый релиз (снапшот)
- Долгосрочная сохранность

### Загрузка
- Web: [zenodo.org](https://zenodo.org) → New upload
- API: [developers.zenodo.org](https://developers.zenodo.org)

---

## 4. Сравнение для BirdLense Hub

| Критерий | Hugging Face | Zenodo |
|----------|--------------|--------|
| Итеративные обновления | ✅ Да | ❌ Только новая версия |
| DOI для цитирования | ❌ Нет | ✅ Да |
| Загрузка через API | ✅ Удобно | ✅ Есть |
| Интеграция с ML | ✅ `load_dataset()` | Ручная загрузка |
| Научная репутация | Растёт | Устоявшаяся |

### Рекомендация
- **Hugging Face** — основной репозиторий для сообщества (частые обновления, ML-интеграция)
- **Zenodo** — периодические снапшоты с DOI (раз в квартал/год, для статей)

---

## 5. Интеграция в COLLABORATIVE_LABELING

В [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) секция «Куда уходят данные»:

| Вариант | Платформа |
|---------|-----------|
| Локально | SQLite BirdLense Hub |
| Экспорт | Ручная выгрузка |
| Сообщество (итеративно) | **Hugging Face** |
| Сообщество (снапшот для статьи) | **Zenodo** |

### Workflow
1. Участники размечают локально
2. Экспорт в YOLO: `export_birdlense_to_yolo.py`
3. Загрузка на HF: `huggingface-cli upload` или скрипт
4. Для статьи: экспорт → Zenodo → DOI в Methods

---

## 6. Ссылки

**Внешние:** [Hugging Face](https://huggingface.co/datasets) · [Zenodo](https://zenodo.org) · [iNaturalist API](https://www.inaturalist.org/pages/api+recommended+practices) · [NABirds](https://dl.allaboutbirds.org/nabirds) · [CUB-200-2011](https://www.vision.caltech.edu/datasets/cub_200_2011/)

**См. также:** [COLLABORATIVE_LABELING.md](./COLLABORATIVE_LABELING.md) · [DATASET_TRAINING_PLAN.md](./DATASET_TRAINING_PLAN.md)
