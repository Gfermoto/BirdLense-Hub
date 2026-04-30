# DINOv2 Production Pipeline (RFC v1)

[Русский](./ML_DINOV2_PRODUCTION_PIPELINE.ru.md)

Parent issue: [#389](https://github.com/Gfermoto/BirdLense-Hub/issues/389)

## Goal

Move DINOv2 from offline prototype scripts to a controlled production path with explicit schema, rollout gates, and failover behavior.

## Modes

| Mode | Where it runs | SLA target | Use case |
| --- | --- | --- | --- |
| `offline_batch` | manual/cron jobs | hours | backfill and experiments |
| `nearline` | scheduled worker | minutes | regular gallery refresh |
| `realtime` | processor sidecar | seconds | online similarity hints |

Default for `dev` and `main`: `offline_batch` or `nearline`. `realtime` only after shadow validation.

## Embedding contract (`embedding_schema@v1`)

- vector length: `384` (DINOv2 small baseline)
- dtype: `float32`
- normalization: `L2`
- distance: cosine
- required metadata:
  - `embedding_schema`: `embedding_schema@v1`
  - `embedding_model_id`: model identifier (for example `facebook/dinov2-small`)
  - `embedding_model_sha16`: short fingerprint of exported model artifact
  - `crop_fingerprint_sha16`: fingerprint of crop content
  - `created_at_utc`: ISO timestamp

Compatibility rule:

- identical schema + identical vector length => compatible for mixed lookup
- schema/version mismatch => no silent merge, hard fail in similarity query path

## Data flow

1. Export crops from SQLite (`scripts/reid/export_crops_from_sqlite.py`).
2. Compute embeddings (`scripts/reid/embed_dinov2_crop.py`).
3. Optional sanity report (`scripts/reid/embed_cosine_report.py`).
4. Import sidecar embeddings (`scripts/reid/import_embeddings_sqlite.py`) — **requires** full `embedding_schema@v1` metadata in JSONL; legacy embedding-only JSONL is skipped.
5. Read-only product exposure via API/UI summary (`/api/ui/system/reid/summary`).

## Failover

- If embedding pipeline fails:
  - species classifier flow remains primary and unaffected
  - Re-ID hints are disabled, never converted into automatic identity merge
- If schema mismatch:
  - reject import/query, emit operator-visible warning
- If stale data:
  - expose stale age in system summary and mark Re-ID status as degraded

## Rollout plan

1. `dev`: offline batch only, manual verification report attached to issue.
2. `main` shadow: nearline mode, no user-facing merge actions.
3. `main` guarded: optional realtime pilot on one camera/domain slice.
4. expand only if quality gates hold for two consecutive evaluation windows.

## Gate metrics

- import success rate >= 99%
- embedding job failure rate <= 1%
- cosine stability checks pass on fixed smoke set
- no regression in processor throughput and detection/classification latency budgets

## On-device vs offline vs product UI split

- on-device: detector/classifier inference, minimal Re-ID status counters
- offline/nearline: embedding generation and refresh
- product UI: read-only status and operator review tools; no auto-merge by default
