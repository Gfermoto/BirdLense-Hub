# Обзор репозитория BirdLense Hub

Отчёт сверен с кодом и CI (`.github/workflows/ci-pr.yml`, `scripts/public/ci-full-local.sh`). Устаревшие утверждения прежней версии (отсутствие `tsconfig`, SCSS, один UI-тест, `controllers.py`, `/api/v1/health`, hardcoded `/opt/birdlense/weights`, отсутствие ruff/pip-audit) **не подтверждаются**.

## 1. Краткий обзор по слоям

| Слой | Ключевые файлы/папки | Что проверить |
|------|---------------------|---------------|
| **Процессор** | `app/processor/src/`<br>`recording_session.py`, `detection_strategy.py`, `frame_processor.py`, `frame_geometry.py`, `detect_first.py`, `dual_stream_timeline.py`, `media_runtime.py`, `go2rtc_stream_source.py` | 1. Dual-stream: `detect_stream_name` на камере, смещение таймлайна detect→main (`dual_stream_timeline.py`, `media_runtime.py`). 2. Detect-first: якорь и persist-строки (`detect_first.py`). 3. Геометрия bbox: letterbox/unpad/remap (`frame_geometry.py`). 4. Широкие `except Exception` (~187 вхождений в 58 файлах) — маскируют сбои. 5. `threading.Lock` есть в отдельных модулях (`mqtt_aggregator.py`, `frigate_mqtt.py`, `processor_runtime_stats.py`), но не единообразно на всём shared state. 6. Типизация: ruff в CI есть, mypy — нет; в hot paths аннотации неполные. |
| **Веб-API** | `app/web/`<br>`routes/`, `openapi.yaml`, `services/strict_ui_api_auth_service.py`, `services/readiness_service.py`, `services/persist_funnel_service.py`, `services/prometheus_metrics_service.py` | 1. Контракт: `openapi.yaml` + `test_openapi_contract.py`. 2. Auth: при `BIRDLENSE_STRICT_API_AUTH=1` закрыт анонимный доступ к `/api/ui/*`; публичный GET-allowlist включает `/api/ui/health`, `/api/ui/readiness`, CSRF и др. (`strict_ui_api_auth_service.py`) — не «все эндпоинты открыты». 3. Валидация: Pydantic + ручные проверки в settings/services. 4. Логи: только `StreamHandler` в stdout (`app_logging.py`), без file/JSON handler. 5. Метрики: readiness, persist funnel, Prometheus (`readiness_service.py`, `persist_funnel_service.py`, `prometheus_metrics_service.py`). |
| **UI** | `app/ui/`<br>`tsconfig.json`, `tsconfig.app.json`, `src/api/client.ts`, `vite.config.ts`, Vitest `*.test.ts(x)` | 1. TypeScript: `npm run typecheck` (`tsc -p tsconfig.app.json --noEmit`) в CI. 2. Стили: MUI + Emotion (`package.json`); **файлов `.scss` нет**. 3. Тесты: **22** Vitest-файла (`src/**/*.test.ts(x)`). 4. HTTP: `csrfFetch` + CSRF token в `api/client.ts`; параллельно raw `fetch` в `timeline.ts`, `dataset.ts`, `labelling.ts` и др., axios в `birdFoodFeed.ts`, `favorites.ts`, `speciesRegistryHub.ts` — смешанная модель. 5. OpenAPI types: `npm run codegen:openapi` → `src/generated/openapi-types.ts`. |
| **Документация** | `docs/`, MkDocs | 1. CI: `mkdocs build --strict`, проверка SITE_MAP. 2. **markdownlint в CI нет**. 3. Устаревшие пути (`/opt/birdlense`) остались только в legacy-доках с явными пометками (`docs/deploy-server.md`, `docs/testing.md`). |
| **CI/CD** | `.github/workflows/ci-pr.yml`, `scripts/public/ci-full-local.sh`, `scripts/verify-prod-env.sh` | 1. Python: bandit, **pip-audit** (не safety), **ruff** check+format, pytest web (~123 теста). 2. UI: eslint, typecheck, vitest, Playwright smoke (docker job). 3. Prod gates: `verify-prod-env.sh` с синтетическими секретами (`BIRDLENSE_STRICT_API_AUTH`, `FLASK_SECRET_KEY`, `PROCESSOR_SECRET`). 4. Docker: `docker compose build birdlense` **без `-q`**. 5. **mypy в CI нет** (ruff есть). |

## 2. Архитектура (актуальное состояние)

| Область | Где в коде | Суть |
|---------|-----------|------|
| Dual-stream detect/main | `media_runtime.py`, `go2rtc_stream_source.py`, `dual_stream_timeline.py` | Отдельный lores detect-поток Go2RTC; смещение таймлайна детекций к main/playback. |
| Detect-first | `detect_first.py`, `recording_session.py` | Ранний якорь по YOLO/Frigate до полного finalize; persist-строки и safeguard. |
| Bbox remap | `frame_geometry.py` | Letterbox, unpad/pad, remap norm bbox между canvas/source/overlay/crop. |
| API-контракт | `app/web/openapi.yaml` | Источник правды для web + codegen UI. |
| Production gates | `scripts/verify-prod-env.sh`, `app/web/config.py` | Обязательные секреты и strict auth в production. |
| Readiness / funnel | `readiness_service.py`, `persist_funnel_service.py` | Сводки готовности и воронки persist (yolo_frames_with_tracks → post_fusion_persisted). |
| Метрики | `prometheus_metrics_service.py`, `request_metrics_service.py` | Prometheus-экспорт и per-request наблюдение уже реализованы. |

## 3. Реальные потенциальные улучшения

Без выдуманных «баг-ID» и номеров строк. Только наблюдаемое в репозитории.

| Приоритет | Область | Файлы / зона | Наблюдение |
|-----------|---------|--------------|------------|
| **P1** | Процессор | `app/processor/src/**/*.py` (58 файлов) | Массовые `except Exception` без узкой классификации — риск проглатывания OOM, IOError, логических ошибок. Наибольшая плотность: `recording_finalize.py`, `mqtt_aggregator.py`, `recording_session.py`, `go2rtc_stream_source.py`. |
| **P1** | UI HTTP-слой | `api/client.ts` vs `api/timeline.ts`, `dataset.ts`, `labelling.ts`, `settingsYamlDb.ts` | Два стека (`csrfFetch`, raw `fetch`, `axios`) — разное поведение CSRF, ошибок и тестируемости. |
| **P2** | Web logging | `app/web/app_logging.py` | Только stdout; для production-сбора нет ротируемого file handler или structured JSON (structlog/opentelemetry — не подключены). |
| **P2** | Процессор concurrency | `mqtt_aggregator.py`, `frigate_mqtt.py`, др. | Lock есть точечно; нет явного аудита всех shared mutable structures (очереди, кэши, stats). |
| **P2** | Статическая типизация Python | processor + web hot paths | Ruff в CI; **mypy/pyright отсутствуют** — типы в `recording_session.py`, `detection_strategy.py` и services неполные. |
| **P3** | CI noise | `.github/workflows/ci-pr.yml` (job docker-tests) | `docker compose build` без `-q` — длинные логи без функционального выигрыша. |
| **P3** | Docs lint | `docs/` | MkDocs `--strict` ловит битые ссылки при сборке; отдельного **markdownlint** нет. |

## 4. Рекомендации (только то, чего ещё нет)

| # | Рекомендация | Обоснование |
|---|-------------|-------------|
| 1 | Сузить `except Exception` в процессоре: ловить ожидаемые типы, логировать с контекстом, re-raise критичные | ~187 широких перехватов; усложняет диагностику YOLO/ingest сбоев |
| 2 | Унифицировать UI HTTP через `csrfFetch` / тонкий wrapper с единым error parsing | Сейчас смесь fetch/axios; тесты мокают по-разному (`client.test.ts`, `weatherRegion.test.ts`) |
| 3 | Добавить **mypy** (или pyright) в `ci-full-local.sh` / CI для `web/` и `processor/src/` — постепенно, с baseline | Ruff уже в CI; typecheck UI уже есть; Python-типы — пробел |
| 4 | Опциональный structured logging / file handler за feature-flag | `app_logging.py` — только `StreamHandler` |
| 5 | `markdownlint` для `docs/` (отдельный CI step или pre-commit) | MkDocs strict ≠ стиль/единообразие markdown |
| 6 | `docker compose build -q` в CI при стабильном кэше | Сократить шум логов docker-tests job |

**Уже сделано — не дублировать в backlog:** ruff + pip-audit + bandit в CI; `npm run typecheck`; 22 Vitest-файла; OpenAPI contract; strict UI auth с allowlist; Prometheus/readiness/funnel; конфиг через `app_config/` и env (`FLASK_SECRET_KEY`, `PROCESSOR_SECRET`); пути весов через config, не hardcode в runtime-коде.

---

> Отчёт отражает состояние репозитория BirdLense Hub на **июнь 2026**. Перед релизом: `make ci-local` (или `make ci-local-docker` для полного слоя) и `make verify-prod-env` на целевом `app/.env`.
