# Active learning helpers (#369)

- **Schema:** [`pool_entry_v1.schema.json`](./pool_entry_v1.schema.json)
- **Template line:** [`emit_pool_template.py`](./emit_pool_template.py)
- **Trace → manifest JSONL:** [`decision_trace_to_pool_manifest.py`](./decision_trace_to_pool_manifest.py) — из экспортированного `decision_trace` (persisted/rejected rows) строит строки пула; пути кропов `_pending/…` заглушки до офлайн-экспорта.
- **SQLite → manifest JSONL:** [`export_pool_from_sqlite.py`](./export_pool_from_sqlite.py) — читает `activity_log.type = decision_trace` напрямую из `birdlense.db`, умеет `--needs-review-only`, `--entropy-ge`, `--margin-le`.

```bash
DB=app/data/db/birdlense.db OUT=pool.jsonl make active-learning-pool-from-sqlite
python3 scripts/active_learning/export_pool_from_sqlite.py --db app/data/db/birdlense.db --needs-review-only -o pool.jsonl
```

See [ACTIVE_LEARNING](../../archive/internal/docs-legacy/ACTIVE_LEARNING.md).
