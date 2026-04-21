# Release Readiness — BirdLense Hub

[English](./RELEASE_READINESS.md)

**Короткие ворота релиза:** [Definition of Done](./DEFINITION_OF_DONE.ru.md) (`make ci-local` + `verify-stack` + ручной смоук ~5 минут).

---

Чеклист перед релизом, деплоем или заявлением «починили / стабилизировали».

## 1. Доменный контракт

- `GET /api/ui/system/domain-health`
- `GET /api/ui/system/species-registry/health`

Ожидаемо:

- `orphaned_visits = 0`
- `visit_species_mismatches = 0`
- `species_resolution_mismatches = 0`
- `duplicate_name_group_count` не растёт без объяснимой миграции
- `duplicate_clip_candidates_24h` не выглядит как массовая деградация

## 2. Конфиг и рантайм

- `GET /api/ui/system/config-audit`
- сверены ключи записи и дедупликации:
  - `processor.max_inactive_seconds`
  - `processor.post_record_seconds`
  - `processor.min_seconds_between_recordings`
  - `detection.dedup_window_seconds`
  - `processor.multi_camera_groups`

## 3. Базовый smoke

- `make verify`
- `BASE_URL=http://YOUR_HOST:8085 ./scripts/verify-release.sh`
- для полного режима с закрытыми настройками:
  `BIRDLENSE_UI_API_KEY=... REQUIRE_SETTINGS_HEALTH=1 BASE_URL=http://YOUR_HOST:8085 ./scripts/verify-release.sh`

### GitHub Actions (`deploy.yml`)

Опционально, но полезно при **strict** UI API: в репозитории завести секрет **`BIRDLENSE_UI_API_KEY`** с тем же значением, что в `app/.env` на сервере. Тогда шаг **Verify** после деплоя вызывает `verify-stack.sh` с **`--check-domain-health`** и **`verify-release.sh`** с **`REQUIRE_SETTINGS_HEALTH=1`**. Без секрета CI проверяет только health/readiness/status, чтобы пайплайн не падал на эндпоинтах, требующих ключ.

Ожидаемо:

- `health` и `readiness` зелёные;
- `status.web = ok`;
- в полном режиме `domain-health`, `species-registry/health` и `config-audit` проходят без `SKIP`.

## 4. Тесты первой волны стабилизации

Минимальный набор:

```bash
cd app
docker compose run --rm -v $(pwd):/app -v $(pwd)/..:/workspace birdlense \
  bash -c 'export PYTHONPATH=/app:/app/web:/app/processor/src && \
  python -m pytest \
    web/tests/test_system_stabilization.py \
    web/tests/test_species_registry.py \
    processor/tests/test_decision_maker.py \
    processor/tests/test_recording_finalize_file_gate.py \
    processor/tests/test_processor_bootstrap.py \
    -q --tb=short'
```

## 5. Review-only и научная объяснимость

- review-only строки не создают `SpeciesVisit`;
- monthly/overview stats не растут от `species_visit_id = NULL`;
- `decision_trace` содержит `decision_kind`, `decision_reason`, `outcome_bucket`, `trust_band` и recording context.

## 6. Данные и реестр видов

Перед merge или деплоем после data-fix:

- dry-run `POST /api/ui/system/species-catalog/reconcile`
- при необходимости `POST /api/ui/system/species-registry/backfill`
- повторно проверить `species-registry/health`

## 7. Что блокирует релиз

Релиз считается заблокированным, если:

- есть немые auto-decisions без объяснимой причины;
- появились новые orphaned visits или species mismatches;
- статистика раздувается от review-only;
- каталог видов дрейфует между `Species`, `SpeciesTaxon` и resolver;
- smoke/verify зелёные только частично или «с оговорками».
