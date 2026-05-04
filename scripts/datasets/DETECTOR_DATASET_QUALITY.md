# Детектор Bird / Rodent / Background — сборка «не говно»

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

## Дальше

- Обучение: `docs/ML_DETECTOR_COLAB.md` (или свой пайплайн).
- Экспорт OpenVINO и сравнение с baseline — см. ML-гейты в `Makefile`.
