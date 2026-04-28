# ML roadmap — что сделано в репозитории и что делаете вы

[English](./ML_OPERATOR_HANDOFF.md)

Эта страница фиксирует **завершение репозиторной части** Phase‑1 по ML ([CV_ML_ROADMAP_PHASES.ru.md](./CV_ML_ROADMAP_PHASES.ru.md)). Обучение по-прежнему **вне Hub** (Colab, свой GPU, Runpod) — так и задумано.

---

## Уже есть в коде (ветка `ML`)

- Стек инференса, контракт весов, бенчмарки, CI, документация.
- Скрипты сборки датасета детектора на **три класса** — см. [DATASETS.ru.md](./DATASETS.ru.md).
- Офлайн CLI эмбеддингов **DINOv2** по кропам и отчёт cosine: [`embed_dinov2_crop.py`](../scripts/reid/embed_dinov2_crop.py), [`embed_cosine_report.py`](../scripts/reid/embed_cosine_report.py), см. [`README`](../scripts/reid/README.md) — вне Docker ([#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383)).

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

---

## Ноутбуки в репозитории

- `scripts/birds_train_cls.ipynb` — классификация.
- `scripts/birds_train.ipynb` — детекция (часто под Runpod); переносите логику в Colab по [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md).

Эпик: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367).
