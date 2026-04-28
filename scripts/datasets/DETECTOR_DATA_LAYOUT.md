# Локальные данные для трёхклассового детектора (YOLO)

Каталоги **`birds_binary_yolo/`**, **`rodent_yolo/`**, **`background_yolo/`** создаются рядом со скриптами (`scripts/datasets/`) и **не коммитятся** (см. корневой `.gitignore`): там лежат изображения и `.txt` разметки.

## Структура (одинаковая для каждого источника)

```
<имя>/
  train/
    images/    # *.jpg / *.png …
    labels/    # для каждого изображения stem.txt (YOLO: class xc yc w h); фон — пустой файл
  val/
    images/
    labels/
```

## Смысл классов до слияния

| Каталог              | Источник (bootstrap по умолчанию) | Один логический класс в labels |
|----------------------|-----------------------------------|--------------------------------|
| `birds_binary_yolo`  | MS COCO 2017, только `bird`       | id `0`                         |
| `rodent_yolo`        | Open Images V6, `Squirrel`        | id `0` (позже merge → Rodent) |
| `background_yolo`    | COCO без детекции `bird`          | пустые `.txt`                  |

## Сборка датасета для Hub

Из **корня репозитория**:

```bash
make dataset-merge-three-class
```

На выходе: `scripts/datasets/birds_rodent_background_yolo/` с `dataset.yaml` (**Bird** / **Rodent** / **Background**). Обучение — [docs/ML_DETECTOR_COLAB.md](../../docs/ML_DETECTOR_COLAB.md).

## Автозаполнение из интернета

```bash
cd scripts/datasets
python3 -m venv .venv-detector && . .venv-detector/bin/activate
pip install fiftyone pyyaml
python3 bootstrap_detector_yolo.py
```

Параметры лимитов см. `python3 bootstrap_detector_yolo.py --help`. Для пробного прогона уменьшите `--birds-train`, `--rodent-train` и т.д.

Дополнительно можно заполнить **`rodent_yolo`** вручную из выгрузки Open Images Toolkit ([convert_oidv4_rodent_to_yolo.py](./convert_oidv4_rodent_to_yolo.py)) — классы Mouse/Rat можно слить в один Rodent отдельным скриптом при необходимости.
