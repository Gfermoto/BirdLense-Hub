# Re-ID offline (Orin)

Прод: `reid_runtime.py` + `models/reid/ornimetrics/reid_embedder.onnx`.

## `run_daily_ssl_cycle.py`

Ежедневный оффлайн цикл: кропы → эмбеддинги ONNX → `reid_embedding` → recluster.

```bash
python3 scripts/internal/reid/run_daily_ssl_cycle.py --db app/data/db/birdlense.db
```

В контейнере: `BIRDLENSE_REID_SSL_DAILY_ENABLED=1` (`entrypoint.sh`).

## `export_crops_from_sqlite.py`

Выгрузка кропов из SQLite для оффлайн-анализа.
