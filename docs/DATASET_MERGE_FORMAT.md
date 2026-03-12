# Формат имён видов при слиянии датасетов

Единый формат **`Scientific_name (Common Name)`** используется для слияния датасетов, Frigate, BirdNET и YOLO.

---

## Зачем

| Источник | Исходный формат | После приведения |
|----------|-----------------|------------------|
| **Frigate** | `Cardinalis cardinalis (Northern Cardinal)` | уже в формате |
| **BirdNET** | `Northern Cardinal`, `Вяхирь` | common name (маппинг в merge) |
| **iNaturalist** | `Columba palumbus` | `Columba palumbus (Common Wood Pigeon)` |
| **birds-525** | `GOLDEN_EAGLE` | `Aquila chrysaetos (Golden Eagle)` |
| **NABirds** | `Northern Cardinal` | не переучиваем |

Совпадение формата с Frigate упрощает слияние детекций (YOLO + Frigate + BirdNET).

---

## Скрипты

### 1. Загрузка с преобразованием

```bash
# birds-525 → Scientific (Common) через маппинг inat_bird_labels.txt
python scripts/datasets/download_hf_birds.py \
  --dataset 34data/birds-525-species \
  --output datasets/birds_525_cls \
  --format scientific_common

# iNaturalist → Scientific (Common) из API (taxon.name + preferred_common_name)
python scripts/datasets/download_inaturalist.py \
  --output datasets/inaturalist_europe_cls \
  --max-obs 2000
```

### 2. Объединение

```bash
python scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/birds_525_cls datasets/inaturalist_europe_cls \
  --output datasets/merged_cls \
  --val-ratio 0.2
```

Имена папок сохраняются как есть (`Scientific (Common)`), если уже в формате.

### 3. Полный пайплайн

```bash
./scripts/datasets/download_and_merge_all.sh
```

---

## Утилиты

`scripts/datasets/species_format.py`:

- `format_scientific_common(scientific, common)` — собрать строку
- `parse_scientific_common(s)` — разобрать `(scientific, common)`
- `extract_common_for_lookup(s)` — извлечь common для поиска в иерархии
- `load_inat_mapping()` — маппинг common → Scientific (Common) из [inat_bird_labels.txt](https://raw.githubusercontent.com/google-coral/test_data/master/inat_bird_labels.txt)

---

## Иерархия и слияние детекций

### Иерархия (`hierarchy_names.txt`)

При создании нового вида (Frigate, BirdNET, новый YOLO) родитель ищется по **common name**:

- `Cardinalis cardinalis (Northern Cardinal)` → извлечь `Northern Cardinal` → родитель `Cardinals, Grosbeaks, and Allies`

Функция `get_parent_name_for_species()` в `app/web/util.py`.

### Слияние детекций (`merge_detections`)

Сравнение по **canonical key** (common name в lower):

- `Northern Cardinal` (BirdNET) и `Cardinalis cardinalis (Northern Cardinal)` (Frigate) → один вид, объединение confidence

---

## Ограничения

- **birds-525**: маппинг из inat_bird_labels (~966 видов). Виды вне списка остаются как есть.
- **iNaturalist**: `preferred_common_name` может отсутствовать — используется scientific.
- **BirdNET**: локализованные имена (`Вяхирь`) — нужен маппинг в `species_mapping` для отображения.

---

См. также: [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md), [DATASET_SCRIPTS.md](./DATASET_SCRIPTS.md).
