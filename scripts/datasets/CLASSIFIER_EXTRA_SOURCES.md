# Добор размеченных данных для классификатора (редкие классы)

Если по виду мало кадров после HF EU-merge, **добавляйте** данные из открытых источников и снова `merge_classification_datasets.py` → `refine_classifier_yolo_cls.py`. Имена сведёт `--normalize` к **`Scientific_(Common)`**.

Автоматизированный добор по списку редких классов: **`backfill_classifier_open.py`** (iNaturalist). Дальше staging вторым/третьим `--inputs` у merge.

---

## 1. Уже в репозитории (скрипты)

| Источник | Скрипт | Заметки |
|----------|--------|---------|
| EU-merge на HF | `download_birds_eu_merged.py` | База ~491 класса |
| iNaturalist **Europe**, research-grade | `download_inaturalist.py` | Увеличить `--max-obs`; опционально `--taxon-id`, `--no-place-filter` для точечного добора вида |
| Birds-525 (Kaggle→HF) | `download_hf_birds.py --format scientific_common` | Пересечение с EU по видам; другой `--dataset`, если зеркало на HF |

Примеры:

```bash
# Массовый добор EU
python3 scripts/datasets/download_inaturalist.py \
  --output datasets/new/classifier/raw/inat_europe_bulk \
  --max-obs 60000 --photo-size medium

# Один вид (taxon_id со страницы вида на inaturalist.org) — глобально, если в Европе мало снимков
python3 scripts/datasets/download_inaturalist.py \
  --output datasets/new/classifier/raw/inat_taxon_12345 \
  --taxon-id 12345 --no-place-filter --max-obs 800 --photo-size medium

# Дополнительный слой birds-525 в том же формате имён
python3 scripts/datasets/download_hf_birds.py \
  --dataset 34data/birds-525-species \
  --output datasets/new/classifier/raw/birds525_hf \
  --format scientific_common
```

Другие зеркала того же семейства датасетов на Hugging Face (проверьте актуальный `repo_id` и лицензию): например зеркала вроде `yashikota/birds-525-species-image-classification` — если структура совместима с `datasets.load_dataset`, можно добавить поддержку в `download_hf_birds.py` или выгрузить вручную и привести к `train/<class>/`.

---

## 2. Крупные открытые коллекции (вне репо)

- **BirdCLEF / LifeCLEF** (Kaggle): очень много видов и метаданных; часто акцент на **аудио**, но бывают наборы с изображениями или мультимодальные задачи — смотреть конкретный год соревнования и условия использования.
- **CUB-200-2011**: 200 видов, сильные боксы/атрибуты; пересечение с EU частичное, но полезно для «общих» видов и как эталон качества разметки.
- **NABirds**: Северная Америка; иерархия видов; в репо уже есть конвертеры под детекцию — для cls нужна отдельная выгрузка в плоский `train/class/`.
- **Macaulay Library** (Cornell): высокое качество медиа по видам; доступ через их API/политики — не всегда массовая загрузка под ML без соглашения.
- **GBIF / Observation.org**: огромные объёмы; разметка и качество снимков неоднородны, нужны фильтры по лицензии и таксону — разумны как вторичный источник после iNat.

---

## 3. Рабочий порядок

1. **`report_classifier_class_counts.py`** — кто ниже порога.
2. **`backfill_classifier_open.py`** — массовый точечный добор с iNat в staging **или** отдельные вызовы **`download_inaturalist.py --taxon-id`** / слой birds-525.
3. **`merge_classification_datasets.py --inputs …`** — добавить staging очередным входом (без урезания уже имеющихся классов).
4. **`refine_classifier_yolo_cls.py`** (`--dedupe --normalize --test-split`, затем `--dedupe-global-only`).

Ручные подборки возможны; iNat обычно быстрее для однотипных фото птицы.
