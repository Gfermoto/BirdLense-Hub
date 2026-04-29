# ML roadmap — что сделано в репозитории и что делаете вы

[English](./ML_OPERATOR_HANDOFF.md)

Эта страница фиксирует **завершение репозиторной части** Phase‑1 по ML ([CV_ML_ROADMAP_PHASES.ru.md](./CV_ML_ROADMAP_PHASES.ru.md)). Обучение по-прежнему **вне Hub** (Colab, свой GPU, Runpod) — так и задумано.

---

## Уже есть в коде (ветка `ML`)

- Стек инференса, контракт весов, бенчмарки, CI, документация.
- Скрипты сборки датасета детектора на **три класса** — см. [DATASETS.ru.md](./DATASETS.ru.md).
- Офлайн цепочка Re-ID/DINO: [`embed_dinov2_crop.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_dinov2_crop.py), [`embed_cosine_report.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_cosine_report.py), [`export_crops_from_sqlite.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/export_crops_from_sqlite.py), см. [`README`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/README.md) — вне Docker ([#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383)).

Это **не заменяет** ваши данные, разметку и время на GPU.

---

## Только вы

| Шаг | Где |
|-----|-----|
| Отбор кропов / экспорт из Hub | Library, `scripts/datasets/` |
| Обучение **классификатора** | [TRAINING.ru.md](./TRAINING.ru.md) (Colab) |
| Обучение **детектора** | [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md) |
| Проверка перед выкладкой | `make validate-weights`, [TRAINING.ru.md](./TRAINING.ru.md) |
| Деплой кода | `make deploy`, когда перейдёте с `dev` на проверенный образ |

### Когда будут новые веса (3-класс детектор + грызун в классификаторе)

1. Положить `best.pt` бинарника и классификатора в дерево `app/processor/models/…` или подставить пути в `user_config.yaml`.
2. Для трёх классов: имена классов в модели согласованы с `processor.detector_scope` и при необходимости `processor.detector_weight_contract: enforce` ([DATASETS.ru.md](./DATASETS.ru.md), [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)).
3. `make validate-weights` и смоук на хабе; затем `make deploy`.
4. Для вида «грызун» в классификаторе — обновить allowlist / `class_names.txt` после дообучения ([TRAINING.ru.md](./TRAINING.ru.md)).

Артефакты для этого пути обучения опубликованы на Hugging Face:
[gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)
(`merged_balanced` для Stage A, `merged` full для Stage B fine-tune).
Пакет весов детектора (YOLO + OpenVINO):
[weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip).

---

## Ноутбуки в репозитории

- `scripts/birds_train_cls.ipynb` — классификация.
- `scripts/birds_train.ipynb` — детекция (часто под Runpod); переносите логику в Colab по [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md).

Эпик: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367).
