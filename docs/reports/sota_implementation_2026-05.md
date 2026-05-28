# SOTA issues — реализация (2026-05)

Закрывать issues только после проверки на `dev`.

## Сделано в коде

| Issue | Что |
|-------|-----|
| #513 | `POST/GET/DELETE /api/ui/jobs`, `async_jobs_service.py`, OpenAPI |
| #512 | `DELETE /api/ui/jobs/track_regen`, флаг отмены в `worker_core` |
| #514 | `GET /api/ui/timeline?limit=&offset=` → `{items,total,limit,offset,has_more}` |
| #509 | `missing_audio=1`, meta `catalog_with_audio` / `catalog_missing_audio`, UI фильтр |
| #508 | `scoring_hint` в video API + tooltip «Почему этот вид?» (fusion-trace по-прежнему в VideoInfo) |
| #515 | PageHelp `speciesDirectory` / `speciesCatalog`, `CatalogOpsHubCard` на Станции |
| #507 | `scripts/classifier_confusion_report.py` (отчёт по ручным правкам) |

## Не в этом коммите (оставить открытыми)

| Issue | Причина |
|-------|---------|
| #510 | Backpressure — смотреть `/api/ui/system/diagnostics/processor-runtime` + processor gauges; нужен UI-порог/алерты |
| #511 | Zero-copy ROI — доработка `FrameContext` в processor |
| #492 | Pydantic contract уже есть (`config_schema.py`); закрыть после smoke невалидного `user_config` на стенде |

## Проверка

```bash
cd app && . .venv/bin/activate && PYTHONPATH=processor/src:web:. pytest \
  web/tests/test_async_jobs_api.py web/tests/test_backpressure_api.py \
  web/tests/test_config_guard.py web/tests/test_timeline_pagination.py \
  web/tests/test_species_catalog_audio_filter.py \
  processor/tests/test_roi_crop.py processor/tests/test_processor_config_guard.py \
  processor/tests/test_processor_backpressure.py -q
cd app/ui && npm run typecheck  # известные ошибки Settings types — вне этой волны
make deploy   # по запросу
```
