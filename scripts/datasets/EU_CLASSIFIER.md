# Классификатор: приоритет европейских птиц

## Принцип

- **Максимум охвата** (~491 класс EU-merge), **ровнее распределение только за счёт добора** открытых размеченных данных (iNaturalist research-grade, HF birds-525-слой и т.д.), **не за счёт выкидывания** изображений из «жирных» классов.
- **`balance_classifier_yolo_cls.py`** — опциональное **урезание** (subsampling); для политики «баланс через добор» **не используйте** его как основной инструмент.

## Базовый слой (рекомендуется)

Готовый мерж ~490 классов, формат `Scientific (Common)`:

```bash
python3 scripts/datasets/download_birds_eu_merged.py \
  --output datasets/new/classifier/yolo_cls_eu_hf
```

Источник: [`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (BirdLense Hub).

## Массовый добор (EU)

```bash
python3 scripts/datasets/download_inaturalist.py \
  --output datasets/new/classifier/raw/inat_europe_bulk \
  --max-obs 60000 \
  --photo-size medium
```

`download_inaturalist.py` по умолчанию: **Europe** (`place_id=96372`), **Aves**, research-grade.

## Точечный добор редких классов (iNat, без урезания)

После первого merge + refine посмотреть «дыры»:

```bash
python3 scripts/datasets/report_classifier_class_counts.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --below 80 \
  --csv datasets/new/classifier/rare_before.csv
```

Собрать слой только добора (поднимает классы до `--target`, обращаясь к API по виду):

```bash
python3 scripts/datasets/backfill_classifier_open.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --staging datasets/new/classifier/raw/inat_backfill \
  --target 120 \
  --place-mode global \
  --report-json datasets/new/classifier/backfill_report.json

# проверка без скачивания:
# ... --dry-run
```

`--place-mode europe` — только Европа; `global` — больше наблюдений для очень редких видов.

Дополнительные открытые источники и ручной добор: **[CLASSIFIER_EXTRA_SOURCES.md](./CLASSIFIER_EXTRA_SOURCES.md)**.

## Слить слои

Каждый новый сырой каталог — ещё один `--inputs`:

```bash
python3 scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/new/classifier/yolo_cls_eu_hf \
           datasets/new/classifier/raw/inat_europe_bulk \
           datasets/new/classifier/raw/inat_backfill \
  --output datasets/new/classifier/yolo_cls_eu_merged \
  --val-ratio 0.2
```

После изменения состава inputs выходную папку лучше брать **новым именем** (`..._merged_v2`), чтобы не перепутать кэши.

## Имена и качество разметки

Утечки между сплитами и **`Scientific_(Common)`** как в Hub:

```bash
python3 scripts/datasets/refine_classifier_yolo_cls.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --cache-dir datasets/new/classifier/.cache \
  --dedupe --normalize --test-split

python3 scripts/datasets/refine_classifier_yolo_cls.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --dedupe-global-only --skip-rebalance
```

Цикл «мало фото → backfill staging → merge (+ новый input) → refine» можно повторять, пока счётчики не устраивают.

### Полировка (добор слоя к уже готовому merged)

Скрипт **`scripts/datasets/polish_eu_classifier.sh`**: бэкап `yolo_cls_eu_merged` → timestamped `*_prev_*`, merge с `--restrict-to-primary-input` (новые классы не появляются), полный refine. Пример после окончания `download_inaturalist.py` в `raw/inat_europe_bulk`:

```bash
EXTRA="datasets/new/classifier/raw/inat_europe_bulk" \\
  bash scripts/datasets/polish_eu_classifier.sh datasets/new/classifier
```

`merge_classification_datasets.py` сохраняет **`test/`**, если он есть у входов.

## Обучение при остаточном дисбалансе

На этапе обучения всё ещё полезны **веса классов / focal / семплинг батча** в Ultralytics — это не замена добору, а дополнение.

## Примечание по составу EU-merge на HF

В архив могут попадать отдельные виды из глобального birds-525 вне Европы; основная масса — EU + совместимые метки. Ужесточение «только Европа» — отдельным таксономическим фильтром по списку видов, если понадобится.
