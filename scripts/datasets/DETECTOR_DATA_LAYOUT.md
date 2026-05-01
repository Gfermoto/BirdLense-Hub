# Локальные данные для трёхклассового детектора (YOLO)

Используйте каталог **`scripts/datasets/binary/`** с тремя подпапками (**`birds`**, **`rodent`**, **`background`**). Содержимое с бинарниками **не коммитится** (корневой `.gitignore`).

## Структура

```
binary/
  README.md          # этот коммитится (краткая шпаргалка)
  birds/
    train/images/
    train/labels/
    val/images/
    val/labels/
  rodent/
    train/...
    val/...
  background/
    train/...
    val/...
  merged/            # только после make dataset-merge-three-class — слитый датасет
```

Формат строк в `labels/*.txt`: YOLO (`class xc yc w h`). У фона допускаются **пустые** файлы.

## Смысл классов до слияния

| Подпапка      | Типичный источник (bootstrap) | Один логический класс в labels |
|---------------|-------------------------------|--------------------------------|
| `birds/`      | COCO 2017, только `bird`      | id `0`                         |
| `rodent/`     | Open Images V6, `Squirrel`    | id `0` → после merge = Rodent |
| `background/` | COCO без детекции `bird`    | пустые `.txt`                  |

## Сборка `dataset.yaml` для Hub

Из **корня репозитория**:

```bash
make dataset-merge-three-class
```

Выход: **`scripts/datasets/binary/merged/`** с классами **Bird / Rodent / Background**. Обучение: [docs/ML_DETECTOR_COLAB.md](../../docs/ML_DETECTOR_COLAB.md).

## Каталог `brg/` и ZIP для Drive

**`scripts/datasets/brg/`** — не отдельная «магическая» стадия Makefile: это обычно **снимок того же YOLO-дерева**, который вы отдаёте в Colab/Drive. Типично: после merge в `binary/merged/` делаете импорты/dedupe и **копируете** результат в `brg/`, либо один раз вызываете `merge_datasets_three_class.py` с `--output-dir brg` вместо путей Makefile.

Упаковка: `python3 scripts/datasets/pack_brg_for_gdrive.py` → **`datasets/BirdLense_detector_brg_<UTC>.zip`** в корне репозитория (`datasets/` в `.gitignore`). Имена архивов на [Hugging Face BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector) другие — не смешивать с локальным шаблоном имени.

## Автозаполнение из интернета

```bash
cd scripts/datasets
python3 bootstrap_detector_yolo.py
```

См. также [binary/README.md](./binary/README.md).

## Раньше были плоские имена (`birds_binary_yolo/` …)

Скрипт слияния по-прежнему принимает любые `--birds-dir` / `--rodent-dir` / `--background-dir`. Старые каталоги можно переименовать в `binary/birds` и т.д. или указать явные пути при вызове `merge_datasets_three_class.py`.
