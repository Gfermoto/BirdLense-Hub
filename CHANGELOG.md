# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Changed

- **Web / SQLAlchemy 2.x:** `ActivityLog` и `Video` загружаются через `db.session.get(...)` вместо устаревшего `.query.get()` (`processor_routes` activity log, `gallery_upload_service`). **Processor:** docstring у `DecisionMaker.decide_stop_recording`, комментарий к ключу `(key, -1)` в `species_normalizer` ([#221](https://github.com/Gfermoto/BirdLense-Hub/issues/221)).
- **Processor (tech debt #222):** `ebird_regional_confidence` больше не правит `sys.path` — импорт `services.ebird_region_service` при нормальном `PYTHONPATH` (`/app:/app/web` в Docker). **MQTT:** разведены `is_mqtt_live()` (сокет к брокеру) и `is_mqtt_ok_for_heartbeat()` (с запасом после обрыва); heartbeat UI — второй, выбор Frigate primary и motion — первый ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** лимит попыток verify-password, `Retry-After` и `client_ip_for_rate_limit` перенесены из `util.py` в `auth.py`; в `util` оставлен re-export для обратной совместимости ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** Wikipedia / iNaturalist, allowlist хостов для прокси, seed-иерархия и канонический маппинг видов, `update_species_info_from_wiki`, `filter_feeder_species` вынесены в **`species_metadata.py`**; `util.py` реэкспортирует прежние имена ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** `get_primary_video_for_visit*`, `format_visit_for_timeline`, `format_unlinked_video_for_timeline` вынесены в **`timeline_payloads.py`**; `util` реэкспортирует их для существующих импортов ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Follow-up ([PR #226](https://github.com/Gfermoto/BirdLense-Hub/pull/226) review):** очистка устаревших IP в счётчике verify-password; разбор `Authorization` для метрик с регистронезависимым `Bearer`; Frigate остаётся primary motion при старте даже если MQTT ещё не live; MQTT-only детекции в `species_normalizer` не затирают друг друга при `one_per_species`; OpenAPI — `400` для `/system/activity`, путь `/system/logs`; UI Overview без небезопасного cast погоды; правки доков scales/`DATA_DIR`; устойчивость `github-issue-link-subissues.sh` к 404 от `gh api`.

### Docs

- **Деплой:** правило Cursor и `scripts/deploy.local.sh.example` описывают **два равноправных режима** — **LAN** (на площадке: `192.168.1.11:22`, UI `:8085`) и **удалённый** (VPS `185.218.111.196:2222`, UI `birdlense.eyera.info` или IP); в `deploy.local.sh` держать активным один блок и переключать при смене места работы.
- **Tech debt:** эпик [#220](https://github.com/Gfermoto/BirdLense-Hub/issues/220); **sub-issues** [#198](https://github.com/Gfermoto/BirdLense-Hub/issues/198), [#201](https://github.com/Gfermoto/BirdLense-Hub/issues/201), [#221](https://github.com/Gfermoto/BirdLense-Hub/issues/221)–[#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225); `scripts/github-issue-link-subissues.sh`. [ROADMAP.ru.md](docs/ROADMAP.ru.md) — **волна D**.
- **Scales / roadmap:** базовая интеграция весов отражена как реализованная; [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) — backlog: **триггер по скачку массы**, **оценка веса птицы в карточке визита** (в духе корма/погоды). [CONFIGURATION](docs/CONFIGURATION.ru.md) — ключи `integrations.scales.*` (MQTT / Home Assistant).

### Fixed

- **UI (Overview):** карточка погоды больше не пропадает из сетки: пока `/api/ui/weather` грузится, показывается скелетон; сбой погоды не блокирует весь обзор — только блок погоды с кнопкой «Повторить».

### Tests

- **Xeno-canto:** `web/tests/test_xeno_canto_service.py` — парсинг и ошибки сети через мок `requests.get`; `GET /species/.../xeno-canto` в `test_api` без реального HTTP. Шаг в CI `openapi-contract` (#202).
- **Birdfood / Web Push:** `web/tests/test_settings_mutations_smoke.py` — 403 при закрытых настройках, POST+PATCH кормушек, дубликат имени, успешный `push/subscribe` при включённых уведомлениях. CI `openapi-contract` (#202).
- **Тот же файл:** стрим видео при `require_auth_for_video_stream` — гость 403, contributor 200; успешный `PATCH /api/ui/settings` с ролью admin (#202).
- **Processor / system:** `test_processor_videos_smoke.py` — секрет, пустой species, порог confidence, успешный ingest, невалидные даты; `test_system_routes_smoke.py` — activity, metrics/history, logs (403/200). CI `openapi-contract` (#202).
- **OpenAPI / CI:** `openapi.yaml` — ответ `/overview` (`hourlyTemperature`, `lastDetection`, `observer_timezone`, `stats.detectionByProvider`), схема `VideoNeighbors` и query-параметры как в API; контракт-тест `GET /videos/{id}/neighbors`. В job `openapi-contract` — **ruff** только для `web/tests/`; мелкие правки импортов под ruff (#202).

### Security

- **Metrics endpoints (optional auth):** если задан **`BIRDLENSE_METRICS_TOKEN`**, `GET /metrics`, `GET /api/metrics` и `GET /api/metrics/summary` требуют `Authorization: Bearer <тот же токен>` (`hmac.compare_digest`); без переменной поведение как раньше (удобно для scrape в LAN). См. [CONFIGURATION](docs/CONFIGURATION.ru.md) → Prometheus.
- **Code scanning (path injection):** чтение и удаление превью для Telegram — **`read_safe_image_bytes`** / **`remove_safe_image_file`** в `util.py`: `realpath` + `commonpath` + **`startswith(DATA_DIR + sep)`**, затем `open`/`os.remove`; логика вынесена из `notifications.py`. Удалён **`_safe_image_path_or_none`**. Для **`py/path-injection`** на sink-строках — **`# lgtm[py/path-injection]`** (путь уже ограничен каталогом данных); иначе анализатор не снимает taint с `realpath(path)` до `open`/`remove`.

## [0.3.2] - 2026-04-03

Патч безопасности и документации после **v0.3.1**: CodeQL, прокси изображений, CodeRabbit follow-up, синхронизация версий.

### Security

- **CodeQL-driven hardening (Python):** species image proxy (`GET /api/ui/species-image`) follows redirects manually with an allowlisted host check on every hop; each request uses a URL rebuilt from parsed host/port/path (no userinfo). Client-facing proxy errors are generic; details only in server logs. Telegram/notification image paths use `_safe_image_path_or_none` that returns only a resolved path under `DATA_DIR`. Go2RTC: connect log omits URL-derived fields (credentials never hit log lines). eBird region comparison cache key uses **SHA-256** (truncated) instead of MD5. Species catalog allowlist parsing avoids a polynomial-ReDoS-prone regex.
- **Follow-up (CodeRabbit review on PR #218):** iNaturalist open-data allowlist for the species image proxy is **hostname-only** (`_host_is_inaturalist_open_data_asset`) — no substring match on the full URL (closes query-string SSRF bypass). `urlparse` / `hostname` / `port` wrapped where needed to avoid 500 on malformed URLs. `_is_safe_image_path` / `_safe_image_path_or_none` use `os.path.commonpath` against `DATA_DIR` to block `data_evil`-style prefix tricks. Regression tests added.
- **UI (`app/ui`):** refreshed `package-lock.json` and `overrides` so **lodash** resolves to **≥4.18.0** (addresses [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc), [GHSA-f23m-r3pf-42rh](https://github.com/advisories/GHSA-f23m-r3pf-42rh)); **serialize-javascript** pinned via override to **≥7.0.5**. `npm audit` clean. Python `requests` / **Flask-Cors** were already at patched versions in `app/web` and `app/processor` requirements.

### Changed

- **Docs / repo hygiene:** added [REPOSITORY_LAYOUT](docs/REPOSITORY_LAYOUT.md) (EN/RU) for onboarding; moved publication drafts to `docs/article/`; refreshed docs index version line and roadmap stack (Ultralytics pip vs Docker base). Root `.gitignore` now ignores `/.pytest_cache/`.
- **Docs refactor:** MkDocs `nav` aligned with [SITE_MAP](docs/SITE_MAP.md) — `DEPLOY_SERVER`, `VERIFICATION`, pre-implementation checklist, `UX_TOOLTIPS`, Russian **A11Y** / **REPOSITORY_LAYOUT**; `INSTALL` cross-links the deploy checklist; [API](docs/API.md) version line tracks root `VERSION`; ROADMAP changelog links use [project/changelog](docs/project/changelog.md); `article/**` and `CONSILIUM_AUDIT.ru.md` excluded from the static site build; ROADMAP anchor IDs fixed for strict builds.
- **Contributor docs:** removed `AGENTS.md`; maintainer workflow lives in [CONTRIBUTING](CONTRIBUTING.md) / RU. [GOVERNANCE](docs/GOVERNANCE.md) / RU, [MCP_SETUP](docs/MCP_SETUP.md), OpenAPI description, PR template, CodeQL/local dev guides, and related copy updated for a standard open-source tone (human reviewers, VS Code).
- **Docs:** MCP again documented explicitly as **Model Context Protocol** for **external AI assistants** (README, OpenAPI narrative, FEATURES, GLOSSARY, MCP_SETUP EN/RU)—without implying the project itself was authored by AI.

## [0.3.1] - 2026-04-04

Патч после **v0.3.0**: обновления зависимостей и согласованность Docker/CI. Merge: [#213](https://github.com/Gfermoto/BirdLense-Hub/pull/213); gunicorn: [#208](https://github.com/Gfermoto/BirdLense-Hub/pull/208).

### Changed

- **Processor:** `ultralytics==8.4.33` в `app/processor/requirements.txt` (обновление пакета через `pip` в образе).
- **Web:** `gunicorn` 23.x → **25.3** в `app/web/requirements.txt`.
- **UI (dev):** `eslint-plugin-react-hooks` **^7.0.1** (`app/ui/package.json` / lockfile).

### Fixed

- **Docker / CI:** базовый образ остаётся `FROM ultralytics/ultralytics:8.4.21` — при `8.4.33` в базе ломалась сборка динамического модуля **ngx_brotli** под nginx из образа (`cc … -Werror`). Версия Ultralytics для рантайма процессора задаётся pip-слоем.

## [0.3.0] - 2026-04-03

Накопительный релиз после **v0.2.10**: обзор и таймлайн, границы Library/System, ужесточение API и CI. Merge: [#211](https://github.com/Gfermoto/BirdLense-Hub/pull/211).

### Fixed

- **Overview / Timeline / визиты:** счётчики «всего визитов», графики топ-видов и «последний час» считают **число визитов** (строки `SpeciesVisit`), а не сумму `max_simultaneous` и не число сегментов `VideoSpecies`. Блок «По источникам» — **сколько визитов** содержат хотя бы один сегмент провайдера (с подсказкой, что сумма может превышать общее число визитов при слиянии источников). **`GET /api/ui/timeline`** и экспорт: дедупликация визитов после `JOIN` (один визит с несколькими роликами больше не дублируется в списке и статистике). PDF-отчёт и `get_monthly_report_data` выровнены с той же семантикой.
- **Overview UI:** карточка «Топ видов» — легенда под диаграммой (как «Суточный паттерн»), без обрезки из‑за `height: 100%` / overflow; масштаб как у суточного паттерна (`hideLegend`, размер 450).
- **Таймлайн «Записи»:** `GET /api/ui/timeline` (и экспорт) дополняется роликами за выбранный интервал, которые **ни к одному визиту не привязаны** — они отображаются отдельными карточками с пометкой «Запись без визита» (`timeline_kind: unlinked_video`, отрицательный `id` в JSON). Листание prev/next на странице видео снова **по всем роликам за локальный день** (как в архиве), без режима `visit_day`.
- **Cleanup / legacy removal:** removed dead Library/System UI leftovers (`RecordingsAndDataset`, `SystemActivity`, dormant BirdDirectory page/help/i18n), so legacy dangerous controls can no longer reappear through accidental imports.
- **Backend surface hardening:** `/api/ui/status/debug` now requires authenticated admin settings access; legacy sync species-registry maintenance routes were removed in favor of the active async `start/status` flow.
- **Docs / operator parity:** TESTING, CONFIGURATION, and ARCHITECTURE docs now match the live routes and current species/catalog UI model.
- **CI:** аудит карточек каталога (`audit_species_cards.py`) — опции `--ignore-direct-image-429`, `--ignore-empty-description`, `--ignore-empty-image-url` и меньше воркеров в PR: не фейлить на **429** Wikimedia и на незаполненных карточках минимальной БД CI.
- **`settings-ui-coverage`:** сканирование всех `*.tsx` в `Settings/` (поля Go2RTC в секциях), allowlist для новых ключей `processor.track_regen_precise_*` и `species.tuning_target_species_ids`.
- **`POST /api/ui/system/db/restore`:** при отсутствии файла в multipart сначала ответ **400** (раньше при отсутствии live SQLite на диске мог вернуться **404** до проверки загрузки).
- **Stabilization / safety:** `POST /api/ui/system/realign-visit-times` now exists with honest preview/apply flow; `clean-orphaned-visits` preview no longer mutates the DB; production no longer treats empty passwords as an implicit admin unlock for system/settings flows.
- **Library / System boundary:** Library now shows a real recordings-on-disk calendar instead of processor heartbeat and points operators to System for maintenance; heartbeat activity moved to System.
- **Overview / cross-day visits:** Overview now counts visits that overlap the selected day and buckets cross-midnight visits into the selected day instead of the previous day’s hour.
- **Species merge integrity:** merging species rows now preserves missing target metadata (description, image, metadata source) instead of silently dropping it.

## [0.2.10] - 2026-03-31

Накопительный релиз после v0.2.9: каталог/реестр, производительность, Telegram/MTProto, CI/E2E, перегенерация треков. Merge: [#196](https://github.com/Gfermoto/BirdLense-Hub/pull/196).

### Tracks / перегенерация

- **Перегенерация треков:** частичная замена по выбранным видам (`species_ids`); сопоставление детекций с каталогом по таксону и имени; `GET /api/ui/species/track-regen-options` — виды с треками на видео (VideoSpecies); при фильтре по виду период запроса — весь охват библиотеки из storage stats; ручные правки — сопоставление вида по таксону, не только построчное равенство имён; лог при пустой очереди с `species_ids`.

### Documentation

- **CONFIGURATION / Telegram:** раздел «если my.telegram.org выдаёт ERROR» — обход через SOCKS/HTTP или без прокси без api_id; уточнены ключи `telegram_proxy_type` и MTProto.
- **CONFIGURATION / Telegram:** добавлены простые команды для авто-ротации прокси на сервере: `make proxy-rotation-install`, `make proxy-rotation-status`, `make proxy-rotation-remove`.
- **INSTALL / docs index:** добавлен короткий путь «one-command setup» для Telegram proxy autorotate в `INSTALL(.ru).md` и `docs/README(.ru).md` (установка, статус, отключение, one-shot).

### Added

- **Каталог видов / allowlist классификатора:** `species.catalog_allowlist_file` + `species.catalog_strict_ingest` — список классов из обучения (скрипт `scripts/datasets/dump_classifier_allowlist.py`), строгий импорт вне списка → «Unknown». `POST /api/ui/system/species-catalog/reconcile` — слияние дубликатов по нормализованному имени, перенос подозрительных (блоклист) и строк вне allowlist на «Unknown». Блоклист также отсекает новый мусор на импорте.
- **Согласованность классификатора и датасета:** `GET /api/ui/system/species-registry/classifier-dataset-alignment` — классы из `processor.models.classifier` (как у процессора), каталог `Species` и папки `data/dataset/train|val`; карточка System «Классификатор, каталог и датасет». Подсказка в отчёте data-quality.
- **Каталог видов / качество данных:** `species_suspect_blocklist.txt` — скрытие не-птиц и «вещей» в справочнике (`GET /api/ui/species?exclude_suspects=1`), карточка System «Качество каталога», `GET /api/ui/system/species-registry/data-quality` (отчёт, дубликаты имён для merge). Календарь миграции исключает те же строки; кэш `migration_cal:v2`.
- **Deploy / статика:** rsync больше не исключает весь `app/data` — на сервер попадает `app/data/images` (иконки корма и т.д.); записи и БД по-прежнему в `app/data/recordings`, `app/data/db`. В образе — `data/images` в `/_bundled_data` и копирование в `/app/data/images` при старте контейнера (fallback).
- **Миграции / UI+API:** фильтры «только с активностью» vs «весь каталог» (`catalog`) и «все визиты» vs «только с видео-детекцией» (`evidence`). Связь с планом [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125).
- **Детекция без дообучения:** `detection.cross_source_confidence_bonus` (по умолчанию 0.02) — одноразовый бонус к confidence при первом слиянии MQTT (Frigate/BirdNET) в существующую YOLO-детекцию.
- **System / observability:** карточка «Наблюдаемость уведомлений» — счётчики `notify_preview_24h` и подсказка по URL экспорта метрик Hub для Heimdall/Grafana; `GET /api/ui/system/observability` (с авторизацией настроек), `GET /api/metrics/summary` (JSON, тот же смысл, что и `/metrics`).
- **Docs / Heimdall:** явно описано направление данных: метрики **отдаёт Hub** (`/metrics`, `/api/metrics/summary`), в Heimdall добавляют ссылку на хаб; поле `heimdall_url` — только проверка доступности Heimdall **с сервера Hub**; про `http://heimdall.local` и резолв из Docker.
- **Gallery:** нормализация JPEG (мин. размер, ограничение стороны) и fallback на **полный кадр**, если кроп по bbox не удался — ближе к надёжности Telegram-превью.
- **Telegram / прокси:** выбор типа — **без прокси**, **SOCKS5 / HTTP (URL)** или **MTProto** (сервер, порт, секрет hex как в приложении Telegram). MTProto-режим отправляет сообщения через **Telethon** (нативный MTProto); нужны **api_id** и **api_hash** с https://my.telegram.org или переменные `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` в окружении. Зависимость: `telethon`. Paid Media (Stars) в MTProto-режиме не поддерживается — отправляется обычное фото.
- **Ops / Telegram:** `scripts/manage-telegram-proxy-rotation.sh` и make-таргеты для установки cron-авторотации (по умолчанию каждые 6 часов). Ротация запускает `scripts/refresh-telegram-proxy.sh` на самом сервере (`BIRDLENSE_PROXY_LOCAL=1`), выбирает лучший рабочий SOCKS5 и обновляет `user_config.yaml` только при изменении.
- **Настройки:** блок «Производительность / кэш API» — включение Redis и опциональный URL (`performance.*`); секретный URL маскируется в API; в **GET /settings** добавлено read-only поле `performance.redis_url_effective_masked` — фактический URL (в т.ч. из `REDIS_URL`), пароль замаскирован; в форме — placeholder и строка «Сейчас используется».
- **Весы у кормушки:** `integrations.scales` — источник MQTT (топик с числом/JSON, совместимо с ESPHome/HA) или сущность Home Assistant; отображение веса на главной в карточке кормушки; процессор пишет `data/feeder_scale_state.json`.
- **Heimdall integration:** новый ключ `general.heimdall_url` (Settings → General) и серверный probe в разделе System (доступность, HTTP-статус, latency, title/version если доступны).
- **System UI / ревизия:** новая карточка «Ревизия конфигурации» на странице System (`/api/ui/system/config-audit`) — показывает deprecated/unknown keys, Telegram photo/proxy, gallery URL и статус Gray/Grey mapping.

### Changed

- **Видео в UI:** поток `/api/ui/videos/:id/stream` по умолчанию доступен гостям (как в ACCESS_CONTROL); опционально `general.require_auth_for_video_stream: true` для прежней блокировки.
- **System / каталог:** карточки качества каталога и согласования классификатора свёрнуты в аккордеон «Диагностика каталога»; смягчены подсказки в UI.
- **Старт Hub / containment:** тяжёлые мутации БД на старте по умолчанию выключены — `BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA`, `BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT`, `BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA`; Telegram «App is UP!» — `BIRDLENSE_NOTIFY_APP_STARTUP=0`. См. CONFIGURATION.
- **GET `/api/ui/species/:id/summary`:** только чтение (без Wikipedia/commit); в ответе `metadata_status` и `metadata_trust`.
- **Processor:** single-stage COCO — только класс `bird`; при `boxes.id is None` повторный `track` на том же кадре; зависимость `lap` для ByteTrack; ESLint — `ignores` для `dist`/`node_modules`.
- **CI (PR):** после web-тестов — E2E smoke Playwright против локального `docker compose up`.
- **Деплой:** при `BIRDLENSE_ENV=production` на удалённый `app/.env` идемпотентно дописываются `TRUSTED_PROXY=1` и `BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1`, если ключей ещё нет.

- **Донаты:** только иконка в шапке (рядом с языком и настройками); убраны из карточки «Корм» и из меню шестерёнки; **URL по-прежнему в настройках** (Общие → ссылка для поддержки).
- **Системная нормализация Gray/Grey:** добавлены канонические пары в `detection.species_mapping` и `species_canonical_mapping.txt` (`Gray-headed Woodpecker`/`Great Gray Shrike` → `Grey-*`), чтобы исключить рассинхрон имён между источниками.
- **Telegram:** подсказка про MTProto vs Bot API (HTTPS); прокси — SOCKS5h или HTTP(S).
- **Пороги детекции (дефолты в репо):** снова нейтральные значения `min_track_duration` 4, `min_confidence_binary` 0.22, `min_confidence_to_process` 0.36, `detection.min_confidence_to_store` 0.36 (без лишнего ужесточения). Продакшен-хаб настраивается **`user_config.yaml` на сервере** (не в git): там заданы рабочие пороги под площадку.
- **Обзор:** подсказки при наведении на все карточки ключевой статистики (раньше только «Время записи»).
- **Локализация / кормушка:** «Реле кормушки» → «Кормушка» (раздел настроек про выдачу корма, весы и реле).
- **Каталог корма:** позиция «Apple pieces» убрана из дефолтного списка; при старте старые строки с таким именем удаляются вместе со связями в `video_bird_food_association` (общая категория **Fruit** остаётся).

### Performance

- **Gunicorn:** `gthread` + **8** потоков (переменная `GUNICORN_THREADS`), `--timeout 0` — воркер не рвёт долгие стримы; параллельные запросы при одном процессе.
- **SQLite:** `check_same_thread=False`, таймаут подключения 30 с; при старте соединения — **WAL**, `synchronous=NORMAL`, `cache_size` ~64 MiB, `temp_store=MEMORY`.
- **Nginx:** **gzip** для JSON/JS/CSS/XML; **upstream keepalive** к Gunicorn (`proxy_http_version 1.1`, пустой `Connection`); **open_file_cache** для статики.
- **Кэш ответов API (TTL):** `/status` 5 с; `/species` 45 с; `/species/observed` 45 с; `/bird_families` 300 с; `/migration-calendar` 120 с; `/timeline` 20 с; `/unknowns` 12 с; `/detection-frames` 45 с; `/species/:id/summary` 30 с; Xeno-Canto 600 с. **Сброс кэша:** `services/http_response_cache.bust_response_caches()` — после PATCH настроек, правок детекций, merge видов, удаления видео и **POST `/api/processor/videos`** (новая запись).
- **Убран `app_config.reload()`** из `GET /api/ui/feed/info` на каждый запрос.
- **React Query:** `refetchOnWindowFocus: false`, `retry: 1`, `gcTime` 15 мин — меньше лишних запросов при переключении вкладок.
- **Страница видео / стриминг:** GET `/api/ui/videos/:id` больше не включает покадровые `frames` (часто мегабайты JSON) — оверлей треков подгружает `GET /api/ui/videos/:id/detection-frames` параллельно; плеер и метаданные появляются сразу после лёгкого ответа. Nginx: для `/api/ui/videos/*/stream` отключены `proxy_buffering` и `proxy_request_buffering`, увеличены таймауты чтения/отдачи — быстрее старт MP4 по HTTP Range.
- **Backend кэширование ([#203](https://github.com/Gfermoto/BirdLense-Hub/issues/203)):** `services/cache.py` — in-memory TTL или **Redis** при `REDIS_URL`. `/api/ui/overview` и region-comparison — как ранее; **тяжёлые эндпоинты «Система» и хранилище** — TTL-кэш с инвалидацией после purge/retention/scan/clean visits и merge видов. **Redis по умолчанию в Docker:** сервис `redis` (`birdlense-redis`) в `docker-compose.yml` и `docker-compose.pull.yml`, `REDIS_URL=redis://redis:6379/0`, `depends_on` + healthcheck. **Nginx Brotli** — динамический модуль `ngx_brotli` в образе. **PostgreSQL:** `DATABASE_URL` + пул в `config.py`; пример только Postgres: `app/docker-compose.stack.example.yml`. Зависимости: `redis`, `psycopg[binary]`.
- **React Query staleTime:** `staleTime=5 мин` на 4 редко-изменяемых запроса (bird-directory, species, observed) — меньше лишних refetch.

### Refactored

- **`util.py` → 3 модуля:** `auth.py` (аутентификация и rate-limit), `notifications.py` (Telegram + Web Push), `weather_service.py` (WeatherFetcher / HAWeatherFetcher / fetch_weather). `util.py` сохраняет re-exports — все существующие импорты работают без изменений. Убраны ~591 строк дублирования.
- **`SettingsForm.tsx` → секции:** `sections/GeneralSection`, `VideoSection`, `ProcessorSection`, `NotificationsSection`, `EBirdSection`, `IntegrationsSection`; `shared/ServiceBlock`, `CamerasListField`. Главный файл стал оркестратором (< 120 строк).
- **React Error Boundary:** `components/ErrorBoundary.tsx` + оборачивает `<Routes>` в `App.tsx` — несломанный рендер при runtime-ошибках в дочерних страницах.

### Fixed

- **Telegram MTProto:** корректный разбор `telegram_api_id` и порта прокси из YAML/чисел (в т.ч. `12345.0`), чтобы после сохранения настроек не «терялся» api_id.
- **Telegram preview:** нормализация фото перед отправкой (`Pillow` + fallback через `OpenCV`) и upscaling очень маленьких кропов (минимум 64px), чтобы снизить ошибки Bot API `IMAGE_PROCESS_FAILED`.
- **Telegram notifications UX:** для детекций передаётся deep-link на конкретную запись (`/videos/{id}`) вместо общего `live`; превью теперь имеет fallback-кроп из сохранённого видео по `frames.bbox`, если `best_frame` отсутствует; кнопка в TG — более нейтральная (`Open video` / `Open live`).
- **Telegram notifications reliability:** чтобы избежать «пустых» уведомлений, добавлен дополнительный fallback на **полный кадр** из видео, если нет `best_frame` и нет валидного `bbox` для кропа.
- **Notifications observability:** добавлены логи источника превью (`best_frame` / `bbox_crop` / `full_frame` / `none`) и метрика Prometheus `birdlense_notify_preview_24h{source=...}` по данным `activity_log` за 24 часа.
- **Статус MQTT в шапке:** при работающем процессоре индикатор берёт **`mqtt_connected` из heartbeat** (тот же клиент, что Frigate/BirdNET). Дополнительно: проверка из веб-процесса ждёт до ~2 с после `loop_start()` и нормализует `mqtt.port` в int — меньше ложных «ошибок» из-за гонки.
- **UI (страница видео):** кнопки «предыдущая / следующая запись» не работали из‑за обращения к несуществующей переменной `listReturnState` (**ReferenceError** в обработчике). Исправлено: `useLocation()`, сохранение `state.from` при переходе к соседним роликам (как с Timeline / Unknowns). Журнал проверок: [VERIFICATION.ru.md](docs/VERIFICATION.ru.md) / [EN](docs/VERIFICATION.md).
- **UI / доступ:** `GET /api/ui/settings/check-access` всегда отвечает **200** с `{ unlocked: false }`, если сессия не разблокирована (раньше **403** — шум в консоли браузера). Защищённые POST/PATCH по-прежнему возвращают 403 без сессии.
- **Processor:** при **single_stage** и **80 классах COCO** детекция по умолчанию только **животные** классы (без person и без предметов): `processor.single_stage_coco_animals_only_auto` (по умолчанию true; читается и устаревший `single_stage_coco_bird_only_auto`, если новый ключ не задан).

### Changed

- **UI:** Migration — режим периода «по годам» **или** «по датам» (без одновременного показа четырёх полей). «Поддержать» в шапке на **всех** страницах (включая главную): **сердце** с анимацией пульса, то же в мобильном меню и в меню шестерёнки.
- **UI:** запрос `settings-check-access` в React Query — `staleTime` 60 с, меньше лишних refetch при навигации.
- **CI / Deploy:** workflow **Deploy** — `concurrency` (один активный деплой на `main`), `timeout-minutes: 45`, `permissions: contents: read`; шаг **Verify** падает с `exit 1`, если health недоступен (раньше только печатался FAIL). **upload-artifact** в CI и E2E → **v6** (Node 24, без предупреждения о Node 20). **INSTALL** / **RU:** пояснение про **Queued** и fallback `make deploy`. Rsync в autodeploy — добавлен `--exclude=app/.env`.
- **Зависимости / безопасность:** `app/ui` — `npm audit fix` (транзитивные обновления, в т.ч. brace-expansion, picomatch, yaml, цепочка до `serialize-javascript`); **`requests[socks]==2.33.0`** в `app/web/requirements.txt` (SOCKS-прокси для Telegram); `requests` **2.33.0** в `app/processor/requirements.txt`. **scripts/setup-auto-deploy.sh** — скачивание runner по **последнему** релизу с GitHub API, `RUNNER_ALLOW_RUNASROOT=1` под root, `./config.sh` с `--unattended --replace`.
- **CI / Deploy:** шаг **Verify** — порт из `BIRDLENSE_PORT` в `app/.env` на сервере (иначе 8085), пауза 10 с и до **36** попыток `curl` с интервалом 5 с после `make pull` (старт контейнера и приложения). Smoke workflow — исправлен маппинг порта контейнера (8080, по умолчанию entrypoint).
- **Процесс / документация:** закрыт открытый хвост issues ([#114](https://github.com/Gfermoto/BirdLense-Hub/issues/114), [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118), [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125), [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163)–[#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167)): ворота UX-контекста для `area:web` в [CONTRIBUTING.md](CONTRIBUTING.md) / [RU](CONTRIBUTING.ru.md); E2E — итеративное расширение в [TESTING.md](docs/TESTING.md) / [RU](docs/TESTING.ru.md); идеи зафиксированы в [ROADMAP.md](docs/ROADMAP.md) / [RU](docs/ROADMAP.ru.md) (новый issue при появлении объёма).

### Added

- **Settings / UI:** поля в веб-настройках для прокси и сети Telegram (`notifications.telegram_proxy_url`, API base, таймауты, сжатие фото); post-roll и блок «несколько камер + BirdNET MQTT» (`processor.*`); зарезервированные **весы** `integrations.scales.*` (топик сохраняется, обработка — позже, [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167)). Web: зависимость **`requests[socks]`** для SOCKS5h.
- **Processor ([#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157)):** `processor.post_record_seconds` — post-roll: увеличивает паузу без детекций перед остановкой записи (сумма с `max_inactive_seconds`).
- **Processor ([#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129)):** опционально `processor.birdnet_mqtt_auto_confidence` и параметры окна/дельты — более низкий порог классификатора для видов из недавних сообщений BirdNET по MQTT (по умолчанию выкл.).
- **Processor ([#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153)):** `processor.multi_camera_groups` + `multi_camera_confidence_boost` — при Frigate-событиях одного вида с двух камер из группы прибавка к `confidence` после merge.
- **Roadmap:** пункт консилиума **№17** — стратегия детекции (two_stage vs single_stage+COCO, пороги в `user_config`, дообучение бинарника); блок в [ROADMAP.ru.md](docs/ROADMAP.ru.md) / [EN](docs/ROADMAP.md), связь с [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163). Дополнено: **чеклист «не забыть»** перед/после консилиума; раздел **«Завершение задач → тестирование оператором»** (`#completion-then-operator-testing`).
- **E2E ([#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118)):** `app/e2e/tests/migration.spec.ts` — фильтр года на Migration и сброс на «все годы»; [TESTING.md](docs/TESTING.md) / [RU](docs/TESTING.ru.md) — отладка отдельного файла (`playwright test` / `--debug`).

## [0.2.9] - 2026-03-28

Релиз доступности и регрессионных проверок. Merge: [#187](https://github.com/Gfermoto/BirdLense-Hub/pull/187), закрыт [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117).

### Added

- **Accessibility ([#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117)):** skip link to `#main-content`, shared `:focus-visible` ring in the MUI theme, migration table `caption` and labeled filter region, status dots as `role="img"` with `aria-label`, darker Live button for WCAG contrast; E2E axe scans in `app/e2e/tests/a11y.spec.ts` (`@axe-core/playwright`); [A11Y.md](docs/A11Y.md) / [RU](docs/A11Y.ru.md). Follow-up: `filledPrimary` Chip color (#047857), info `Alert` link/button contrast, migration heatmap cells (border + light tint), `Avatar` `imgProps.alt`, default `aria-label` on `CircularProgress`, overview species legend chips (`data-testid` + keyboard) for stable E2E.

## [0.2.8] - 2026-03-28

Накопительный релиз после **v0.2.7**: страница «Система» (метрики, история, посетители), донаты в UI, eBird/датасет/реестр видов и волна багфиксов. Merge: [#185](https://github.com/Gfermoto/BirdLense-Hub/pull/185).

### Changed

- **Документация:** [FEATURES](docs/FEATURES.md) / [RU](docs/FEATURES.ru.md) и [API](docs/API.md) / [RU](docs/API.ru.md) — эндпоинты «Система»: live-метрики, `/system/metrics/history`, `/system/visitors`.

- **Система / UI:** метрики хоста (`GET /api/ui/system/metrics`) отделены от статистики посетителей (`GET /api/ui/system/visitors?days=…`); смена периода посетителей больше не перезапускает опрос CPU; на странице «Система» — накопительные графики за сессию просмотра (опрос 5 с); убраны карточки кодирования/MQTT; ссылка «Поддержать» в шапке и мобильном меню скрыта на главной (остаётся карточка «Корм» и пункт в меню шестерёнки). Prometheus `/metrics` не выполняет лишних запросов по посетителям.

- **Система / история метрик:** таблица `system_resource_sample`, фоновый sampler (~30 с, хранение 72 ч, отключается `DISABLE_SYSTEM_METRICS_SAMPLER`), `GET /api/ui/system/metrics/history`; графики на «Системе» — серия с сервера + «хвост» живого опроса, выбор окна 6/24/48 ч. Интервал и хранение: `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC`, `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS`; см. CONFIGURATION, `app/.env.example`.

- **Доки деплоя / MCP:** основная площадка в правилах и примерах — LAN **192.168.1.11:22**, UI **http://192.168.1.11:8085/**, MCP **`http://192.168.1.11:8085/mcp`**; публичный хост birdlense.eyera.info оставлен как альтернатива в `deploy.local.sh.example` и MCP_SETUP.

### Added

- **Региональный топ eBird: авто-пороги классификатора ([#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128)):** процессор подмешивает в эффективные `species_confidence_overrides` виды из топа региона (после `ebird.species_mapping`) с порогом `max(floor, min_confidence_to_process − delta)`; ручные строки важнее; ключи `processor.ebird_regional_top_*`; `PYTHONPATH` процессора включает `/app/web`; см. [CONFIGURATION.md](docs/CONFIGURATION.md).

- **eBird species mapping hints ([#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136)):** `GET /api/ui/settings/ebird-species-mapping-suggestions` и кнопка в настройках — подсказки строк для `ebird.species_mapping` по региональному топу eBird vs каталог; общий кэш топа с фильтром «Региональные» в `ebird_region_service`; см. [CONFIGURATION.md](docs/CONFIGURATION.md).

- **Bird Directory regional filter ([#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132)):** «Региональные» строятся по топу eBird для региона из настроек (как Migration) и по видам с детекциями BirdNET MQTT; в ответе `GET /api/ui/species` — `regional_scope`; кэш списка eBird ~30 мин; дока в [CONFIGURATION.md](docs/CONFIGURATION.md).

- **Donation / support surfaces ([#121](https://github.com/Gfermoto/BirdLense-Hub/issues/121)):** при заданном `general.donate_url` ссылка «Support» / «Поддержать» в шапке (desktop), в мобильном меню и в меню шестерёнки; общий кэш `feed-info` с карточкой Food на Overview; i18n EN/RU/DE; [CONFIGURATION](docs/CONFIGURATION.md) / [ACCESS_CONTROL](docs/ACCESS_CONTROL.md).

- **Bird food catalog ([#134](https://github.com/Gfermoto/BirdLense-Hub/issues/134)):** расширен дефолтный список кормов (в т.ч. EU: fat balls, hemp seed, oats, mixes, rapeseed, apple); `seed_bird_food()` идемпотентно добавляет только отсутствующие по `name`; дока в [CONFIGURATION.md](docs/CONFIGURATION.md) / [RU](docs/CONFIGURATION.ru.md); тест `test_bird_food_seed.py`.

- **Production secrets runbook ([#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)):** [SECRETS_ROTATION.md](docs/SECRETS_ROTATION.md) / [RU](docs/SECRETS_ROTATION.ru.md) — перечень env/YAML, порядок ротации, проверка, откат, шаблон экстренной заметки; ссылки из [SECURITY.md](docs/SECURITY.md), [CONFIGURATION.md](docs/CONFIGURATION.md), MkDocs nav.

- **Release hygiene ([#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120)):** `scripts/check-docs-version.py` сверяет корневой `VERSION` с `mkdocs.yml`, `app/ui/package.json` и `app/web/openapi.yaml`; чеклист в [VERSIONING.ru.md](docs/VERSIONING.ru.md) / [EN](docs/VERSIONING.md); шаг в CI `openapi-contract`.

- **Species registry (backend):** сервис нормализации видов, API под админ/систему, smoke `test_species_registry.py` и шаг CI в `openapi-contract`; операторская дока в [TESTING.ru.md](docs/TESTING.ru.md).
- **Dataset export (train-ready):** `dataset_info.json` v2 с `manifest` и `quality`, опциональный `test` split в UI, query `test_ratio` / `strict_quality` на `GET /api/ui/dataset/export`, smoke `test_dataset_export_service.py` в CI; описание в [DATASETS.ru.md](docs/DATASETS.ru.md).
- **Документация:** подготовительный чеклист перед реализацией [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) / [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) — [PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md](docs/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md) / [EN](docs/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md); ссылка из [ROADMAP](docs/ROADMAP.ru.md).
- **#54 (CI):** контрактный смоук OpenAPI — новый тест `app/web/tests/test_openapi_contract.py` и job `openapi-contract` в `.github/workflows/ci-pr.yml` (гейт на PR/push в `main`/`dev`).
- **#55 (Migration):** life list / «виды за год» покрывается самой таблицей миграции (фильтр по годам + строки и столбец Σ); отдельный дублирующий блок-чеклист на странице убран.
- **#81 (phase C):** единый журнал ручных правок Unknowns/Video — backend activity `species_correction` + endpoint `GET /api/ui/corrections/recent` + блок последних правок на странице Unknowns.

### Changed

- **Волна A (bugs):** [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) ретроэкспорт с периодом подхватывает сирот без `Video`; retention каскадно удаляет `VideoSpecies`/`SpeciesVisit` как при API удалении записи. [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) poll regenerate spectrograms/tracks с timeout 120s. [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) после удаления видео — возврат по `state.from` или на `/library`.
- **Dataset export:** при `strict_quality=1` и **ready_for_train** экспорт отменяется, если хотя бы один класс не прошёл `min_images_per_class` (явный отказ вместо тихого пропуска); чекбокс в Library; см. [DATASETS.ru.md](docs/DATASETS.ru.md).
- **CodeQL / code scanning:** устранены открытые Python-алерты без «принятия риска» — `urlparse` для источников метаданных, линейный разбор скобок вместо ReDoS-регекса, `_safe_image_path_or_none` для Telegram crop, `mkstemp` в спектрограмме, редактирование URL в логах go2RTC; тесты `test_util_metadata.py`; см. [CODEQL.ru.md](docs/CODEQL.ru.md).
- **Migration UI:** убран дублирующий блок «чеклист за год» над таблицей — те же виды и суммы уже есть в таблице миграции.
- **#56 (CORS config):** demo-host удалён из hardcoded CORS defaults; теперь базовые non-localhost origins задаются через `CORS_DEFAULT_ORIGINS` (и runtime `CORS_ORIGINS`), что безопаснее для self-hosting.

## [0.2.7] - 2026-03-23

### Changed

- **Отчётность:** без отдельных страниц `PROJECT_REPORTING*` — правила в [docs/ROADMAP.md](docs/ROADMAP.md) / [RU](docs/ROADMAP.ru.md) и [CONTRIBUTING](CONTRIBUTING.md) / [RU](CONTRIBUTING.ru.md); вести **Issues** и доску, не дублировать политикой в `docs/`.
- **Доки окружения:** прод-UI **https://birdlense.eyera.info/**, SSH **185.218.111.196:2222** — [`.cursor/rules/deploy.mdc`](.cursor/rules/deploy.mdc), [MCP_SETUP](docs/MCP_SETUP.md) / [RU](docs/MCP_SETUP.ru.md), пример [`scripts/deploy.local.sh.example`](scripts/deploy.local.sh.example).
- **#85 (video neighbors):** `GET /api/ui/videos/:id/neighbors` теперь поддерживает локальный день (`day_scope=local`, `tz_offset_minutes`) и опциональный переход на соседние сутки (`cross_day`); UI страницы видео использует локальный режим по умолчанию.
- **#50 (processor MQTT resilience):** MQTT-клиент процессора использует встроенный reconnect/backoff paho (`reconnect_min_delay`/`reconnect_max_delay`), а в конфиг/доки добавлены параметры и пояснение про пропуски live-событий при обрывах.
- **Settings UI (MQTT):** в форму добавлены `publish_topic`, `reconnect_min_delay`, `reconnect_max_delay` для полной настройки MQTT без ручного редактирования YAML.
- **CI/процесс:** `settings-ui-coverage` расширен метаданными зрелости для non-UI ключей (`ops-only`, `advanced`, `backend-managed`, `planned-ui`) с `reason` и `next_step`; это даёт прозрачный план эволюции настроек, а не только pass/fail.
- **#51 (операторский UX):** в System добавлены безопасные `SQLite backup/restore` (скачивание бэкапа и восстановление из файла с авто-`pre_restore` копией), плюс документация в INSTALL/TROUBLESHOOTING.
- **#52 (UI i18n):** добавлена пилотная третья локаль `de` (German) в `react-i18next`, улучшен выбор стартового языка (saved/browser/fallback), переключатель языка теперь полностью через i18n-ключи.
- **#107 (Overview stats):** карточка «Средняя длительность» / Mean recording duration считает среднюю длительность **одной записи** (`Video`), а не среднюю длительность визита (`SpeciesVisit`), чтобы метрика соответствовала названию.

### Added

- **Project hygiene:** скрипт `scripts/github-project-sync.sh` для автосинхронизации доски (Status/Поток по состоянию issue, auto-assignee для open задач без исполнителя, отчёт по open задачам без checklist-подзадач).
- **#53 (CI):** workflow `.github/workflows/docker-image-smoke.yml` — ежедневный smoke-тест опубликованного `ghcr.io/<owner>/birdlense-hub:latest` (pull/run + проверка `/api/ui/health`).
- **#48:** скрипт `scripts/datasets/export_birdlense_to_yolo.py` — экспорт локальных кропов BirdLense (`app/data/dataset/train`) в YOLO classification layout `train/val` с детерминированным split и `dataset_info.json`.
- **#47 (maintainer hygiene):** скрипт `scripts/security/scan_git_history_secrets.sh` для прохода по полной git-истории через Gitleaks (Docker) + документированный процесс в [SECURITY](docs/SECURITY.md) / [RU](docs/SECURITY.ru.md).

## [0.2.6] - 2026-03-23

Накопительный релиз после **v0.2.5**: CI CodeQL, навигация по видео **#82**, деплой/Web Push, сопутствующие доки и инфраструктура репозитория.

### Fixed

- **Деплой:** rsync исключает **`.tools/`** (локальный CodeQL из `scripts/codeql-local.sh`) — не заливать гигабайты на сервер.
- **Деплой (`scripts/deploy.sh`):** rsync исключает `.venv-docs-tmp`, `.venv-docs`, `site/`, `app/.venv` — не заливать локальные venv на сервер.
- **Web Push:** при битых **p256dh/auth** или пустых ключах подписка **удаляется** из БД (раньше — предупреждение в лог на каждую отправку); pytest `web/tests/test_web_push_service.py`.
- **Gallery:** приём ответа приёмника **201** и **204** (раньше только 200); при отсутствии подходящих детекций — **INFO** в лог с причинами фильтра.
- **Страница вида `/species/:id`:** валидация id; при **404** — понятное сообщение и ссылка в каталог; пустые **weather** / некорректная длина **hourlyActivity** не ломают графики (MUI Charts). API summary: обновление из Wikipedia обёрнуто в **try/except**, чтобы сеть/БД не отдавали «мёртвую» страницу.
- **Unknowns ↔ видео:** после смены вида или merge на странице видео список «Неизвестные» больше не «залипает» на старых данных (инвалидация **`['unknowns']`** в `DetectedSpecies`; раньше кэш жил до 5 минут).
- **Удаление видео:** сначала **коммит** в БД, затем удаление папки записи на диске — при ошибке транзакции файлы не удаляются; после удаления — сброс кэша **`video` / `video-neighbors` / `videos`** и инвалидация соседей по дню.
- **CI:** сайт документации — без workflow на `release` (деплой только с `main`), чтобы не было failed deployment в списке при теге.

### Added

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — полный цикл работы для мейнтейнеров (тесты, CHANGELOG/docs, push, PR, `make deploy`).
- **CI: CodeQL** — workflow `.github/workflows/codeql.yml` (Python `app/web` + `app/processor`, TypeScript `app/ui/src`), конфиги `.github/codeql/`; доки [CODEQL](docs/CODEQL.md) / [RU](docs/CODEQL.ru.md), пункты в mkdocs и SITE_MAP; рекомендация расширения **GitHub.vscode-codeql** в `.vscode/extensions.json`; скрипт **`scripts/codeql-local.sh`**; `.gitignore`: **`.tools/`** (локальный CLI, БД, SARIF); в доке — пример triage последнего локального прогона.
- **#82**: на странице видео — кнопки «предыдущий / следующий» ролик за тот же календарный день UTC, что и `start_time`; API `GET /api/ui/videos/:id/neighbors` (`previous_id`, `next_id`, `index`, `total`, `day_utc`).
- Скрипт `scripts/github-project-mark-done.sh` — пометить issue на доске **BirdLense Hub — Roadmap** как **Done** (поля **Status** и **Поток**); см. [CONTRIBUTING](CONTRIBUTING.md).
- Примеры алертинга Prometheus: `examples/prometheus/birdlense.rules.yml`, `examples/prometheus/alertmanager.birdlense.example.yml`; раздел **Alerting** в [CONFIGURATION](docs/CONFIGURATION.md) / RU — закрывает [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).
- `app/ui/package.json`: поле **`engines`** (Node **22.x**, минимум **22.13**; npm **>=10**) — согласовано с CI и UI Docker stage.
- `.vscode/extensions.json` — рекомендуемые расширения (ESLint, Prettier, Docker).
- CI: workflow **`E2E (Playwright)`** (`.github/workflows/e2e-scheduled.yml`) — раз в неделю + `workflow_dispatch`; **не** required в ruleset.
- CI: job **`docker-tests`** — сборка образа `birdlense` + `make test` + `make test-web` на каждый PR/push в `main` и `dev` (см. [TESTING](docs/TESTING.md)); в ruleset **Protect** на `main` required checks: **`ui-build`**, **`docs`**, **`docker-tests`**.
- Скрипты GitHub Project: `scripts/github-project-pat-hint.sh`, загрузка `scripts/.env.project`, шаблон `scripts/env.project.example` — **classic PAT** вместо OAuth refresh (без круга device-login).
- Roadmap: секция **Backlog consilium (March 2026)** + 11 активных GitHub Issues [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) для доски Project ([#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) ARM — вне скоупа).
- CI: workflow `prune-branches.yml` — опционально, только **`workflow_dispatch`**: снятие с `origin` веток кроме **`main`** и **`dev`** (без cron; обычная уборка — после merge PR).
- Скрипт `scripts/github-project-add-backlog-consilium.sh` — добавить issues **#46–#57** на доску Project, с пропуском **#49** по умолчанию (`GITHUB_BACKLOG_SKIP_ISSUES`; нужен scope `project` у `gh`).
- `.github/github-social-preview.png` — Open Graph / Social preview для репозитория (1280×640).

### Changed

- **Репозиторий:** в git добавлено **`.cursor/rules/deploy.mdc`** (шаблон деплоя для локальной среды); в **`.gitignore`** — исключение только для этого файла, остальной `.cursor/` по-прежнему не коммитится.
- **CI: CodeQL** — `github/codeql-action` **v3 → v4** ([changelog GitHub](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/)): без предупреждений о Node 20 и deprecation v3 на раннере.
- **Доки CodeQL** (EN/RU): `workflow_dispatch`, **codeql-action@v4** в вводном абзаце; установка расширения в VS Code (CLI, VSIX, ID **`GitHub.vscode-codeql`**). **`.vscode/extensions.json`** — тот же ID издателя.
- ROADMAP (EN/RU): бэклог оператора — issues [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (галерея), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (коррекция видов Unknowns ↔ видео), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (навигация по видео); карточки на Project **BirdLense Hub — Roadmap**.
- Безопасность [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46): rate limit `POST /api/ui/settings/verify-password` — IP клиента за nginx (`client_ip_for_rate_limit`: `X-Real-IP`, `X-Forwarded-For`; nginx передаёт оба для `/api` и `/metrics`), сброс счётчика при успешном входе, **`Retry-After`** при **429**; pytest `TestVerifyPasswordRateLimit`; доки ACCESS_CONTROL / API / SECURITY / TESTING / OPEN_SOURCE_PREP / ROADMAP.
- Политика платформы: **официально только x86/amd64** (Intel/AMD); ARM / aarch64 не поддерживаются и не планируются — ROADMAP, доки, конфиг; бэклог без ARM64 Docker ([#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49)).
- ROADMAP (EN/RU): **триаж** Issue vs Discussion; **Future work candidates** (a11y, E2E, секреты, версии стека, community/donation UX); таблица идей переименована в **Shipped ideas (archive)**; UX-блок выровнен; [ACCESS_CONTROL](docs/ACCESS_CONTROL.md) ссылается на кандидатов.
- `chore(deps)`: **@mui/x-charts** 7.x → 8.x в `app/ui` ([#42](https://github.com/Gfermoto/BirdLense-Hub/pull/42)).
- `.gitignore`: `app/data/processor.log*` — ротированные логи процессора не коммитятся.
- GitHub: модель веток — **фича → PR в `dev`**, затем **PR `dev`→`main`**; CONTRIBUTING + шаблон PR; `delete_branch_on_merge=true` (фичи не копятся, `main`/`dev` защищены от удаления). `github-repo-bootstrap.sh` и [GITHUB_SETUP_GH.ru.md](docs/GITHUB_SETUP_GH.ru.md) §4 обновлены.
- Доки: INSTALL ↔ `scripts/deploy.sh` (контейнер `birdlense`, `DEPLOY_REMOTE_DIR`, rsync, Intel override, исключение **`.tools/`**); пример `deploy.local.sh.example` с `DEPLOY_REMOTE_DIR`; SCENARIOS.ru (Grafana) как в EN; OPEN_SOURCE_PREP.ru — актуальный блок про плейсхолдеры; README / I18N_STATUS / SITE_MAP — формулировки под MkDocs; пути клон `BirdLense-Hub` vs каталог на сервере.
- `app/Makefile`: комментарии деплоя и E2E без захардкоженного LAN IP.
- GitHub: ruleset **Protect** на default branch — обязательны успешные checks **`ui-build`** и **`docs`** (workflow CI); approvals по-прежнему 0 (solo).
- Dependabot — не больше **одного открытого PR на блок** (`open-pull-requests-limit: 1`).
- Локально: remote **`upstream`** к стороннему репозиторию не используется (репозиторий на GitHub — не форк).
- Доки: [LOCAL_DEV](docs/LOCAL_DEV.md) / RU — Node 22 (nvm/fnm/Volta), WSL / VS Code, Python **3.11** (приложение) vs **3.12** (MkDocs), venv для доков, чеклист перед релизом; [TESTING](docs/TESTING.md) / RU — предупреждение про RAM и OOM при `make test`, workflow E2E по расписанию; [Documentation](docs/Documentation.md) / RU — явное разделение Python для MkDocs и runtime; [CONTRIBUTING](CONTRIBUTING.md) / RU — PR: полный набор тестов; [README](README.md) / RU — блок **Developers**.

---

## [0.2.5] - 2026-03-23

### Added

- **#81** (фаза B): на странице **Неизвестные** после успешной коррекции вида или «Верно» — в уведомлении действие **«Открыть видео»** (по умолчанию остаётесь в списке; при наличии `video_id` snackbar дольше открыт). См. [UX_UNKNOWN_VIDEO_CORRECTION](docs/UX_UNKNOWN_VIDEO_CORRECTION.md).

---

## [0.2.4] - 2026-03-22

### Fixed

- **#80** (галерея): фоновая загрузка кадров после `POST /api/processor/videos` выполняется внутри **Flask app context** — иначе SQLAlchemy не видел сессию и загрузки не происходили. Логи: `Gallery upload thread failed` при прочих ошибках.
- **Web Push:** `notify_app_startup` вызывает `notify()` внутри **app context** — устранено предупреждение `Working outside of application context` при старте, если включены push и есть подписки.

### Added

- Тесты `app/web/tests/test_gallery_upload.py`; смок галереи в [TESTING](docs/TESTING.md) §2.6 / [TESTING.ru](docs/TESTING.ru.md) §8; troubleshooting в [CONFIGURATION](docs/CONFIGURATION.md) → Gallery.
- Спецификация UX [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81): [UX_UNKNOWN_VIDEO_CORRECTION](docs/UX_UNKNOWN_VIDEO_CORRECTION.md); фаза A: подсказки в справке Unknowns / Video details (i18n EN/RU).

---

## [0.2.3] - 2026-03-20

### Added

- GitHub: Discussions/Issues/labels/milestones; скрипты bootstrap/import для Project (опционально).
- CI: PR — сборка UI + strict MkDocs; Redoc для OpenAPI в `docs/reference/`.
- Docs: `SHORT_DESCRIPTION` EN/RU; `app/README` EN/RU.

### Changed

- Обновлены версии GitHub Actions (checkout, setup-*, upload-*, Docker).

### Fixed

- Pages и Docker: корректные триггеры на **published** Release (`latest`, деплой сайта).
- MkDocs: баннер и версия в шапке от `VERSION` / `extra.site_version`; ROADMAP EN без ложного бэклога; strict — внешние ссылки на blob.

---

## [0.2.2] - 2026-03-20

### Added

- **Документация:** статический сайт (MkDocs + GitHub Pages), карта и i18n; отчёт **Wiki report** в Actions (Summary, артефакт, опционально push в GitHub Wiki).
- **Сообщество:** `GOVERNANCE`, `CODEOWNERS`, шаблон PR; инструкция настройки репозитория через `gh` (`GITHUB_SETUP_GH`); `WIKI_AUTOMATION`; черновик материала в `docs/article/habr.md`.

### Security

- **npm (UI):** обновлена транзитивная зависимость `flatted` (GHSA high / prototype pollution).

### Fixed

- Push в GitHub Wiki: проверка `has_wiki`, понятные ошибки; bootstrap без флага `--disable-wiki` в старых версиях `gh`.

### Changed

- В bootstrap репозитория Wiki включается через API (`has_wiki=true`).

---

## [0.2.1] - 2026-03-19

### Added

- **Prometheus /api/metrics** — эндпоинт для Grafana (CPU, память, диск, GPU, detections, species, videos).
- **Intel GPU метрики** — карточка GPU в System, `gpu_percent` из sysfs/intel_gpu_top.

### Changed

- **Документация** — консолидация: TROUBLESHOOTING в один файл, MQTT/Gallery/Detection в CONFIGURATION, INSTALL+DEPLOYMENT+DEPLOY_USER в INSTALL, TRAINING+HUGGINGFACE в TRAINING. Удалены дубли, архив сокращён.
- **Подсказка кодирования** — убрано «(NUC, Celeron и др.)» из UI.

---

## [0.2.0] - 2026-03-18

### Added

- **Публичная галерея** — тестовый контейнер `docker/gallery-test` для проверки загрузки кадров.
- **Порог бинарного детектора** — настраиваемый `processor.min_confidence_binary` (по умолчанию 0.25) для снижения ложных срабатываний.
- **PWA: prompt при обновлении** — Snackbar «Доступна новая версия» вместо автоматической перезагрузки.

### Changed

- **Пороги детекции** — повышены по умолчанию: `min_confidence_to_process` 0.15, `min_track_duration` 3 сек, `min_confidence_to_store` 0.10.
- **Шрифты** — Google Fonts загружаются асинхронно (не блокируют рендер, быстрее в РФ).
- **Telegram** — retry, увеличенный timeout, fallback на текст при ошибке фото, сжатие изображений.

---

## [0.1.10] - 2026-03-17

### Changed

- **Overview** — grid вместо flex для Feed+Chart (стабильный layout при логине).
- **FeedCard** — подсказка «Кнопка доступна администратору. Волонтёры могут помочь с видами» вместо «Введите пароль настроек».
- **ProtectedRoute** — универсальное сообщение «Введите пароль администратора для доступа к этому разделу» для Settings, System, Library.

### Security

- **Ограничения для не залогиненных** — PDF-отчёт, экспорт (CSV/JSON/eBird/Dataset), изменение корма в кормушке доступны только после входа (admin или contributor для экспорта; admin для корма).

---

## [0.1.9] - 2026-03-17

### Added

- **Карточка «Сравнение с регионом»** — показ списков видов: ваши виды в топе региона и полный топ региона по eBird.

### Changed

- **Unknowns** — выбор даты и времени суток как в Записях (DatePicker + Утро/День/Вечер/Ночь вместо прокрутки по часам).
- **timeUtils** — общий `getTimeRange` для Timeline и Unknowns.

---

## [0.1.8] - 2026-03-17

### Added

- **Unknowns — подсказка про выбор часа** — при выборе времени (не 00:00) показываются только детекции за выбранный час.
- **E2E smoke-тесты** — Overview, Timeline, Unknowns, System.

### Changed

- **Unknowns** — убрано дублирование заголовка и описания (остаётся только PageHelp).
- **PDF-отчёт** — брендинг BirdLense Hub, шапка/футер на каждой странице, Executive Summary, секция «About this report».
- **Зависимости** — @mui/system для сборки, keyframes из @emotion/react.

---

## [0.1.7] - 2026-03-16

### Added

- **«Применить ко всем в видео»** — массовая коррекция: выбрать вид и объединить все детекции в одном видео (удобно при разных нейросетях или прерываниях).
- **«Исправить счётчики»** — Система → Управление хранилищем: удаляет осиротевшие визиты и синхронизирует species_id. Исправляет некорректные счётчики в календаре и каталоге после коррекций.

### Changed

- **Навигация** — короткие подписи: «Миграции», «Каталог», «Food», «Species».
- **Календарь миграций** — убрано дублирование заголовка (остаётся только PageHelp).
- **TG-фото** — отправка через base64 вместо пути к файлу (надёжнее при любом деплое).
- **Инвалидация кэша** — при коррекции видов обновляются migration-calendar, bird-directory, species, speciesSummary.

### Fixed

- **Счётчики после коррекции** — календарь миграций и каталог птиц теперь обновляются при исправлении видов.

---

## [0.1.6] - 2026-03-16

### Added

- **Кнопка «Скачать видео»** — только для админа и помощника (contributor_or_admin_access), после ввода пароля.
- **TG-превью best frame** — в уведомлениях Telegram отправляется фото лучшего кадра детекции.

### Changed

- **Секреты в production** — FLASK_SECRET_KEY, PROCESSOR_SECRET, BIRDLENSE_ENV задаются через deploy.local.sh и записываются в app/.env на сервере.
- **deploy.sh** — запись секретов без дубликатов (grep -v -E).

### Security

- **image_path** — валидация _is_safe_image_path перед отправкой в Telegram.

---

## [0.1.5] - 2026-03-15

### Added

- **lastDetection по end_time** — виджет «Последняя птица» показывает последнее по времени наблюдение (order_by end_time), не первое.
- **Bird = неопределённый объект** — «Bird»/«bird» без вида не считается в overview (топ, статистика), всегда в Unknowns.
- **MQTT merge по timestamp** — MQTT-события используют реальное время (не растягивают на всё видео).
- **Унификация окон merge** — visit_timeout = dedup_window_seconds (45 сек по умолчанию).

### Fixed

- **Code review fixes** — `datetime.now()` → UTC в Overview и activity; `logger.warn` → `logger.warning`; `request.json or {}` в purge_storage; валидация `species_id` (int).
- **Race при регенерации** — блокировка повторного запуска (409 если уже running).
- **Path traversal** — проверка формата video_path в detection_crop_service.

### Refactored

- **parse_utc_timestamp** — утилита для парсинга timestamp.
- **get_primary_video_for_visit**, **format_visit_for_timeline** — хелперы для timeline.
- **overview_service** — вынос логики Overview в сервис.
- **species_summary_service** — вынос логики species summary в сервис.
- **Константы** — LOG_LINES_DEFAULT/MAX, UNKNOWNS_LIMIT_MAX.
- **API.md** — добавлены dataset/export, push/*, статус unknown.

### Added (ранее)

- **Роли доступа** — два пароля: `settings_password` (Admin), `contributor_password` (помощник). Contributor: коррекция видов, iNaturalist, отчёты, экспорт датасета. Admin: кормушка, настройки, система. Документ [ACCESS_CONTROL.md](docs/ACCESS_CONTROL.md).
- **Датасет из лучших кадров** — сохранение best_frame в `data/dataset/train/<Species>/` для экспорта и дообучения. Конфиг `processor.save_dataset_crops: true`, `processor.dataset_min_confidence` (по умолчанию 0.5). API `GET /api/ui/dataset/export` — ZIP с train/val и dataset_info.json. Кнопка «Экспорт датасета» в Система → Управление хранилищем. При коррекции вида в Unknowns/VideoDetails файл перемещается в директорию нового вида.

### Changed

- **Кормушка** — кнопка «Выдать корм» защищена паролем Admin. Без разблокировки кнопка неактивна.
- **Экспорт датасета** — доступен в Timeline (для Contributor) и в Система (для Admin).

---

## [0.1.4] - 2026-03-15

### Added

- **eBird export** — экспорт списка видов в формате eBird Record для импорта в eBird.org. Кнопка «Экспорт для eBird» в Timeline. Настройки: Настройки → Расширенные (страна, регион, локация).
- **Confidence по виду** — пороги `min_confidence` по видам. Редкие виды — ниже порог. Конфиг `processor.species_confidence_overrides: {"Species Name": 0.05}`. Настройки → Processor.
- **Экспорт в iNaturalist** — кнопка «Отправить в iNaturalist» на карточке детекции (Timeline) и на странице видео. Скачивает кадр из видео и открывает inaturalist.org/observations/upload. API: `GET /api/ui/detections/:id/crop`.

### Changed

- **Timeline** — выбор даты + время суток вместо дата+час. DatePicker без прокрутки по часам. Добавлена Ночь (22–06) для ночных птиц.

---

## [0.1.3] - 2026-03-15

### Added

- **Prometheus метрики** — эндпоинт `GET /metrics` в формате Prometheus: `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total`. Для Grafana и дашбордов.
- **«Неизвестные»** — страница `/unknowns` со списком детекций с низкой confidence (< порога). Ручная проверка и исправление вида. Порог настраивается в Настройках → Расширенные или в конфиге `ui.unknown_confidence_threshold` (по умолчанию 0.5).
- **PDF-отчёт** — месячный отчёт: N видов, топ-5, графики. Кнопка «PDF-отчёт» на Overview. API: `GET /api/ui/report/pdf?month=YYYY-MM`.
- **Bird song player (Xeno-canto)** — кнопка «Воспроизвести песню» на странице вида. API v3, ключ в Настройки → Расширенные. Fallback: ссылка на поиск xeno-canto.org при отсутствии ключа. API: `GET /api/ui/species/:id/xeno-canto`.

---

## [0.1.2] - 2026-03-14

### Added

- **Playback speed (0.5x, 2x)** — кнопки в видеоплеере для замедления/ускорения просмотра.
- **Виджет «Последняя птица»** — блок на Overview с последней детекцией дня (время и вид).
- **CSV/JSON экспорт** — кнопка экспорта в Timeline: скачать визиты за выбранный период в CSV или JSON.
- **Фильтр по времени суток** — в Timeline: Утро (6–10), День, Вечер (18–22).
- **Webhook** — POST при каждой детекции на настраиваемый URL (Настройки). JSON: species, confidence, time, source.
- **PWA** — vite-plugin-pwa: service worker, offline cache, install prompt «Добавить на главный экран».

---

## [0.1.1] - 2026-03-14

### Added

- **Источник распознавания в UI** — полосы и карточки показывают YOLO, Frigate или BirdNET. Документация: `docs/DETECTION_SOURCES.md`.
- **deploy.sh** — rsync вместо tar|ssh; автоустановка rsync на сервере; повторы при сбое (SYNC_RETRIES=3, BUILD_RETRIES=2).

### Changed

- **Консолидация детекций** — `min_confidence_to_process`: 0.03 → 0.10, `min_track_duration`: 1 → 2 сек. Меньше ложных срабатываний.
- **Рефакторинг** — удалён мёртвый код `useMockData` в api.tsx; фильтрация камер вынесена в `app_config/cameras.py`; E2E-хелперы в `e2e/helpers/settings.ts`.
- **merge_detections** — реализован `dedup_window_seconds`: детекции одного вида с разрывом > 45 сек считаются разными визитами.
- **_canonical_key** — нормализация имён с underscore (`Great_Tit`, `Parus major (Great Tit)` → один ключ для слияния).
- **birdnet_local** — заменён на `birdnet_mqtt` (audio_detections всегда пустой). `legacy` оставлен для импорта старых записей.

### Removed

- **mocks.tsx** — не использовался.
- **deploy-to-server.sh** — заменён на `make deploy`.

### Fixed

- **deploy.sh** — защита от повреждения `.env`: при размере > 1 MB файл заменяется на `.env.example`.
- **SIGPIPE при деплое** — rsync устойчивее к обрывам, чем tar|ssh.

---

## [0.1.0] - 2026-03-12

Первый стабильный релиз (без alpha/beta).

### Added

- **Telegram-уведомления** — бот отправляет сообщения в канал или чат. Настройки: токен бота, chat_id, base_url для ссылок.
- **Telegram Bot API 9.4/9.5** — кнопки с эмодзи и стилем (primary), динамическое время `<tg-time format="r">`, опция `link_preview_large` для больших превью ссылок.
- **sendPhoto** — при `processor.save_images: true` отправляется фото детекции в Telegram.
- **sendPaidMedia** — раздельные настройки: Stars за просмотр (0–25000) и за пересылку/копирование.

### Changed

- **Уведомления** — отправляются **после слияния** (YOLO + Frigate/BirdNET), а не по первому результату YOLO. Один результат на вид.
- **merge_detections** — один результат на вид (max confidence, объединённый интервал). Дедупликация YOLO-треков и MQTT-событий.
- **Уведомления** — ntfy заменён на Telegram Bot API.

### Removed

- **ntfy** — убран из nginx (порт 8081), deploy.sh, UI.

### Fixed

- **Защита по паролю** — единая точка входа при нажатии на иконку шестерёнки.
- **Картинки птиц (Wikipedia)** — resolveImageUrl() для абсолютных и относительных URL.
- **PROCESSOR_SECRET** — корректная запись в deploy.sh (printf).
- **Деплой** — env_file, health check, .env.example при первом деплое.
- **Processor API** — timeout 30s, retry при 5xx.
- **VideoPlayer** — сброс view при смене видео без спектрограммы.
- **MQTT** — reconnect при обрыве.
- **Конфиг** — валидация YAML, fallback на пустой dict.

---

## [0.1.0-beta.2] - 2026-03-11

### Fixed

- **Heartbeat** — устойчивый retry при ошибках, логирование 403 при неверном PROCESSOR_SECRET
- **Status icons** — цвета (ok=зелёный, unknown=amber)
- **E2E** — baseURL по умолчанию localhost:8085

### Changed

- **Docs** — европейские птицы, датасеты

---

## [0.1.0-beta.1] - 2026-03-10

### Added

- **Coverage** — pytest-cov, `make test-coverage`, `make test-report`
- **PROCESSOR_SECRET** — автогенерация при деплое

### Changed

- **util.py** — путь к `hierarchy_names.txt` через `__file__`
- **Makefile** — volume для test (локальный код)

### Removed

- **CPU temperature** — убрана из метрик
- **Orphan containers** — удалены старые контейнеры

### Fixed

- Web API тесты — путь к seed/hierarchy_names.txt

---

## [0.1.0-alpha.1]

Первый альфа-релиз.

[0.3.2]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.2
[0.3.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.1
[0.3.0]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.0
[0.2.6]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.2.6
[0.2.5]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.2.5
[0.2.4]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.2.4
[0.2.3]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.2.3
[0.2.0]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.2.0
[0.1.10]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.10
[0.1.9]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.9
[0.1.8]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.8
[0.1.7]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.7
[0.1.6]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.6
[0.1.5]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.5
[0.1.4]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.4
[0.1.3]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.3
[0.1.2]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.2
[0.1.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.1
[0.1.0]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0
[0.1.0-beta.2]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.1
[0.1.0-alpha.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-alpha.1
