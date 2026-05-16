#!/usr/bin/env bash
# Картинки val COCO 2017 → кэш FiftyOne: ~/fiftyone/coco-2017/validation/data/
#
# Варианты архива:
#  - Официальный val2017.zip: внутри val2017/*.jpg
#  - Зеркало (часто лучше тянется, чем cocodataset.org):
#    curl -L -o val2017.zip https://github.com/ultralytics/yolov5/releases/download/v1.0/coco2017val.zip
#    внутри: coco/images/val2017/*.jpg
#
# Важно: в validation/ должен быть полный labels.json (20+ MiB). Иначе FiftyOne
# возьмёт урезанный манифест и увидит только ~32 кадра. Положить:
#   unzip -j ann_trainval2017.zip annotations/instances_val2017.json
#   cp instances_val2017.json ~/fiftyone/coco-2017/validation/labels.json
# (аннотации: http://images.cocodataset.org/annotations/annotations_trainval2017.zip)
set -euo pipefail
VAL_ZIP="${1:-${HOME}/fiftyone/coco-2017/tmp-download/val2017.zip}"
DEST="${HOME}/fiftyone/coco-2017/validation/data"
if [[ ! -f "$VAL_ZIP" ]]; then
  echo "Нет файла: $VAL_ZIP" >&2
  echo "См. комментарии в начале скрипта." >&2
  exit 1
fi
if [[ ! -s "$VAL_ZIP" ]]; then
  echo "Файл пустой (0 байт): $VAL_ZIP" >&2
  exit 1
fi
mkdir -p "$DEST"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
unzip -q "$VAL_ZIP" -d "$TMP"
if [[ -d "$TMP/val2017" ]]; then
  cp -f "$TMP/val2017"/*.jpg "$DEST/" || true
elif [[ -d "$TMP/coco/images/val2017" ]]; then
  cp -f "$TMP/coco/images/val2017"/*.jpg "$DEST/" || true
else
  echo "Неожиданная структура архива (ждали val2017/ или coco/images/val2017/)" >&2
  find "$TMP" -maxdepth 4 -type d
  exit 1
fi
N=$(find "$DEST" -maxdepth 1 -name '*.jpg' | wc -l)
echo "OK: в $DEST сейчас $N jpg (ожидается 5000 для полного val2017)."
