# Re-ID prototypes (`#383` / `#374`)

Offline helpers — **не** в Docker-процессоре по умолчанию.

## `embed_dinov2_crop.py`

Эмбеддинг одного или нескольких **кропов** (jpeg/png) через **DINOv2** из `torch.hub` (Facebook Research). Выход: L2-нормированный вектор (JSON Lines на stdout).

**Зависимости:** `torch`, `torchvision`, `Pillow` (отдельный venv или машина с GPU/CPU для экспериментов).

```bash
python3 scripts/reid/embed_dinov2_crop.py --image path/to/crop.jpg
python3 scripts/reid/embed_dinov2_crop.py --glob 'samples/*.jpg' --output embeddings.jsonl
```

## `embed_cosine_report.py`

Сводка по **pairwise cosine** (numpy), опционально **top-K соседей** и сравнение пар из файла (`path1<TAB>path2`) со случайными «разными» парами.

```bash
pip install numpy   # если ещё нет (рядом с torch не обязательно ставить отдельно)
python3 scripts/reid/embed_cosine_report.py --jsonl embeddings.jsonl --topk 5 -o report.md
```

## `export_crops_from_sqlite.py`

Выгрузка **кропов из SQLite Hub** (`video_species` + bbox из `frames`), те же правила пути, что и UI/датасет. Нужны **ffmpeg**, **opencv-python**, запуск с корня репозитория (скрипт сам добавляет `app/` в `PYTHONPATH`).

```bash
# из корня BirdLense-Hub, при наличии app/data/db/birdlense.db и записей
PYTHONPATH=app DATA_DIR=app/data \
  python3 scripts/reid/export_crops_from_sqlite.py \
  --db app/data/db/birdlense.db -o /tmp/reid_crops --limit 80 --manifest /tmp/reid_manifest.jsonl

python3 scripts/reid/embed_dinov2_crop.py --glob '/tmp/reid_crops/*.jpg' -o /tmp/embed.jsonl
python3 scripts/reid/embed_cosine_report.py --jsonl /tmp/embed.jsonl --topk 5 -o /tmp/report.md
```

См. также [REID_ROADMAP.md](../../docs/REID_ROADMAP.md).
