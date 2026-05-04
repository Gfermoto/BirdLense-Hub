# Детектор Bird / Rodent / Background — сборка «не говно»

## Локальная структура `binary/`

Каталог **`scripts/datasets/binary/`**: подпапки **`birds/`**, **`rodent/`**, **`background/`**. Крупные файлы в `.gitignore`.

```
binary/
  birds/, rodent/, background/   # train|val/images + labels/
  merged/                         # после make dataset-merge-three-class
```

Формат `labels/*.txt`: YOLO (`class xc yc w h`); у фона допускаются **пустые** файлы.

| Подпапка | Типичный источник (bootstrap) | Один логический класс в labels до merge |
|----------|-------------------------------|----------------------------------------|
| `birds/` | COCO `bird`, опционально OID Bird | id `0` |
| `rodent/` | Open Images V6 и т.д. | id `0` → после merge = **Rodent** |
| `background/` | COCO без детекции `bird` | пустые `.txt` |

Автозаполнение: `cd scripts/datasets && python3 bootstrap_detector_yolo.py`. Старые плоские каталоги можно передать в `merge_datasets_three_class.py` через `--birds-dir` / `--rodent-dir` / `--background-dir`. Краткая шпаргалка: [binary/README.md](./binary/README.md).

---

## Проблема одного источника птиц

Только **COCO `bird`** даёт узкий домен (часто крупный план, не ваши кормушки/камеры). Для recall на реальных сценах нужен **второй домен** боксов птиц.

## Что добавлено в `bootstrap_detector_yolo.py`

| Источник | Флаг | Эффект |
|----------|------|--------|
| Open Images V6 **Bird** | `--birds-oid-train`, `--birds-oid-val` | Дополнительные изображения с боксами птицы → тот же YOLO-класс `0`, папка `binary/birds/`. |
| OID без огромного train CSV | `--birds-oid-validation-only` | Все OID-птицы из сплита `validation`; квоты `--birds-oid-train` / `--birds-oid-val` раскладываются по папкам `train`/`val` (как у грызунов). |
| Hard-negative фон | `--background-hard-train`, `--background-hard-val` | COCO: есть **person** / **dog** / **cat**, **нет** `bird`, метки **пустые** → класс фона; учит «не поднимать птицу» на людей и питомцев. |
| Состав триггеров | `--background-hard-labels` | По умолчанию `person,dog,cat`. |

Обычный фон (`--background-*`) по-прежнему: случайные COCO-кадры **без** птицы.

## Рекомендуемые порядки величин (старт полноценного датасета)

Не жёсткий стандарт — зависит от диска и времени. Ориентир:

| Ветка | train | val | Комментарий |
|-------|-------|-----|-------------|
| COCO bird | 2 000–4 000 | 500–900 | База |
| OID Bird | 0 или 2 000+ | 500–2 500 | Если train OID тяжёл — только `--birds-oid-validation-only` и большая `--birds-oid-val` |
| Rodent (OID) | 3 000–6 000 | 700–1 500 | Полный train OID, если тянет машина; иначе validation-only |
| Фон «простой» | 4 000–8 000 | 1 000–2 000 | Без птицы |
| Фон hard | 1 500–3 000 | 400–800 | Люди/кошки/собаки, без птицы |

После заполнения всегда из корня репозитория:

```bash
make dataset-merge-three-class
```

Проверка разметки (пример):

```bash
make dataset-validate-yolo-labels LABELS_DIR=scripts/datasets/binary/merged/train/labels CLASS_COUNT=3
```

## Готовый пример ARGS

См. комментарий в начале `bootstrap_detector_yolo.py` (блок с `--birds-oid-val 2500` и `--background-hard-*`).

Или скрипт:

```bash
bash scripts/datasets/build_detector_dataset_large.sh
```

(редактируй числа под свой диск).

## Волны (меньше пиков памяти и сети)

Один скрипт дробит те же итоговые квоты на микроволны и делает паузу между ними:

```bash
bash scripts/datasets/build_detector_dataset_waves.sh
WAVE_PAUSE=15 CHUNK_SIZE=30 bash scripts/datasets/build_detector_dataset_waves.sh
RUN_MERGE=1 bash scripts/datasets/build_detector_dataset_waves.sh   # в конце merge
```

Точечные флаги bootstrap (для своих сценариев): `--skip-birds-coco`, `--skip-birds-oid`, `--skip-background-soft`, `--skip-background-hard`.

## Дальше

- Обучение: `docs/ML_DETECTOR_COLAB.md` (или свой пайплайн).
- Экспорт OpenVINO и сравнение с baseline — см. ML-гейты в `Makefile`.
