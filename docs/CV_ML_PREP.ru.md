# Контракт подготовки CV / ML

[English](./CV_ML_PREP.md)

Эта страница фиксирует подготовительный контракт для
[issue #377](https://github.com/Gfermoto/BirdLense-Hub/issues/377) перед
стартом большого эпика CV / ML roadmap ([#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)).

Scope узкий: зафиксировать границу детектор/классификатор, будущую границу
инференс-бэкенда, правила воспроизводимости данных и процесс снятия блокировки
с эпика. OpenVINO/ONNX Runtime, обучение новых весов и рефакторинг процессора
здесь не реализуются.

Порядок внедрения после подготовки: [CV_ML_ROADMAP_PHASES.ru.md](CV_ML_ROADMAP_PHASES.ru.md).

---

## 1. Контракт классов детектора

Runtime сейчас использует двухэтапный пайплайн:

```text
YOLO detector -> scoped target boxes -> species classifier -> fusion
```

Метки первого этапа нормализуются в
`TwoStageStrategy._normalize_detector_label`:

| Семейство сырой метки детектора | Каноническая runtime-метка |
|---------------------------------|-----------------------------|
| `bird`, `avian`, варианты регистра/underscore/hyphen | `Bird` |
| `squirrel`, `chipmunk`, `rodent`, `грызун`, варианты регистра/underscore/hyphen | `Rodent` |
| `background`, точный плановый третий класс для hard negatives | `Background` |
| любое другое имя класса | нормализованная title-case метка, всё равно вне default scope |

Дефолтный runtime-scope первого этапа:

```yaml
processor:
  detector_scope: ["Bird", "Rodent"]
```

Только валидные боксы, чья нормализованная метка входит в
`processor.detector_scope`, попадают во второй этап — классификатор видов.
Класс детектора вроде `background`, `negative`, `empty` или другой hard-negative
должен оставаться вне `detector_scope`; такие боксы отбрасываются до crop
classification и не должны создавать кандидатов видов.

Для планового трёхклассового детектора канонические имена классов YOLO
`dataset.yaml` / `model.names` такие:

```yaml
names:
  0: Bird
  1: Rodent
  2: Background
```

`Background` — канонический третий класс для detector hard negatives. Другие
сырые имена hard-negative вроде `negative` или `empty` тоже нормализуются вне
default scope, но не удовлетворяют каноническому трёхклассовому rollout
контракту, если отклонение не описано явно в rollout notes.

Для новых весов детектора validation contract такой:

1. Хотя бы один класс должен нормализоваться в `Bird`.
2. Хотя бы один класс должен нормализоваться в `Rodent`, если rollout ожидает
   распознавание грызунов.
3. Любой background / hard-negative класс должен нормализоваться в метку вне
   настроенного `processor.detector_scope`.
4. Маппинг имён классов нужно фиксировать в rollout notes вместе с точным
   `processor.detector_scope`, применённым в production.

Fail-fast проверка загруженных весов относится к первому implementation issue
эпика: при загрузке модели сравнить `model.names` после нормализации с
ожидаемым трёхклассовым контрактом и настроенным scope, упасть с понятной
ошибкой при отсутствии целевого класса и упасть, если `Background` или другой
hard-negative класс случайно включён в scope.

---

## 2. Граница inference backend

Текущая точка входа:

- `app/processor/src/detection_stack.py` читает конфиг и создаёт
  `TwoStageStrategy`;
- `TwoStageStrategy` в `app/processor/src/detection_strategy.py` напрямую
  вызывает Ultralytics YOLO для detector tracking и classifier inference;
- `FrameProcessor` потребляет результат `DetectionStrategy.detect(...)` и не
  должен знать, какой inference backend используется: Torch, OpenVINO или ONNX
  Runtime.

Будущую backend abstraction нужно вставлять ниже `detection_stack.py` и внутри
strategy layer, а не размазывать по `FrameProcessor`. Стабильная граница:

```text
detection_stack factory
  -> strategy constructor
    -> detector backend: frame -> tracked boxes with class name, confidence, bbox
    -> classifier backend: crop -> top label / confidence or probability vector
```

Черновые имена конфига, резервируемые для эпика:

| Ключ / env overlay | Назначение | Начальное значение |
|--------------------|------------|--------------------|
| `processor.inference_backend` / `BIRDLENSE_INFERENCE_BACKEND` | выбор backend | `torch` (также `openvino` для IR бинарника) |
| `processor.inference_device` / `BIRDLENSE_INFERENCE_DEVICE` | device hint (`cpu`, `cuda`, `auto`, `openvino:CPU`) | `auto` |
| `processor.inference_precision` / `BIRDLENSE_INFERENCE_PRECISION` | precision hint (`fp32`, `fp16`, `int8`, `auto`) | `auto` |
| `processor.models.binary` | путь к Torch `.pt` бинарного детектора | существующий путь |
| `processor.models.binary_openvino` | каталог или `.xml` OpenVINO при backend `openvino` | пусто, пока не задано |
| `processor.models.classifier` | текущий путь классификатора; остаётся главным для Torch `.pt` | существующий путь |

Не переименовывать существующие `processor.models.binary` и
`processor.models.classifier` в рамках OpenVINO-работы. Если появятся
конвертированные артефакты, добавлять backend-specific опциональные ключи под
`processor.models.*`, сохранив текущие ключи как Torch default.

---

## 3. Данные и воспроизводимость

Train-ready export path в `docs/DATASETS.md` — канонический baseline для Phase 1:

- использовать `ready_for_train=1` для автоматического `train/val` split;
- использовать `strict_quality=1` для rollout-кандидатов;
- держать `split_seed` фиксированным для повторяемости;
- хранить `dataset_info.json` и `classes.txt` рядом с обученными весами;
- отклонять rollout evidence с дубликатами `(video_id, track_id)` или
  cross-split leakage по `video_id`.

Минимальный размер класса задаёт `min_images_per_class`. Для формальных
rollout-кандидатов классы ниже минимума исключаются, а с `strict_quality=1`
экспорт падает вместо тихой сборки слабых классов.

Hard negatives для детектора нужно вести через manifest, а не смешивать с
папками species-class. Manifest должен следовать паттерну `dataset_info.json`:
schema/version, source path, class label, split, source video или collection id
при наличии, fingerprint/hash для аудита. Background / hard-negative метки
детектора — только detector evidence и не должны попадать в classifier
`classes.txt`.

---

## 4. Гигиена legacy config

Production runtime поддерживает только `two_stage`. Если в `user_config.yaml`
остались `processor.detection_strategy: single_stage` или старые single-stage
пути моделей, `detection_stack.py` пишет warning, что значение игнорируется, и
собирает two-stage stack.

Рекомендуемая чистка перед стартом эпика:

1. Удалить `processor.detection_strategy: single_stage` из локального
   `user_config.yaml`.
2. Не тюнить `processor.models.single_stage`; это compatibility artifact, не
   production runtime input.
3. Держать `processor.detector_scope` явным при тестировании новых весов
   детектора, чтобы rollout notes могли воспроизвести точный scope первого
   этапа.

---

## 5. Снятие блокировки с эпика

После выполнения и merge acceptance checklist из issue #377:

1. Закрыть issue #377.
2. Снять с epic #367 метку `epic:blocked`.
3. На Roadmap board перевести epic #367 из Backlog в Ready или In progress, если
   реализация стартует сразу.
4. Оставить короткий комментарий в #367: `Prep completed in #377`.

Эпик остаётся заблокированным, пока эта страница, `docs/DATASETS.md` и
`docs/CONFIGURATION.md` не согласованы по контракту detector/classifier и
legacy-конфигу.
