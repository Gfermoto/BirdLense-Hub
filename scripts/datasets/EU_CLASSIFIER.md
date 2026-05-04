# Классификатор: приоритет европейских птиц

## Принцип

- **Максимум охвата европейских видов**, баланс за счёт **добавления** данных (iNat EU, готовый EU-merge на HF), а не выкидывания классов.
- **`balance_classifier_yolo_cls.py`** с дефолтами `--min-images 40` и узким `--max-ratio` режет много видов — так **не** добиваются ~491 класса. Для баланса при почти полном охвате см. раздел **«Баланс при полном охвате»** ниже.

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

## Баланс при полном охвате (~491 класс)

Имена остаются в **`Scientific_(Common)`** (папки), если перед балансом выполнен **`refine_classifier_yolo_cls.py --normalize`** — как в прежнем пайплайне.

Порядок:

1. HF (+ опционально iNat) → `merge_classification_datasets.py` → **`refine ... --dedupe --normalize --test-split`**
2. **`balance_classifier_yolo_cls.py`** — подрезает только «толстые» классы относительно типичного минимума; редкие классы с малым числом кадров сохраняются целиком до потолка:
   - **`--min-images 12`** — отсечь только совсем пустые/сломанные классы (подберите 8–20 под ваш merge; чем меньше, тем ближе к 491).
   - **`--max-ratio 6`** — верхняя граница ≈ в 6 раз выше базы `m` (при необходимости 5–10).
   - **`--anchor-percentile 5`** — база `m = max(min_count, P5 по классам)`, чтобы один класс с 1–2 фото не задавал жёсткий потолок всем остальным.

Пример:

```bash
python3 scripts/datasets/balance_classifier_yolo_cls.py \
  --root datasets/new/classifier/yolo_cls_eu_merged \
  --min-images 12 --max-ratio 6 --anchor-percentile 5 --seed 42 \
  --report-json datasets/new/classifier/balance_report.json
```

3. Затем снова убрать дубликаты по файлам: **`refine_classifier_yolo_cls.py --dedupe-global-only --skip-rebalance`** (или без `--skip-rebalance`, если хотите пересобрать train/val пропорции).

Включить этот шаг из скрипта: **`CLASSIFIER_BALANCE=1 bash scripts/datasets/build_eu_classifier_yolo.sh ...`**

Качество: до баланса имеет смысл **добавить iNat EU** (research-grade, больший `--max-obs`), чтобы поднять пол у редких видов — тогда балансировка меньше режет полезные данные.

## Обучение при дисбалансе классов

Даже после баланса полезны **веса классов / focal / семплинг** в Ultralytics. Датасетный баланс и loss-трюки не исключают друг друга.

## Примечание по составу EU-merge на HF

В архив могут попадать отдельные виды из глобального birds-525 вне Европы; основная масса — EU + совместимые метки. Ужесточение «только Европа» — отдельным таксономическим фильтром по списку видов (BirdLife / ручной allowlist), если понадобится.
