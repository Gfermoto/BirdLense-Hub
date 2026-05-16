# Re-ID prototypes (`#383` / `#374`)

Offline helpers — **не** в Docker-процессоре по умолчанию.

## `embed_dinov2_crop.py`

Эмбеддинг одного или нескольких **кропов** (jpeg/png) через **DINOv2** из `torch.hub` (Facebook Research). Выход: L2-нормированный вектор (JSON Lines на stdout).

Каждая строка JSONL также содержит контрактные поля для прод-пайплайна (**`embedding_schema@v1`**, `embedding_model_id`, `embedding_model_sha16`, `crop_fingerprint_sha16`, `created_at_utc`) — см. `docs/ML_DINOV2_PRODUCTION_PIPELINE.md`.

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
python3 scripts/reid/import_embeddings_sqlite.py --db app/data/db/birdlense.db --jsonl /tmp/embed.jsonl --manifest /tmp/reid_manifest.jsonl
```

`import_embeddings_sqlite.py` creates/updates sidecar table `reid_embedding`
(`video_species_id`, `video_id`, `species_id`, `track_id`, `crop_path`,
`model`, `dim`, `embedding_json`, плюс контрактные колонки из JSONL). Это не включает Re-ID в продуктовый UI, но
фиксирует локальное хранение эмбеддингов для следующего API/UI этапа #374.

## `run_daily_ssl_cycle.py`

Ежедневный оффлайн цикл для Re-ID/SSL без остановки прод-пайплайна:

1. извлекает кропы из `video_species` за окно `--window-hours`,
2. строит DINOv2 эмбеддинги через runtime backend (`reid_runtime`),
3. обновляет `reid_embedding`,
4. recluster по видам (cosine threshold),
5. обновляет кандидаты (`individual_label`) и опционально авто-клички в `video_species`,
6. пишет отчёт с метриками: `reid_consistency`, `nickname_churn`, `id_switches`.

```bash
# базовый запуск
python3 scripts/reid/run_daily_ssl_cycle.py \
  --db app/data/db/birdlense.db \
  --window-hours 24 \
  --limit 400 \
  --cluster-threshold 0.88 \
  --report-json app/data/reid_ssl_reports/latest.json

# вариант с авто-обновлением пустых individual_nickname в video_species
python3 scripts/reid/run_daily_ssl_cycle.py \
  --db app/data/db/birdlense.db \
  --window-hours 24 \
  --limit 400 \
  --cluster-threshold 0.88 \
  --update-video-nicknames \
  --report-json app/data/reid_ssl_reports/latest.json
```

Для Docker-дистрибутива (one-click install) планировщик можно держать **внутри контейнера**
через переменные `.env` (entrypoint), без host cron:

```bash
BIRDLENSE_REID_SSL_DAILY_ENABLED=1
BIRDLENSE_REID_SSL_INTERVAL_SEC=86400
BIRDLENSE_REID_SSL_START_DELAY_SEC=300
BIRDLENSE_REID_SSL_REPORT_JSON=/app/data/reid_ssl_reports/latest.json
```

См. также [REID_ROADMAP.md](../../docs/REID_ROADMAP.md).
