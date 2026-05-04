# Классификатор: приоритет европейских птиц

## Принцип

- **Максимум охвата европейских видов**, баланс за счёт **добавления** данных (iNat EU, готовый EU-merge на HF), а не выкидывания классов.
- Скрипт **`balance_classifier_yolo_cls.py`** с жёстким `--min-images` / `--max-ratio` **не использовать** для этой цели — он специально режет редкие виды ради ровного лосса.

## Базовый слой (рекомендуется)

Готовый мерж ~490 классов, формат `Scientific (Common)`:

```bash
python3 scripts/datasets/download_birds_eu_merged.py \
  --output datasets/new/classifier/yolo_cls_eu_hf
```

Источник: [`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged) (BirdLense Hub).

## Добавить объём (EU, research-grade)

Увеличить `--max-obs` (десятки тысяч наблюдений — долго, уважать rate limit API):

```bash
python3 scripts/datasets/download_inaturalist.py \
  --output datasets/new/classifier/raw/inat_europe_bulk \
  --max-obs 40000 \
  --photo-size medium
```

`download_inaturalist.py` уже фильтрует **Europe** (`place_id=96372`) и **Aves**.

## Слить без дублирования файлов

```bash
python3 scripts/datasets/merge_classification_datasets.py \
  --inputs datasets/new/classifier/yolo_cls_eu_hf \
           datasets/new/classifier/raw/inat_europe_bulk \
  --output datasets/new/classifier/yolo_cls_eu_merged \
  --symlink \
  --val-ratio 0.2
```

Дальше — утечки и имена (без жёсткого «баланс-реза»):

```bash
python3 scripts/datasets/refine_classifier_yolo_cls.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --cache-dir datasets/new/classifier/.cache \
  --dedupe --normalize --test-split

python3 scripts/datasets/refine_classifier_yolo_cls.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --dedupe-global-only --skip-rebalance
```

При необходимости добавить третий вход (другой открытый датасет) тем же `merge_classification_datasets.py`.

## Обучение при дисбалансе классов

Не резать классы: **веса классов / focal loss / subsampling батча** в конфиге Ultralytics (отдельная настройка тренировки, не датасетный «кромсатель»).

## Примечание по составу EU-merge на HF

В архив могут попадать отдельные виды из глобального birds-525 вне Европы; основная масса — EU + совместимые метки. Ужесточение «только Европа» — отдельным таксономическим фильтром по списку видов (BirdLife / ручной allowlist), если понадобится.
