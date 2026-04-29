# DINOv2 production pipeline (RFC v1)

[English](./ML_DINOV2_PRODUCTION_PIPELINE.md)

Родительская задача: [#389](https://github.com/Gfermoto/BirdLense-Hub/issues/389)

## Цель

Перевести DINOv2 из offline-прототипа в управляемый production-контур: явная схема эмбеддингов, rollout-gates, failover.

## Режимы

| Режим | Где выполняется | Целевой SLA | Назначение |
| --- | --- | --- | --- |
| `offline_batch` | ручной/cron job | часы | backfill и эксперименты |
| `nearline` | периодический worker | минуты | регулярное обновление галереи |
| `realtime` | sidecar рядом с processor | секунды | online подсказки similarity |

По умолчанию для `dev` и `main`: `offline_batch` или `nearline`. `realtime` только после shadow-валидации.

## Контракт эмбеддинга (`embedding_schema@v1`)

- размерность вектора: `384` (базово DINOv2 small)
- тип: `float32`
- нормализация: `L2`
- метрика: cosine
- обязательные метаданные:
  - `embedding_schema`: `embedding_schema@v1`
  - `embedding_model_id`: идентификатор модели (например `facebook/dinov2-small`)
  - `embedding_model_sha16`: короткий fingerprint экспортированного артефакта
  - `crop_fingerprint_sha16`: fingerprint crop-контента
  - `created_at_utc`: ISO timestamp

Совместимость:

- одинаковая schema + одинаковая размерность => совместимый mixed lookup
- несовпадение schema/version => жёсткий отказ без silent merge

## Поток данных

1. Экспорт crop-ов из SQLite (`scripts/reid/export_crops_from_sqlite.py`).
2. Расчёт эмбеддингов (`scripts/reid/embed_dinov2_crop.py`).
3. Опциональный sanity-отчёт (`scripts/reid/embed_cosine_report.py`).
4. Импорт sidecar-эмбеддингов (`scripts/reid/import_embeddings_sqlite.py`).
5. Read-only экспозиция статуса через API/UI (`/api/ui/system/reid/summary`).

## Failover

- При падении embedding pipeline:
  - основной species-поток не затрагивается
  - Re-ID подсказки отключаются, auto-merge не включается
- При schema mismatch:
  - import/query отклоняются, выдаётся операторский warning
- При устаревших эмбеддингах:
  - в system summary показывается возраст и degraded-статус

## План rollout

1. `dev`: только offline batch, ручной отчёт в issue.
2. `main` shadow: nearline, без пользовательских merge-действий.
3. `main` guarded: опциональный realtime-пилот на одном camera/domain slice.
4. Масштабирование только при прохождении quality gates в двух окнах подряд.

## Gate-метрики

- success rate импорта >= 99%
- failure rate embedding job <= 1%
- cosine-stability проверки проходят на фиксированном smoke-наборе
- нет регрессии по throughput/latency основного CV-пайплайна

## Разделение on-device / offline / product UI

- on-device: detector/classifier inference, минимальные счётчики Re-ID статуса
- offline/nearline: генерация и обновление эмбеддингов
- product UI: read-only статус + операторские review-инструменты; auto-merge по умолчанию выключен
