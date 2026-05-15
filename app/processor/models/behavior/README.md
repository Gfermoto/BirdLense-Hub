# Веса baseline поведения (`behavior_logistic_export@v1`)

## Что уже лежит в этом каталоге

Файл **`behavior_logistic_export@v1.json`** — это **реально обученная** логистическая регрессия (sklearn), но на **синтетическом** манифесте из репозитория (`scripts/fixtures/behavior/synthetic_train_manifest.v1.json`). Она **не привязана к вашим камерам** и годится, чтобы проверить, что процессор грузит JSON и пишет метки; для продакшена замените файл после обучения на своих разметках.

Рядом каталог **`behavior_logistic_openvino/`** с **`behavior_logistic.onnx`** — тот же классификатор в виде одного Gemm для **OpenVINO** (`processor.models.behavior_openvino`, см. дефолтный конфиг). При `processor.behavior_recognition.inference_backend: auto` процессор возьмёт ONNX при наличии runtime OpenVINO и корректных путей; иначе остаётся numpy по JSON. Пересборка ONNX из обновлённого JSON: **`make ml-export-behavior-onnx`** (нужен пакет `onnx`, обычно в `app/.venv`).

1. В веб-интерфейсе: **Настройки** → аккордеон **Процессор** → блок **«Распознавание поведения»** (`/settings#processor-behavior`).
2. Путь к весам оставьте **`models/behavior/behavior_logistic_export@v1.json`** (так в дефолтном конфиге).
3. Включите **«Включить baseline поведения»**, сохраните.
4. **Перезапустите контейнер/процессор** — иначе подхватится только после рестарта.

## Пересобрать демо-веса у себя (опционально)

Из корня репозитория, с установленным `scikit-learn`:

```bash
pip install 'scikit-learn>=1.3,<2'
python3 scripts/ml_behavior_train_baseline.py \
  --manifest scripts/fixtures/behavior/synthetic_train_manifest.v1.json \
  --export-out app/processor/models/behavior/behavior_logistic_export@v1.json \
  --predictions-out /tmp/behavior_predictions_synthetic.json
```

Или цель **`make ml-train-behavior-synthetic-fixture`** (см. `Makefile` рядом с `ml-train-behavior-baseline`).

## Обучение на своих разметках (настоящие данные)

Нужна папка с CSV аннотациями в формате, который читает `scripts/ml_behavior_dataset_manifest.py` (см. исходник скрипта — колонки кадра, id поведения и т.д.).

```bash
cd /путь/к/BirdLense
ANNOTATIONS_ROOT=/путь/к/разметке OUT=/tmp/behavior_dataset_manifest.v1.json make ml-build-behavior-dataset

MANIFEST=/tmp/behavior_dataset_manifest.v1.json \
EXPORT=/tmp/my_export.json \
PRED=/tmp/my_predictions.json \
  make ml-train-behavior-baseline
```

Полученный **`EXPORT`** скопируйте на хаб (например в `app/processor/models/behavior/`), в настройках укажите **относительный путь от корня `app/processor/`**, включите baseline, сохраните, перезапустите процессор.
