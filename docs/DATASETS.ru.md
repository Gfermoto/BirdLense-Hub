# Датасеты и модели BirdLense

[English](./DATASETS.md)

---

Справочник: форматы, скрипты, источники, оборудование. **Обучение:** [TRAINING](./TRAINING.ru.md).

---

## Операционный flow в Library (Hub)

Критичный happy-path для ежедневной работы оператора в `Library`:

1. **Импорт с диска** (`Сканировать и импортировать`).
2. **Регенерация** за период (`Спектрограммы` → `Треки`).
3. **Экспорт ZIP датасета** (опционально: `только вручную подтверждённые`).
4. **Обслуживание**: `retro-export` для доэкспорта и `clean dataset` для очистки.

### Период «за всё время»

В `Library` теперь есть пресет **«За всё время»**. Он не угадывает диапазон по календарю, а берёт его из реально найденных записей на диске (`storage/stats`), поэтому безопасно выбирает весь архив без ручного поиска первой даты.

Практический совет:
- начните с **последних 7 или 30 дней**, если хотите оценить скорость операции;
- используйте **«За всё время»**, когда устройство не занято активной съёмкой;
- для очень большого архива самой тяжёлой операцией обычно будет **перегенерация треков**, затем **спектрограммы**; экспорт ZIP датасета обычно легче, если crops уже подготовлены.

Формула метрики «Уникальные посетители» в `System`: количество сессий `SpeciesVisit` за выбранный период (не уникальные особи, а уникальные визит-сессии).

### Экспорт «готово к train»

В `Library -> Экспорт датасета` включите опцию **«Готово к train (авто split train/val, без пост-скрипта)»**.  
Опционально: **«Добавить test split (~10%)»** — в ZIP попадёт и `test/<class>/...` (hold-out).

ZIP будет содержать:
- `train/<class>/...`, `val/<class>/...`, при необходимости `test/<class>/...`
- `classes.txt`
- `dataset_info.json` — паспорт выгрузки (`manifest.schema=birdlense_dataset_export_v2`, фильтры, `split_seed`, `fingerprint_sha256_16`) и блок **`quality`**: дубликаты `(video_id, track_id)`, «утечка» одного `video_id` между сплитами.

API: `GET /api/ui/dataset/export` — параметры `test_ratio`, `strict_quality=1` (отменить выгрузку при дубликатах треков, утечке `video_id` между сплитами или если при **ready_for_train** есть классы ниже `min_images_per_class`).

Это убирает обязательный промежуточный запуск `scripts/datasets/export_birdlense_to_yolo.py` для базового сценария дообучения.

---

## 1. Модели

| Компонент | Версия | Дообучено на |
|-----------|--------|--------------|
| **Детектор** | YOLO11n | NABirds + COCO birds + OIDv4 squirrel (бинарный bird/squirrel) |
| **Классификатор EU** | YOLO11n-cls | birds-525 + iNaturalist (~491 вид) — активна в `best.pt` |
| **Классификатор US** | YOLO11n-cls | NABirds (~400 видов) — резерв в `best_US.pt` |

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
| `export_birdlense_to_yolo.py` | Локальные кропы BirdLense (`app/data/dataset/train`) → YOLO cls `train/val` |
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
| `classification/weights/best.pt` | EU-классификатор (YOLO11n-cls, активна) |
| `classification/weights/best_US.pt` | Резерв US (опционально) |
| `classification/weights/class_names.txt` | Allowlist классов для привязки каталога |
| `detection/weights/best.pt` | Бинарный детектор (YOLO11n) |

Всё остальное в `app/processor/models/` — это экспорт/тренировка, а не runtime input.

---

## 4. Источники датасетов

### Для EU (приоритет)

| Датасет | Видов | Ссылка |
|---------|-------|--------|
| **[34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species)** | 525 | Hugging Face |
| **iNaturalist Europe** | Тысячи | [API](https://api.inaturalist.org/v1/docs/), `place_id=96372` |

Шипнутый детектор обучен на **NABirds + COCO birds + OIDv4 squirrel**, а шипнутый EU-классификатор — на **birds-525 + iNaturalist Europe (~490/491 видов)**.

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
BirdLense (записи) → export_birdlense_to_yolo.py → YOLO dataset
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
