# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Security

- **A2 / roadmap [#418](https://github.com/Gfermoto/BirdLense-Hub/issues/418):** переменная **`BIRDLENSE_HIDE_DIRECT_RECORDINGS`** (`1`/`true`/`yes`/`on`) — при старте контейнера не добавляется nginx-`location` для **`/data/recordings/`**; анонимный доступ к предсказуемым URL получает **403**, воспроизведение остаётся через **`/api/ui/videos/:id/stream`** (`app/nginx/standalone.conf.template`, `app/scripts/entrypoint.sh`). Доки: **CONFIGURATION**, **SECURITY**, **DEPLOY_SERVER** (EN/RU), **`app/.env.example`**. Публичный VPS — единый чеклист: **`docs/PUBLIC_RECORDINGS*.md`** ([#423](https://github.com/Gfermoto/BirdLense-Hub/issues/423)).

- **[#341](https://github.com/Gfermoto/BirdLense-Hub/issues/341):** на POST upload-роутах (веса процессора, file-test, restore SQLite, YAML import) отклоняется непустой **`Content-Encoding`**, кроме единственного значения **`identity`** — снижает риск decompression bomb при нетипичных клиентах (`services/upload_request_encoding_guard.py`). Путь из ревью `processor.js` / `uploads.js` в этом репозитории отсутствует; дублирующих Flask-логгеров по коду не найдено.

- **[#339](https://github.com/Gfermoto/BirdLense-Hub/issues/339):** nginx больше не отдаёт весь volume `DATA_DIR` по префиксу `/data/`. Разрешены только **`/data/recordings/`**, **`/data/images/`**, **`/data/file_test/`** (видео, картинки каталога, file-replay); остальное, включая **`/data/db/*.db`**, датасет и кэш, получает **403** (`app/nginx/standalone.conf.template`, `standalone.conf`, `default.conf`).

### Changed

- **Roadmap EN/RU:** секция **Scale / [#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424)** — статус закрытого эпика и таблица результатов B1–B3 (ссылки на доки и [#432](https://github.com/Gfermoto/BirdLense-Hub/issues/432)–[#434](https://github.com/Gfermoto/BirdLense-Hub/issues/434)).

- **Scale [#432](https://github.com/Gfermoto/BirdLense-Hub/issues/432):** процессор — наблюдаемость **`triggers.*`**: gauge в `processor_runtime_stats.json` (`trigger_cfg_*`, `trigger_mqtt_*`, `trigger_frigate_degraded_no_mqtt`, `trigger_*_paths_count`, …), счётчики fallback фабрики motion (`trigger_motion_factory_*`), обновление при старте motion-стека и connect/disconnect MQTT (`trigger_runtime_gauges.py`, `motion_runtime.py`, `mqtt_aggregator.py`, `motion_detectors/factory.py`).

- **Scale [#433](https://github.com/Gfermoto/BirdLense-Hub/issues/433):** документация — очереди/backpressure (`mqtt.publish_queue_max`, `mqtt_outbound_*`, `motion_trigger_queue_drop_total`, `feeder_scale_queue_drops_total`) в **PROCESSOR_PERFORMANCE** EN/RU, **CONFIGURATION** EN/RU (ключ `publish_queue_max`), **TROUBLESHOOTING** EN/RU.

- **Scale [#434](https://github.com/Gfermoto/BirdLense-Hub/issues/434) / epic [#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424):** операторский SSOT для PostgreSQL как БД хаба — **`archive/internal/docs-legacy/POSTGRES_MIGRATION.md`** / **`.ru.md`** (compose, `DATABASE_URL`, пул, greenfield vs миграция данных, ограничения процессорского SQLite и BirdNET FIFO); навигация **MkDocs**, **SITE_MAP** EN/RU, строки в **CONFIGURATION** EN/RU, блок в **RUNBOOKS** EN/RU.

- **A2 / roadmap [#423](https://github.com/Gfermoto/BirdLense-Hub/issues/423):** единый операторский SSOT для публичного контура записей — **`docs/user/public-recordings.md`** / **`.ru.md`**; **SECURITY** / **DEPLOY_SERVER** / **CONFIGURATION** / **ACCESS_CONTROL** сведены к перекрёстным ссылкам вместо дублирования чеклистов; **mkdocs**, **SITE_MAP**, **README** (EN/RU).

- **Деплой (доки):** явно зафиксирован сценарий **только `http://IP:порт`** без домена и без внешнего reverse proxy до появления DNS/TLS — `DEPLOY_SERVER` (EN/RU), `deploy.local.sh.example`, `.cursor/rules/deploy.mdc`, подсказка в конце `scripts/deploy.sh`.

- **A1 / деплой:** опционально **`RUN_VERIFY_PROD_BEFORE_DEPLOY=1`** в `deploy.local.sh` — перед rsync вызывается **`scripts/verify-prod-env.sh`** по локальной копии server **`app/.env`**; цель **`make preflight-deploy`** (= `verify-prod-env` + **`make verify`**). Пример базового URL VPS в **`DEPLOY_SERVER`** (EN/RU).

- **A3 / наблюдаемость CV:** в JSON-строке **`recording_session_summary`** (processor logs) добавлены поля **`duration_s`**, **`triggered_camera`**, **`yolo_frames_with_tracks`**, **`session_extended_by_frigate_only`** — проще root-cause по воронке; **TROUBLESHOOTING** EN/RU обновлены.

- **Триггеры и конфиг:** из **`default_config.yaml`** убран блок **`motion:`**; источник истины для захвата — **`triggers.*`**. Остаток **`motion:`** в пользовательском YAML при загрузке сворачивается в **`triggers`** (**`migrate_legacy_motion_block`**, **`fold_legacy_motion_out_of_merged_config`**). **`get_effective_trigger_config`** без чтения **`motion.*`** как fallback; нужен явный **`triggers.frigate.enabled`** для записи по Frigate. UI: фильтры Frigate в **`triggers.frigate.*`**. Документы ARCHITECTURE, CONFIGURATION (EN/RU), TESTING/TROUBLESHOOTING/GLOSSARY (EN/RU), CONFIGURATION_TRIGGERS_INVENTORY (EN/RU), SETTINGS_TRIGGERS_PHASE2 (EN/RU) приведены в соответствие.

- **Документация:** актуализация ROADMAP EN/RU — секция **Scale / [#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424)** (треки B1–B3: motion/triggers, очередь процессора, Postgres); дочерние issues **#432–#434**; родитель фазы [#418](https://github.com/Gfermoto/BirdLense-Hub/issues/418). Ранее в этом блоке: апрель 2026 в заголовках backlog, UI видов **v0.3.7+**, outcome эпика реестра; SECURITY EN/RU (baseline gitleaks); индекс [docs/README](docs/index.md) / [README.ru](docs/ru/index.md) и эпик CV/ML [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367), [CV_ML_PREP](archive/internal/docs-legacy/CV_ML_PREP.md) / [RU](archive/internal/docs-legacy/CV_ML_PREP.ru.md), [HUB_EPICS_TRACKER](archive/internal/docs-legacy/HUB_EPICS_TRACKER.md) / [RU](archive/internal/docs-legacy/HUB_EPICS_TRACKER.ru.md); [VERIFICATION](archive/internal/docs-legacy/VERIFICATION.md) / [RU](archive/internal/docs-legacy/VERIFICATION.ru.md).

- **[#343](https://github.com/Gfermoto/BirdLense-Hub/issues/343) (фазы C–D):** UI — **`BirdFood`** и ответы **`/status`**, **`/readiness`** типизированы через **`openapi-types`** (`types.ts`, **`camerasHealth.ts`**); документ **`docs/project/UI_API_MANUAL_CONTRACTS.md`** (ручные контракты: камеры, feed/info, observability) + ссылка из **`docs/project/openapi.md`**; Vitest: **`client.test.ts`**, **`camerasHealth.test.ts`**, **`birdFoodFeed.test.ts`**; **`data-testid`** на пунктах навигации (**`nav-pill-*`**, **`nav-live`**, мобильное **`nav-mobile-*`**) и смоук **Playwright** на **`nav-pill-timeline`**.

- **[#343](https://github.com/Gfermoto/BirdLense-Hub/issues/343) (фаза B):** UI — импорты страниц/хуков/настроек переведены с барреля **`api.tsx`** на доменные модули (**`client`**, **`timeline`**, **`video`**, **`weatherRegion`**, **`migrationCalendar`**, **`dataset`**, **`birdFoodFeed`**, **`camerasHealth`**, **`fileTest`**, **`settingsSession`**, **`settingsYamlDb`**, **`systemAuditMetrics`**, **`notificationsProcessor`**, **`speciesRegistryHub`**, **`speciesOverviewDetections`**); в **`api.tsx`** остаются **`getApiErrorMessage`**, **`resolveImageUrl`** и реэкспорты; обновлены моки Vitest (**`SpeciesDirectory`**, **`RecognitionImprovement`**, **`TimelinePage`**, **`Navigation`**, **`App.routes`**).

- **[#343](https://github.com/Gfermoto/BirdLense-Hub/issues/343) (фаза A):** UI — **`client.ts`** (base URL, axios timeout, **`JOB_STATUS_POLL_TIMEOUT_MS`**), **`timeline.ts`**, **`video.ts`** (видео, соседи, fusion trace, nearest recording day, delete/regen/merge), **`weatherRegion.ts`**, **`migrationCalendar.ts`**, **`dataset.ts`**, **`birdFoodFeed.ts`**, **`camerasHealth.ts`**, **`fileTest.ts`**, **`settingsSession.ts`**, **`systemAuditMetrics.ts`**, **`notificationsProcessor.ts`** (push / notify / restart / веса), **`settingsYamlDb.ts`** (YAML, БД, purge, ZIP→координаты), **`speciesRegistryHub.ts`** (реестр, fusion/recognition, BirdNET FIFO, purge-диагностика), **`speciesOverviewDetections.ts`** (каталог/обзор вида, тюнинг, Xeno-Canto, PDF, детекции, review-queue, corrections); **`api.tsx`** — `getApiErrorMessage`, `resolveImageUrl` и реэкспорты; **`queryKeys`** — таймлайн, unknowns, **video**, bird-directory, **speciesSummary** (в т.ч. `bySpecies`), **storage** (stats), **overview** / **weather** / **calendar**, **`systemPanels`** (аудит конфига, observability, каталог, recognition/fusion, веса и др.), **feed**, **health** (статус шапки), **live** (камеры), **birdFood**, **fileTest**, **speciesDirectory**; миграция ключей на **Timeline**, **Unknowns**, **VideoDetails** / **VideoInfo** / **DetectedSpecies**, **Overview**, **WeatherCard**, **MigrationCalendar**, **DatabaseMaintenanceCard**, **StorageOverview**, **RecordingsCalendar**, **DatasetExportsCard**, **Navigation**, **FeedCard**, **StatusIndicator**, **Footer**, **Live**, **FoodManagement**, **FileReplayCard**, карточки **Система** (**SystemHero**, **ConfigAudit**, **Observability**, **CatalogRepair**, **RecognitionImprovement**, **SpeciesDataQuality**, **ClassifierDatasetAlignment**, **ProcessorWeights**, **AutomationFusion**), **SpeciesDirectory**, **SpeciesSummary**, **ProcessorFrigateFusionBlock**; тесты **`timeline.test.ts`**, **`video.test.ts`**, **`weatherRegion.test.ts`**.

- **Документация (CONFIGURATION):** EN/RU — блок **On this page** / **По странице** (быстрые якоря), ссылки на **`app/.env.example`** и **`docs/project/openapi.md`** в шапке; **I18N_STATUS** — строка **SETTINGS_TRIGGERS_PHASE2**, шаг про OpenAPI/contract-тест при смене HTTP-маршрутов.

- **Документация (рефакторинг):** в **README** EN/RU — одна строка для CI-политики вместо дублирующихся ссылок на **CI_AND_QUALITY**; в блоке безопасности EN — ссылка на **SECURITY.ru**; в **README.ru** — симметричные EN-ссылки для ACCESS/SECURITY; в таблицах команд — регенерация OpenAPI. В **Documentation** EN/RU — раздел **OpenAPI spec maintenance** с якорем `{#openapi-spec-maintenance}`, пункт чеклиста ревью и строка в **Key documents**; **SITE_MAP** EN/RU — строка про скрипты OpenAPI.

- **Документация:** описание **CI** приведено к текущим workflow (ежедневный прогон **`ci-pr.yml`** на ветке по умолчанию, **`workflow_dispatch`**; **E2E (Playwright)** — ежедневно, не «раз в неделю»). Задокументированы **`make ci-local`** / **`make ci-local-docker`** и скрипт `scripts/ci-full-local.sh` (README EN/RU, `docs/CI_AND_QUALITY*`, `docs/TESTING*`, `docs/LOCAL_DEV*`, `docs/QUICKSTART`, `docs/README*`, `docs/Documentation*`, `docs/REPOSITORY_LAYOUT*`, `docs/VERIFICATION*`, `docs/OVERVIEW*`). В **README.ru** в таблицу команд добавлен отсутствовавший **`make verify`**.
- **Документация (установка/деплой):** `docs/INSTALL*`, `docs/DEPLOY_SERVER*` — выравнивание с **`scripts/deploy.sh`**: локальная сборка UI до rsync, **`DEPLOY_SSH_PORT`**, не удаляется **`birdlense-redis`**, полный **`verify-stack`**, список исключений rsync (в т.ч. **`.venv-ci`**). Вариант 4: явно про **Redis** в полном `docker-compose.yml` vs минимальный **image** compose. В **INSTALL.ru** добавлены шаги **`make verify`** для вариантов 2–3.
- **Деплой:** в **`scripts/deploy.sh`** rsync-исключение **`.venv-ci`**, чтобы локальный CI-venv не уезжал на сервер.
- **Документация (продолжение):** исправлен несуществующий **`make restart`** → `docker compose restart birdlense` / `make stop && make start` (**TROUBLESHOOTING**, **RECOVERY_CONFIG.ru**). **ARCHITECTURE** EN/RU — пояснение портов nginx/Flask/MCP. **SCENARIOS** 6 — ссылки на **DEPLOY_SERVER** и **`make verify`**. **FEATURES** EN/RU — строка **Library** и пример **`GET /readiness`** в таблице маршрутов. **API** EN/RU — строка **`/readiness`**. **GLOSSARY** EN/RU — термины **Library** / **Библиотека**. **MCP_SETUP** EN/RU — явная ссылка на **`scripts/deploy.sh`**.
- **Документация (аудит):** в **SECURITY** / **SECRETS_ROTATION** EN/RU везде явно **`app/.env`** там, где речь о сервере/контейнере; **RECOVERY_CONFIG** EN — явные команды перезапуска после ручного копирования YAML. **SETTINGS_TRIGGERS_PHASE2** включён в **`mkdocs.yml`** и **SITE_MAP** (EN/RU), чтобы `mkdocs build --strict` не ругался на страницу вне `nav`.
- **Документация (CONFIGURATION):** таблица переменных окружения EN/RU выровнена с **`app/.env.example`**: `FLASK_MAX_CONTENT_LENGTH`, `GUNICORN_THREADS`, `TRUSTED_PROXY`, `HA_URL`, `XENO_CANTO_API_KEY`, `HF_TOKEN`, сэмплер системных метрик, `BIRDLENSE_METRICS_TOKEN`; исправлен смешанный RU-текст в английской таблице; якоря `{#prometheus--grafana}` / `{#system-page-metrics-history}` для внутренних ссылок.
- **OpenAPI / API docs:** в **`app/web/openapi.yaml`** описаны все маршруты **`/api/ui/system/species-registry/*`** (seed, backfill, unresolved, enrich-metadata, health, materialize-allowlist, repair-cards, data-quality, classifier-dataset-alignment, coverage-metrics, tuning-targets/export); в **`docs/contributor/api.md`** / **`docs/ru/api.ru.md`** — таблица-обзор с отсылкой к YAML.
- **OpenAPI (полное покрытие UI + processor):** второй **`servers`** URL **`…/api/processor`** и пути ingest; для **`/api/ui`** добавлены недостающие маршруты (cameras, status/debug, push, feed, video download/stream/delete/merge/regen, settings unlock/yaml, notify, species extras, timeline/report exports, dataset/detections, storage nearest-day, domain-health, fusion jobs, telegram-proxy refresh, diagnostics, review-queue, DB backup/restore, retention, observability, visitors/track и др.) плюс **`DELETE /videos/{video_id}`**. Скрипты **`scripts/generate_openapi_remaining_paths.py`** и **`scripts/merge_openapi_fragments.py`** для регенерации блока; **`docs/project/openapi.md`** — как пользоваться двумя серверами в спецификации.

- **Настройки (UI):** удалён неиспользуемый `VideoSection` (дублировал захват/кормушку и старую модель `motion.source`). Поля весов интеграции и кормушки вынесены в `shared/scalesIntegrationFields.tsx` и `shared/feederRelayFields.tsx`. В `check-settings-ui-coverage.py` для legacy `integrations.scales.motion_trigger_*` добавлен явный allowlist (смена на `triggers.scales.*` в форме).

- **Процессор в настройках:** `ProcessorSection.tsx` разбит на восемь блоков в `sections/processor/*.tsx` (пороги, тайминги, мультикамера/BirdNET, расширенные пороги, guardrails, light gate, спектрограмма/датасет, Frigate fusion) — оркестратор ~70 строк.

- **Coverage настроек:** из `AUTO_ALLOWLIST_KEYS` убраны ключи, для которых уже есть `form.Field` в дереве Settings (меньше ложного «planned-ui» для полей с UI).

- **[#340](https://github.com/Gfermoto/BirdLense-Hub/issues/340):** тесты `processor_runtime_stats` для больших байтовых gauge (порядка 100 GiB), окна latency с `maxlen=200` и отрицательных сэмплов; в миграции **`004_birdnet_fifo_event`** уточнено, что `sa.JSON()` на PostgreSQL создаётся как JSONB (SQLAlchemy 2.x).

---

## [0.3.7] - 2026-04-25

### Changed

- Версия проекта **0.3.7** (`VERSION`, OpenAPI, MkDocs `site_version`, UI `package.json`).

---

## [0.3.6] - 2026-04-21

### Changed

- Версия проекта **0.3.6** (`VERSION`, OpenAPI, MkDocs `site_version`, UI `package.json`).

---

## [0.3.5] - 2026-04-15

### Changed

- Версия проекта **0.3.5** (`VERSION`, OpenAPI, MkDocs `site_version`, UI `package.json`).

### Security

- **Трассировка fusion:** `GET /api/ui/videos/{id}/fusion-trace` и кнопка на странице ролика — только для **оператора (contributor)** и **администратора** (`contributor_or_admin_access`), не для анонимных зрителей. OpenAPI и CONFIGURATION (EN/RU) обновлены.

### Added

- **Единый контракт verify / readiness:** `scripts/verify-stack.sh` — последовательная проверка `/api/ui/health`, `/api/ui/readiness` (200 или 503 с полезной нагрузкой), `/api/ui/status` (опционально камеры); подключено в `install.sh`, `scripts/deploy.sh`, `make verify` (корень и `app/`). **`GET /api/ui/readiness`** — пинг БД, проверка записи в `data/` и `app_config/`, компоненты в JSON; в строгом UI API добавлен allowlist для readiness/status. Карточка **Система → готовность** (`SystemReadinessCard`), axios `validateStatus` для 200/503. OpenAPI: `/readiness`, расширенная схема 503. **Vitest** (`app/ui/`: `npm run test`) в CI; E2E smoke — ожидание health и навигация. Документация: `docs/user/quickstart.md`, `docs/user/runbooks.md`, обновления README, INSTALL, LOCAL_DEV, DEPLOY_SERVER, TESTING, VERIFICATION, `mkdocs.yml`.

- **Свои веса YOLO из UI ([#276](https://github.com/Gfermoto/BirdLense-Hub/issues/276)):** **Система → Веса процессора** — загрузка `.pt` для бинарного детектора и классификатора и `class_names.txt` в `DATA_DIR/custom_weights/`, обновление `user_config` абсолютными путями, сброс к встроенным путям, флаг перезапуска процессора после операций. API `GET/POST /api/ui/system/processor-weights/*`; проверка `.pt` как zip-чекпойнта без `torch` в web; загрузка классификатора требует существующего allowlist или `acknowledge_classifier_only`.

- **Тестовый прогон по файлам без рестарта ([#270](https://github.com/Gfermoto/BirdLense-Hub/issues/270)):** при `video.source=file` процессор не блокируется на пустой папке; обмен через `data/file_test_control/desired.json` и `status.json` (старт/стоп, loop, abort сессии). API `GET/POST /api/ui/system/file-test/*`, карточка на странице **Библиотека** (список, upload, удаление, прогресс polling). `GET .../status` всегда 200 с полем `video_source`, чтобы UI не опрашивал 409 вне режима `file`.

- **Fusion decision trace ([#272](https://github.com/Gfermoto/BirdLense-Hub/issues/272)):** `GET /api/ui/videos/{id}/fusion-trace` и диалог на странице ролика (**Fusion trace** / **Трассировка fusion**) — шаги по трекам (детектор → классификатор → evidence → аудио → fusion → итог) плюс сырой JSON; документация в **CONFIGURATION** (EN/RU).

- **BirdNET MQTT FIFO ([#269](https://github.com/Gfermoto/BirdLense-Hub/issues/269)):** таблица **`birdnet_fifo_event`** в hub БД (Alembic **`004_birdnet_fifo_event`**); процессор пишет в SQLite **`data/db/birdlense.db`** через фоновый поток (**WAL**, **`busy_timeout`**), гидратирует RAM при старте MQTT; **`GET .../diagnostics/birdnet-fifo`** отдаёт снимок из БД при наличии строк (иначе JSON-файл как раньше). Ключи **`processor.birdnet_fifo_persist_enabled`**, **`processor.birdnet_fifo_sqlite_busy_ms`**. При **`DATABASE_URL`** PostgreSQL запись из процессора отключена (нет общего sqlite-файла).

- **BirdNET FIFO — диагностика в UI ([#303](https://github.com/Gfermoto/BirdLense-Hub/issues/303)):** диалог **Система → Автоматизация → BirdNET FIFO** — таблица видов (`species_fifo_table`: MQTT-имя, ключ слияния с видео, счётчик событий, латинское имя, «как давно»), зелёная полоса слева для «услышан в окне»; сырой JSON в свёрнутом блоке; общий merge-key (**`app_config/birdnet_merge_key`**) для web и processor; тесты web/processor; локали EN/RU. Закрывает UX по сравнению с «стеной JSON».

### Changed

- **Web / observability:** заголовок **`X-Request-ID`** и логирование с привязкой к запросу (`app/web/app_logging.py`, подключение из `app.py`).

- **Deploy script:** `scripts/deploy.sh` — `set -euo pipefail`, локально **`npm ci && npm run build`** в `app/ui`, пост-деплой проверка через `verify-stack.sh`; безопасная подстановка необязательных переменных окружения в remote heredoc (`${VAR:-}`).

- **Документация (тон и структура):** MCP описан как протокол для **авторизованных клиентов** (автоматизация, интеграции), без акцента на ИИ-редакторы; README / OVERVIEW / SHORT_DESCRIPTION — явная аудитория **орнитология** и **citizen science**; внутренние файлы `PRE_IMPLEMENTATION_UNKNOWN_TIMELINE*.md` и `LEGACY_CLEANUP.md` исключены из публикуемого MkDocs; навигация и перекрёстные ссылки подогнаны под `mkdocs build --strict`.

- **UI / CI:** job `ui-build` запускает **`npm run typecheck`** (`tsc -p tsconfig.app.json`); тип **`Settings`** расширен полями процессора / весов / motion из конфига; мелкие правки под строгий TS (Pie highlightScope, PWA virtual module, web-push `patchSettings`). **`locales/zh.json`** — полное дерево ключей как в `en.json`, перевод на упрощённый китайский (zh-CN); пилотная локаль **`de`** удалена, сохранённый язык **`de`** в localStorage однократно переносится на **`zh`**.

- **Офлайн-прогон по файлам (UI):** заголовок секции и единственный переключатель зацикливания — только внутри карточки на **Библиотеке**; якорь `#file-replay` на самой карточке. Документация RU: исправлена ссылка «Система» → **Библиотека**. Лимит upload `video.file_test_max_upload_mb`: по умолчанию **10240 MiB** (>10000), зажим в коде **64–65536 MiB**.

- **Fusion decision trace (семантика):** в payload `decision_trace` добавлены **`persisted_tracks`** / **`persisted_track_count`** и флаг строки **`persisted_to_clip`**; **`accepted_tracks`** остаётся ссылкой на тот же список (legacy). Экспорт fusion-training и скрипт CSV обходят **один** список клипа, чтобы не дублировать строки. UI/API: bucket трека **`persisted`**, подписи «сохранено в клипе» vs «DecisionMaker accepted».

- **BirdNET ↔ видео, ключ слияния:** в **`birdnet_merge_key`** сначала матчится **`detection.species_mapping`** по научному имени (ключи вида **`Parus major (Great Tit)`**), затем уже **`species_taxon.common_name`** из SQLite — колонка «ключ для видео» и слияние с YOLO не прыгают между русским и английским из‑за локали в каталоге. В **`default_config.yaml`** добавлены типовые европейские виды (в т.ч. из RU BirdNET).

- **`species_normalizer._to_title_case`:** дефисы в составе названия не превращаются в пробелы (корректнее вывод для **`Red-breasted Flycatcher`**, **`Eurasian Eagle-Owl`** и т.п. после **`normalize()`**).

- **`birdnet_merge_key`:** значение из **`detection.species_mapping`** по научному имени возвращается **как в YAML** (без повторного **`normalize()`**), чтобы не портить написание вроде **Red-breasted** / **Eagle-Owl**.

### Fixed

- **Intel GPU на сервере (VA-API + метрики UI):** `docker-compose.override` теперь генерируется скриптом **`app/scripts/docker-compose-intel-override-gen.sh`**: все `/dev/dri/renderD*` и `card*`, **`group_add`** с GID групп **video/render хоста** (раньше без них устройства были `rw-rw----` → VA-API и косвенно метрики ломались), **`CAP_PERFMON`** вместе с `SYS_ADMIN` для `intel_gpu_top`. Вызывается из **`scripts/deploy.sh`** и из **GitHub Actions Deploy** перед `make start`.

- **Intel PMU / `intel_gpu_top` на VPS:** при **`kernel.perf_event_paranoid=3`** (и на части хостов даже при **1**) ядро отказывает в perf/PMU в Docker даже с **`CAP_PERFMON`**. После **1.8** **`scripts/deploy.sh`** и **GitHub Actions** при наличии **`docker-compose.override.yml`** пишут **`/etc/sysctl.d/99-birdlense-perf.conf`** со значением **0** и **`sysctl -p`** (ошибки игнорируются). INSTALL (EN/RU): при нехватке **0** — **−1** вручную или **`privileged: true`** в override.

- **Метрики Intel GPU в Docker:** при `intel_gpu_top` с ошибкой PMU `Permission denied` предупреждение в лог не чаще **раза в час** (если после правок override ошибка останется).

- **Логи процессора:** «No detections after merge…» — не чаще **раза в 120 с** на уровне WARNING (между — DEBUG).

- **Логи FFmpeg при записи go2rtc:** прогресс `frame=` / «Queue input is backward in time» / «Last message repeated» — **DEBUG**, итоговые строки — INFO.

- **Файл-реплей UI:** переключатель зацикливания — приоритет `desired.loop` над `processor.loop`, пауза ~4.5s без перезаписи из polling после клика, сброс при ошибке `loopMut`. **Upload 413:** в Flask задан высокий **`MAX_CONTENT_LENGTH`** (переменная **`FLASK_MAX_CONTENT_LENGTH`** в байтах); в UI отдельный текст, если 413 похож на ответ прокси (не JSON хаба). Документация INSTALL/CONFIGURATION: nginx `client_max_body_size` для `/api/`. **Встроенный nginx образа Hub:** в `docker-nginx-main.conf` задан **`client_max_body_size 64g`**; для `location /api` — длинные **`proxy_*_timeout`** и **`proxy_request_buffering off`**, чтобы прокси в контейнере не отсекал большие тела запросов.

- **CI processor tests:** `test_two_stage_strategy_integration` больше не требует jay/bird в top-1 на `1.jpg` — реальные веса дают другие виды (напр. GYRFALCON в Docker); проверяется конвейер binary + species head и валидные `class_name`.

- **Docker / fusion export:** контекст сборки `birdlense` — **корень репозитория** (`docker-compose`: `context: ..`, `dockerfile: app/Dockerfile`); в образ копируется **`scripts/export_fusion_training_data.py`**, `repo_root()` и E2E/тесты без монтирования `..:/workspace` не ломаются.

- **Тесты без пропусков:** `test_settings_with_mcp_token` задаёт временный `mcp.token`; `test_regional_scope_true_for_birdnet_detection` создаёт и удаляет вид в БД; `test_detection_strategy` не подменяет `ultralytics`, если пакет установлен (интеграции YOLO в Docker); Playwright smoke — пустой Overview без `test.skip`.

- **CI / Settings UI:** ключ **`general.session_idle_minutes`** из `default_config` — поле в **Settings → Security** (EN/RU), тип **`session_idle_minutes`**, при двух уровнях доступа PATCH для помощника снимает это поле (**`CONTRIBUTOR_ADMIN_ONLY_PATCH_PATHS`**). **Ruff format** для **`app/processor/src/interfaces.py`**.

- **Docker / nginx (non-root):** каталог **`/var/log/nginx`** в образе принадлежит **`birdlense`**; **`error_log`** / **`access_log`** указывают туда же — без alert «could not open … /var/log/nginx/error.log» при старте. Кэши **`app/.ruff_cache`** и **`app/.pytest_cache`** в **`.gitignore`**. См. [TROUBLESHOOTING](docs/user/troubleshooting.md) / [RU](docs/ru/troubleshooting.ru.md).

### Changed

- **Processor ([#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295)):** `DetectionStrategyProtocol` в **`app/processor/src/interfaces.py`**; `FrameProcessor` аннотирован протоколом; тест **`test_detection_strategy_protocol.py`**. Док: [ARCHITECTURE](docs/contributor/architecture.md) / [RU](docs/ru/architecture.ru.md) § Maintainability baseline; [REPOSITORY_LAYOUT](docs/contributor/repository-layout.md) / [RU](archive/internal/docs-legacy/REPOSITORY_LAYOUT.ru.md) — состав **`app/processor/`**.

- **[#279](https://github.com/Gfermoto/BirdLense-Hub/issues/279):** опциональный строгий режим UI API — при **production** и **`BIRDLENSE_STRICT_API_AUTH=1`** запросы к **`/api/ui/*`** требуют сессию (после `verify-password`), **`BIRDLENSE_UI_API_KEY`** (`X-Birdlense-Api-Key` или Bearer) или **MCP Bearer**; исключения: `health`, `requires-password`, `check-access`, `verify-password`, `vapid-public`, `logout`, preflight **OPTIONS**. **Docker Compose** и **`scripts/deploy.sh`** пробрасывают/сливают `BIRDLENSE_STRICT_API_AUTH` и `BIRDLENSE_UI_API_KEY`; CI — отдельный шаг `test_strict_ui_api_auth.py`. См. **SECURITY** / **ACCESS_CONTROL** / **CONFIGURATION** / **SECRETS_ROTATION** / **INSTALL** (EN/RU), `app/.env.example`, `scripts/deploy.local.sh.example`.

- **Web ([#292](https://github.com/Gfermoto/BirdLense-Hub/issues/292)):** CORS и SQLite PRAGMA — **`app/web/flask_extensions.py`**; старт схемы, seed, species registry, legacy cleanup и фоновый metadata repair/enrich — **`app/web/app_startup.py`**; `app.py` остаётся тонкой фабрикой. Док: [REPOSITORY_LAYOUT](docs/contributor/repository-layout.md) / [RU](archive/internal/docs-legacy/REPOSITORY_LAYOUT.ru.md), [ARCHITECTURE](docs/contributor/architecture.md) / [RU](docs/ru/architecture.ru.md).

- **[#283](https://github.com/Gfermoto/BirdLense-Hub/issues/283):** локальные CORS origins (Vite, `birdlense.local`, порт хаба) заданы в **`config.Config`** и переменной окружения **`CORS_LOCAL_DEV_ORIGINS`** (пустая строка — не добавлять встроенный набор); `app/web/app.py` только собирает итоговый список вместе с `CORS_DEFAULT_ORIGINS` / `CORS_ORIGINS`.

- **Весы / ESPHome MQTT ([#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) комментарий, [#232](https://github.com/Gfermoto/BirdLense-Hub/issues/232) закрыт):** префикс **`integrations.scales.mqtt_topic_prefix`** (`birdlense/scale` → топики `weight`, `bird_present`, `command`); процессор мержит **`bird_present`** в `feeder_scale_state.json`; **`POST /api/ui/feed/scale-tare`** публикует **`mqtt_tare_payload`** (по умолчанию `TARE`); карточка кормушки — строка присутствия и кнопка тары (админ). Ключи **`mqtt_command_topic`** / **`mqtt_tare_payload`** в YAML. Документация: **CONFIGURATION** (EN/RU).

- **Processor (tech debt [#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225) / [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238)):** цикл motion → запись и финализация вынесены в **`MotionRecordingSession`** (`app/processor/src/recording_session.py`); **`main.py`** оставляет сбор зависимостей и вызов сессии.
- **Web (миграции схемы, [#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225)):** вместо try/except **`ALTER TABLE`** на старте — **Flask-Migrate / Alembic** (`app/web/migrations/`, ревизия **`001_schema_patches`**, идемпотентные колонки); после **`db.create_all()`** вызывается **`upgrade()`**; зависимость **`Flask-Migrate`** в `web/requirements.txt`.

### CI

- **CodeQL (Python):** в **`.github/codeql/codeql-config-python.yml`** добавлены **`query-filters`** — отключены **`py/reflective-xss`** (ответы JSON через `jsonify`), **`py/stack-trace-exposure`** (краткие ошибки клиенту) и **`py/path-injection`** (ложное срабатывание на `data_paths` при реальном `realpath`/`commonpath`; `recording_layout_paths` уже в `paths-ignore`).

- **openapi-contract:** Radon — закрепить **`radon==6.0.1`** (на PyPI нет **6.0.5**; шаг «cyclomatic complexity» падал на `pip install`).

- **[#286](https://github.com/Gfermoto/BirdLense-Hub/issues/286):** job `ui-build` — после `npm ci` выполняется **`npm run lint`**, затем build; ESLint: плагин `react-hooks` с правилами **`rules-of-hooks`** и **`exhaustive-deps`** (без полного `recommended` v7 с React Compiler rules).

- **[#284](https://github.com/Gfermoto/BirdLense-Hub/issues/284):** `.github/workflows/npm-audit-scheduled.yml` — еженедельно + `workflow_dispatch`: `npm audit --omit=dev --audit-level=moderate` в `app/ui`; политика в комментариях workflow. Док: [TESTING](docs/contributor/testing.md) / [RU](docs/ru/testing.ru.md).

### Docs

- **Processor / Telegram:** в [CONFIGURATION](docs/user/configuration.md) / [RU](docs/ru/configuration.ru.md) описан ключ **`processor.min_confidence_to_notify`** (отдельный порог для фото в Telegram); в [TROUBLESHOOTING](docs/user/troubleshooting.md) / [RU](docs/ru/troubleshooting.ru.md) — почему после правок `processor.*` / `detection.*` нужен **перезапуск processor**.

- **[#234](https://github.com/Gfermoto/BirdLense-Hub/issues/234):** гайд [HEIMDALL](archive/internal/docs-legacy/HEIMDALL.md) / [RU](archive/internal/docs-legacy/HEIMDALL.ru.md) — шаблон URL для плиток linuxserver/Heimdall v2 (ручное добавление; без импорта в UI); опциональный HTML закладок для браузера в [docs/examples/heimdall/](docs/examples/heimdall/); ссылки из [CONFIGURATION](docs/user/configuration.md) / [RU](docs/ru/configuration.ru.md), навигация MkDocs.

- **[#287](https://github.com/Gfermoto/BirdLense-Hub/issues/287):** аудит завершён — в `create_app`/рантайме web нет `ALTER TABLE`; DDL только в Alembic; зафиксировано в [ARCHITECTURE](docs/contributor/architecture.md) / [RU](docs/ru/architecture.ru.md) (политика DDL + PRAGMA).

- **Синхронизация с кодом и CI:** обновлены [TESTING.md](docs/contributor/testing.md) / [TESTING.ru.md](docs/ru/testing.ru.md) (полный перечень job workflow CI), [ARCHITECTURE](docs/contributor/architecture.md) / [RU](docs/ru/architecture.ru.md) (Alembic/Flask-Migrate), [REPOSITORY_LAYOUT](docs/contributor/repository-layout.md) / [RU](archive/internal/docs-legacy/REPOSITORY_LAYOUT.ru.md) (`create_app`, migrations, services), [ROADMAP](docs/contributor/roadmap.md) / [RU](docs/ROADMAP.ru.md) (версии React/Vite из `package.json`, строка про схему БД, волна maintainability [#292](https://github.com/Gfermoto/BirdLense-Hub/issues/292)–[#297](https://github.com/Gfermoto/BirdLense-Hub/issues/297) + security [#277](https://github.com/Gfermoto/BirdLense-Hub/issues/277)–[#287](https://github.com/Gfermoto/BirdLense-Hub/issues/287)), [README](docs/index.md) / [RU](docs/ru/index.md), [Documentation](docs/contributor/documentation.md) / [RU](docs/Documentation.ru.md) (чеклист ревью), [VERSIONING](archive/internal/docs-legacy/VERSIONING.md) / [RU](archive/internal/docs-legacy/VERSIONING.ru.md), корневые [CONTRIBUTING](CONTRIBUTING.md) / [RU](CONTRIBUTING.ru.md). Ссылки на корневой `CHANGELOG` и `.github/workflows/ci-pr.yml` ведут на GitHub, чтобы **`mkdocs build --strict`** не ругался на пути вне `docs/`.

- **Roadmap / техдолг:** [#201](https://github.com/Gfermoto/BirdLense-Hub/issues/201) отмечен закрытым, активный processor backlog — [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238); обновлены [ROADMAP.md](docs/contributor/roadmap.md), [ROADMAP.ru.md](docs/ROADMAP.ru.md), пример `github-issue-link-subissues.sh`. Эпик [#220](https://github.com/Gfermoto/BirdLense-Hub/issues/220) в заголовке ссылается на processor [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238).
- **Техдолг — переоценка плана:** тело [#220](https://github.com/Gfermoto/BirdLense-Hub/issues/220) переписано (статусы #221–#224/#198/#201, таблица «что сделано / что осталось»); [#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225) и [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238) синхронизированы с кодом (`build_detection_stack`, `is_mqtt_live` / `is_mqtt_ok_for_heartbeat`).

### Changed

- **Processor / eBird (#238):** вынесен общий модуль **`app/ebird_region_core.py`** (регион, HTTP top-N, кэш, маппинг имён через `app_config`). Процессор **`ebird_regional_confidence`** больше не импортирует `services.*`; `ebird_region_service` и **`ebird_util.REGION_NAME_TO_CODE`** используют core. Docker: `COPY ebird_region_core.py`.

### Fixed

- **Ручная коррекция вида (UI):** по умолчанию `PATCH /api/ui/detections/:id` больше не использует **`legacy_fanout`** (обновление всех строк того же вида на ролике + синхронный FFmpeg для датасет-кропов на каждой строке), из‑за чего запрос мог занимать минуты и «вешать» вкладку. Теперь по умолчанию **`single_track`** (как сценарий Unknowns / одна строка); страница видео явно передаёт **`apply_scope: legacy_fanout`**. При большом числе затронутых строк перенос/извлечение кропов датасета уходит в **фоновый поток** после `commit`.

- **Processor / MQTT (#238):** при обрыве брокера исходящая **очередь не сбрасывается**; `publish_detection` ставит сообщения в очередь и при кратковременном offline (если брокер настроен); слив только при живом сокете. `stop()` по-прежнему очищает очередь.
- **Деплой:** rsync больше не синхронизирует корневой каталог **`datasets/`** (локальные данные для обучения), чтобы не заливать гигабайты на VPS.
- **Code review (PR #235):** пустой дефолт `homeassistant.url` в `default_config.yaml` — снова работает fallback на `weather.ha_url` при апгрейде; безопасный `int` для `history_max_lines` в процессоре; журнал весов обрезается по числу строк, а не только после 512 KiB; миграция `scales_weight_delta_kg` — игнор только дубликата колонки, остальные ошибки логируются и пробрасываются; OpenAPI `Settings` — блок `homeassistant`; валидация min в UI для порога/дебаунса триггера по весам; уточнены CONFIGURATION и RU-локали.

### Added

- **Timeline / карточка визита:** в ответе `/api/ui/timeline` и в UI (`VisitCard`) поле **`scales`** — оценка дельты весов с «основного» ролика визита (как на странице видео). [#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) закрыт.

### Changed

- **Деплой:** `scripts/deploy.sh` — rsync исключает **`app/data/`** целиком и **`app/.env`**, как в [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml); локальные записи/БД/images на VPS не затираются при `make deploy`.
- **Processor (tech debt #225, шаг 1):** из `main.py` вынесены `processor_support` (логирование, heartbeat, restart flag, пути записи) и `notify_preview_encode` (превью для уведомлений).
- **Processor (tech debt #224):** исходящие MQTT-публикации из потока записи идут в очередь и отправляются только из потока сетевого цикла (`Client.publish` — single writer); цикл `loop_forever` заменён на `loop` + слив очереди. **`frame_processor`:** при слабом свете троттлинг без `sleep(1)` на критическом пути записи ([#224](https://github.com/Gfermoto/BirdLense-Hub/issues/224)).
- **Настройки → General:** подсказка **`heimdall_url`** — явно указано, что Heimdall **не** импортирует сущности BirdLense; URL только для проверки доступности с Hub; плитка на хаб и `/metrics` — вручную.
- **Трекинг:** [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) закрыт (основной объём весов); [#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) (дельта на карточке визита) закрыт после реализации в timeline/UI; **ROADMAP** обновлён.
- **Настройки весов (UI):** при источнике Home Assistant — информационный блок, почему нет опций дельты/триггера (процессор только MQTT); **CONFIGURATION** — уточнён разрыв `mqtt` vs `homeassistant`.
- **Home Assistant:** URL и Long-Lived Token вынесены в отдельную секцию **`homeassistant.*`** и блок настроек «Home Assistant» (общие для погоды, весов с `source: homeassistant` и др.); в «Погода» при источнике HA остаётся только **`weather.ha_entity_id`**. Устаревшие `weather.ha_url` / `weather.ha_token` по-прежнему читаются как fallback и помечаются в аудите конфига; те же ключи игнорируются в списке «unknown» аудита. Env **`HA_URL`** / **`HA_TOKEN`** по-прежнему перекрывают YAML.
- **Scales:** убран ключ и переключатель `integrations.scales.estimate_require_video_detection` — дельта веса за клип **по умолчанию и всегда** не пишется для роликов только с BirdNET (`audio`); звук остаётся для вида, не для привязки к весам. **Docker:** лимиты контейнера хаба **4 CPU / 4G**, Redis **256M** maxmemory, **Gunicorn 16** потоков по умолчанию; кэш API по-прежнему `performance.cache_redis_enabled: true` + `REDIS_URL` в compose.
- **Web (PR #227 follow-up):** кэш **`filter_feeder_species`** — сигнатура каталога Species учитывает сумму `length(name)` (переименования без смены id/parent); **`bust_feeder_species_filter_cache`** после seed / backfill (не dry-run) / materialize-allowlist species-registry; **`app/pyproject.toml`** — interrogate с порогом 80% (исключён `tests`, игнор вложенных функций, `__init__`, magic и `_semiprivate`); **`make docs-check`** запускает `interrogate` из `web/` без принудительного успеха.
- **Processor (tech debt #223):** единая сборка пайплайна детекции — **`detection_stack.build_detection_stack`** (`resolve_single_stage_model_path`, стратегия two/single stage, `FrameProcessor`, `DecisionMaker`, eBird overrides); **`main.py`** и **`track_regenerator.build_detection_pipeline`** используют её вместо дублирования ([#223](https://github.com/Gfermoto/BirdLense-Hub/issues/223)).
- **Web (tech debt #223):** маршруты метрик/visitors/history — в **`ui_system_metrics_routes`**; species-registry — в **`ui_system_species_registry_routes`**; из **`ui_system_routes`** убраны дубликаты эндпоинтов (одна регистрация на Flask) ([#223](https://github.com/Gfermoto/BirdLense-Hub/issues/223)).
- **Web (tech debt #198 закрыт):** публичные **`/api/ui/*`** вынесены из монолита в доменные модули **`ui_*_routes`**; **`ui_routes.py`** — только **`register_routes`** и реэкспорт хелперов таймлайна (`build_merged_timeline_items`, `parse_timeline_iso`). См. [ARCHITECTURE](docs/ru/architecture.ru.md) ([#198](https://github.com/Gfermoto/BirdLense-Hub/issues/198)).
- **Follow-up ([PR #227](https://github.com/Gfermoto/BirdLense-Hub/pull/227) review):** **`data_paths`** — единый `_resolved_path_under_data_dir`, безопасный **`full_path_for_video`** (только под `DATA_DIR`); **`timeline_payloads`** — сравнение окон визитов в aware UTC; **`visitors/track`** — лимит POST по IP, сброс только префикса `system_visitors:`, retry при `IntegrityError` на уникальном `(browser_hash, seen_day)`; seed/backfill species-registry — инвалидация кэшей; **`observer_time`** — даты солнца из astral, вечер до конца суток; **`detection_stack`** — предупреждение при fallback `yolov8n.pt`; **`species_metadata`** — отсутствие `hierarchy_names.txt`, `build_hierarchy_tree` через `_load_hierarchy_parent_map`.
- **Web / SQLAlchemy 2.x:** `ActivityLog` и `Video` загружаются через `db.session.get(...)` вместо устаревшего `.query.get()` (`processor_routes` activity log, `gallery_upload_service`). **Processor:** docstring у `DecisionMaker.decide_stop_recording`, комментарий к ключу `(key, -1)` в `species_normalizer` ([#221](https://github.com/Gfermoto/BirdLense-Hub/issues/221)).
- **Processor (tech debt #222):** `ebird_regional_confidence` больше не правит `sys.path` — импорт `services.ebird_region_service` при нормальном `PYTHONPATH` (`/app:/app/web` в Docker). **MQTT:** разведены `is_mqtt_live()` (сокет к брокеру) и `is_mqtt_ok_for_heartbeat()` (с запасом после обрыва); heartbeat UI — второй, выбор Frigate primary и motion — первый ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** лимит попыток verify-password, `Retry-After` и `client_ip_for_rate_limit` перенесены из `util.py` в `auth.py`; в `util` оставлен re-export для обратной совместимости ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** Wikipedia / iNaturalist, allowlist хостов для прокси, seed-иерархия и канонический маппинг видов, `update_species_info_from_wiki`, `filter_feeder_species` вынесены в **`species_metadata.py`**; `util.py` реэкспортирует прежние имена ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** `get_primary_video_for_visit*`, `format_visit_for_timeline`, `format_unlinked_video_for_timeline` вынесены в **`timeline_payloads.py`**; `util` реэкспортирует их для существующих импортов ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Tech debt [#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222) закрыт:** разгрузка `util.py` доведена до конца — фасад `util` + `species_metadata`, `timeline_payloads`, `data_paths`, `observer_time`, `time_util`, `metrics_auth`, `species_constants`, `compat_reexports`; обратная совместимость через реэкспорты. Прогон: `make test`, `make test-web`; деплой на площадку — `make deploy`.
- **Web (tech debt #222):** **`compat_reexports.py`** — реэкспорт auth / notifications / weather_service; `util` подтягивает их через `import *` ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** **`species_constants.py`** — `GENERIC_BIRD_SPECIES`; потребители импортируют напрямую, `util` реэкспортирует ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** **`time_util.py`** — `ensure_utc`, `parse_utc_timestamp`; **`metrics_auth.py`** — `metrics_bearer_denied`; `util` реэкспортирует ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Web (tech debt #222):** каталог данных и безопасные пути к файлам — в **`data_paths.py`** (`_data_dir`, `read_safe_image_bytes`, `recordings_dir`, `full_path_for_video`, …); часовой пояс наблюдателя и солнечные интервалы — в **`observer_time.py`**; `util` реэкспортирует прежние имена ([#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222)).
- **Follow-up ([PR #226](https://github.com/Gfermoto/BirdLense-Hub/pull/226) review):** очистка устаревших IP в счётчике verify-password; разбор `Authorization` для метрик с регистронезависимым `Bearer`; Frigate остаётся primary motion при старте даже если MQTT ещё не live; MQTT-only детекции в `species_normalizer` не затирают друг друга при `one_per_species`; OpenAPI — `400` для `/system/activity`, путь `/system/logs`; UI Overview без небезопасного cast погоды; правки доков scales/`DATA_DIR`; устойчивость `github-issue-link-subissues.sh` к 404 от `gh api`.

### Docs

- **Деплой:** `scripts/deploy.local.sh.example` и [DEPLOY_SERVER](docs/user/deploy-server.md) описывают **два равноправных режима** — **LAN** (на площадке: `192.168.1.11:22`, UI `:8085`) и **удалённый** (VPS `203.0.113.10:2222` как пример [TEST-NET-3](https://datatracker.ietf.org/doc/html/rfc5737), UI `https://hub.example.com/` или IP); в `deploy.local.sh` держать активным один блок и переключать при смене места работы.
- **Tech debt:** эпик [#220](https://github.com/Gfermoto/BirdLense-Hub/issues/220); **sub-issues** [#198](https://github.com/Gfermoto/BirdLense-Hub/issues/198) (**закрыт** — модульные `ui_*_routes`), [#201](https://github.com/Gfermoto/BirdLense-Hub/issues/201) (**закрыт** — PR [#237](https://github.com/Gfermoto/BirdLense-Hub/pull/237)), [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238) (processor фаза 2: **`MotionRecordingSession`** **сделано**), [#221](https://github.com/Gfermoto/BirdLense-Hub/issues/221)–[#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225) (**#225** в хабе: Alembic **`001`** + сессия записи **сделано**); `scripts/github-issue-link-subissues.sh`. [ROADMAP.ru.md](docs/ROADMAP.ru.md) — **волна D**.
- **Scales / roadmap:** [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) и [#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) закрыты. [CONFIGURATION](docs/ru/configuration.ru.md) — `integrations.scales.*` (MQTT / Home Assistant).

### Fixed

- **UI (Overview):** карточка погоды больше не пропадает из сетки: пока `/api/ui/weather` грузится, показывается скелетон; сбой погоды не блокирует весь обзор — только блок погоды с кнопкой «Повторить».

- **CI:** синхронизация **`app/ui/src/generated/openapi-types.ts`** с `openapi.yaml` (шаг `codegen:openapi` + `git diff` в workflow).

- **CI:** `ruff format` для `web/services/readiness_service.py`, `web/tests/test_system_stabilization.py`.

- **npm (Dependabot GHSA-r4q5-vmmm-2653):** обновлён **follow-redirects** (транзитивно от axios) — `npm audit` без находок.

- **E2E smoke (CI docker-tests):** сценарий **`/unknowns`** — ожидание финального URL **`/timeline`** без **`review=1`** для гостя (как в UI после `Navigate` + сброса review).

### Tests

- **Visitors track:** `test_security_hardening.py` — **429** при превышении лимита POST `/api/ui/system/visitors/track` по IP (PR #227).
- **Telegram proxy:** `test_telegram_proxy.py` импортирует `util` как топ-уровневый модуль (`import util`), в духе `conftest` и остальных web-тестов — избегает двойной загрузки `web.util` vs `util` и цикла с `timeline_payloads` (#222).
- **Xeno-canto:** `web/tests/test_xeno_canto_service.py` — парсинг и ошибки сети через мок `requests.get`; `GET /species/.../xeno-canto` в `test_api` без реального HTTP. Шаг в CI `openapi-contract` (#202).
- **Birdfood / Web Push:** `web/tests/test_settings_mutations_smoke.py` — 403 при закрытых настройках, POST+PATCH кормушек, дубликат имени, успешный `push/subscribe` при включённых уведомлениях. CI `openapi-contract` (#202).
- **Тот же файл:** стрим видео при `require_auth_for_video_stream` — гость 403, contributor 200; успешный `PATCH /api/ui/settings` с ролью admin (#202).
- **Processor / system:** `test_processor_videos_smoke.py` — секрет, пустой species, порог confidence, успешный ingest, невалидные даты; `test_system_routes_smoke.py` — activity, metrics/history, logs (403/200). CI `openapi-contract` (#202).
- **OpenAPI / CI:** `openapi.yaml` — ответ `/overview` (`hourlyTemperature`, `lastDetection`, `observer_timezone`, `stats.detectionByProvider`), схема `VideoNeighbors` и query-параметры как в API; контракт-тест `GET /videos/{id}/neighbors`. В job `openapi-contract` — **ruff** только для `web/tests/`; мелкие правки импортов под ruff (#202).

### Security

- **Metrics endpoints (optional auth):** если задан **`BIRDLENSE_METRICS_TOKEN`**, `GET /metrics`, `GET /api/metrics` и `GET /api/metrics/summary` требуют `Authorization: Bearer <тот же токен>` (`hmac.compare_digest`); без переменной поведение как раньше (удобно для scrape в LAN). См. [CONFIGURATION](docs/ru/configuration.ru.md) → Prometheus.
- **Code scanning (path injection):** чтение и удаление превью для Telegram — **`read_safe_image_bytes`** / **`remove_safe_image_file`** в `util.py`: `realpath` + `commonpath` + **`startswith(DATA_DIR + sep)`**, затем `open`/`os.remove`; логика вынесена из `notifications.py`. Удалён **`_safe_image_path_or_none`**. Для **`py/path-injection`** на sink-строках — **`# lgtm[py/path-injection]`** (путь уже ограничен каталогом данных); иначе анализатор не снимает taint с `realpath(path)` до `open`/`remove`.

---

## [0.3.4] - 2026-04-09

Патч CI/доков и синхронизация версии перед слиянием ветки настроек/UI.

### Fixed

- **Документация (MkDocs `--strict`):** в **CONFIGURATION** (EN/RU) ссылки на стартовые профили `app/configs/*.yaml` ведут на GitHub (`blob/main/...`), чтобы сборка сайта доков не падала на «файл не найден» относительно дерева `docs/`.
- **Processor / тесты:** более устойчивые сценарии MQTT (пустой `motion.frigate_label_filter`, `topic_matches_sub` как в paho) и тайминг `post_record` в CI.

### Changed

- Версия проекта **0.3.4** (`VERSION`, OpenAPI, MkDocs `site_version`, UI `package.json`).

## [0.3.2] - 2026-04-03

Патч безопасности и документации после **v0.3.1**: CodeQL, прокси изображений, доработки по итогам ревью PR, синхронизация версий.

### Security

- **CodeQL-driven hardening (Python):** species image proxy (`GET /api/ui/species-image`) follows redirects manually with an allowlisted host check on every hop; each request uses a URL rebuilt from parsed host/port/path (no userinfo). Client-facing proxy errors are generic; details only in server logs. Telegram/notification image paths use `_safe_image_path_or_none` that returns only a resolved path under `DATA_DIR`. Go2RTC: connect log omits URL-derived fields (credentials never hit log lines). eBird region comparison cache key uses **SHA-256** (truncated) instead of MD5. Species catalog allowlist parsing avoids a polynomial-ReDoS-prone regex.
- **Follow-up (security review on PR #218):** iNaturalist open-data allowlist for the species image proxy is **hostname-only** (`_host_is_inaturalist_open_data_asset`) — no substring match on the full URL (closes query-string SSRF bypass). `urlparse` / `hostname` / `port` wrapped where needed to avoid 500 on malformed URLs. `_is_safe_image_path` / `_safe_image_path_or_none` use `os.path.commonpath` against `DATA_DIR` to block `data_evil`-style prefix tricks. Regression tests added.
- **UI (`app/ui`):** refreshed `package-lock.json` and `overrides` so **lodash** resolves to **≥4.18.0** (addresses [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc), [GHSA-f23m-r3pf-42rh](https://github.com/advisories/GHSA-f23m-r3pf-42rh)); **serialize-javascript** pinned via override to **≥7.0.5**. `npm audit` clean. Python `requests` / **Flask-Cors** were already at patched versions in `app/web` and `app/processor` requirements.

### Changed

- **Docs / repo hygiene:** added [REPOSITORY_LAYOUT](docs/contributor/repository-layout.md) (EN/RU) for onboarding; moved publication drafts to `docs/article/`; refreshed docs index version line and roadmap stack (Ultralytics pip vs Docker base). Root `.gitignore` now ignores `/.pytest_cache/`.
- **Docs refactor:** MkDocs `nav` aligned with [SITE_MAP](archive/internal/docs-legacy/SITE_MAP.md) — `DEPLOY_SERVER`, `VERIFICATION`, pre-implementation checklist, `UX_TOOLTIPS`, Russian **A11Y** / **REPOSITORY_LAYOUT**; `INSTALL` cross-links the deploy checklist; [API](docs/contributor/api.md) version line tracks root `VERSION`; ROADMAP changelog links use [project/changelog](CHANGELOG.md); `article/**` and `CONSILIUM_AUDIT.ru.md` excluded from the static site build; ROADMAP anchor IDs fixed for strict builds.
- **Contributor docs:** removed `AGENTS.md`; maintainer workflow lives in [CONTRIBUTING](CONTRIBUTING.md) / RU. [GOVERNANCE](GOVERNANCE.md) / RU, [MCP_SETUP](docs/contributor/mcp-setup.md), OpenAPI description, PR template, CodeQL/local dev guides, and related copy updated for a standard open-source tone (human reviewers, VS Code).
- **Docs:** MCP again documented explicitly as **Model Context Protocol** for **authorized automation and integrations** (README, OpenAPI narrative, FEATURES, GLOSSARY, MCP_SETUP EN/RU).

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
- **`SettingsForm.tsx` → секции:** `sections/GeneralSection`, `VideoSection` (позже удалён), `ProcessorSection`, `NotificationsSection`, `EBirdSection`, `IntegrationsSection`; `shared/ServiceBlock`, `CamerasListField`. Главный файл стал оркестратором (< 120 строк).
- **React Error Boundary:** `components/ErrorBoundary.tsx` + оборачивает `<Routes>` в `App.tsx` — несломанный рендер при runtime-ошибках в дочерних страницах.

### Fixed

- **Telegram MTProto:** корректный разбор `telegram_api_id` и порта прокси из YAML/чисел (в т.ч. `12345.0`), чтобы после сохранения настроек не «терялся» api_id.
- **Telegram preview:** нормализация фото перед отправкой (`Pillow` + fallback через `OpenCV`) и upscaling очень маленьких кропов (минимум 64px), чтобы снизить ошибки Bot API `IMAGE_PROCESS_FAILED`.
- **Telegram notifications UX:** для детекций передаётся deep-link на конкретную запись (`/videos/{id}`) вместо общего `live`; превью теперь имеет fallback-кроп из сохранённого видео по `frames.bbox`, если `best_frame` отсутствует; кнопка в TG — более нейтральная (`Open video` / `Open live`).
- **Telegram notifications reliability:** чтобы избежать «пустых» уведомлений, добавлен дополнительный fallback на **полный кадр** из видео, если нет `best_frame` и нет валидного `bbox` для кропа.
- **Notifications observability:** добавлены логи источника превью (`best_frame` / `bbox_crop` / `full_frame` / `none`) и метрика Prometheus `birdlense_notify_preview_24h{source=...}` по данным `activity_log` за 24 часа.
- **Статус MQTT в шапке:** при работающем процессоре индикатор берёт **`mqtt_connected` из heartbeat** (тот же клиент, что Frigate/BirdNET). Дополнительно: проверка из веб-процесса ждёт до ~2 с после `loop_start()` и нормализует `mqtt.port` в int — меньше ложных «ошибок» из-за гонки.
- **UI (страница видео):** кнопки «предыдущая / следующая запись» не работали из‑за обращения к несуществующей переменной `listReturnState` (**ReferenceError** в обработчике). Исправлено: `useLocation()`, сохранение `state.from` при переходе к соседним роликам (как с Timeline / Unknowns). Журнал проверок: [VERIFICATION.ru.md](archive/internal/docs-legacy/VERIFICATION.ru.md) / [EN](archive/internal/docs-legacy/VERIFICATION.md).
- **UI / доступ:** `GET /api/ui/settings/check-access` всегда отвечает **200** с `{ unlocked: false }`, если сессия не разблокирована (раньше **403** — шум в консоли браузера). Защищённые POST/PATCH по-прежнему возвращают 403 без сессии.
- **Processor:** удалён legacy-compat флаг для старого single-stage COCO animal-only режима; runtime и конфигурация сведены к production-пайплайну `two_stage`.

### Changed

- **UI:** Migration — режим периода «по годам» **или** «по датам» (без одновременного показа четырёх полей). «Поддержать» в шапке на **всех** страницах (включая главную): **сердце** с анимацией пульса, то же в мобильном меню и в меню шестерёнки.
- **UI:** запрос `settings-check-access` в React Query — `staleTime` 60 с, меньше лишних refetch при навигации.
- **CI / Deploy:** workflow **Deploy** — `concurrency` (один активный деплой на `main`), `timeout-minutes: 45`, `permissions: contents: read`; шаг **Verify** падает с `exit 1`, если health недоступен (раньше только печатался FAIL). **upload-artifact** в CI и E2E → **v6** (Node 24, без предупреждения о Node 20). **INSTALL** / **RU:** пояснение про **Queued** и fallback `make deploy`. Rsync в autodeploy — добавлен `--exclude=app/.env`.
- **Зависимости / безопасность:** `app/ui` — `npm audit fix` (транзитивные обновления, в т.ч. brace-expansion, picomatch, yaml, цепочка до `serialize-javascript`); **`requests[socks]==2.33.0`** в `app/web/requirements.txt` (SOCKS-прокси для Telegram); `requests` **2.33.0** в `app/processor/requirements.txt`. **scripts/setup-auto-deploy.sh** — скачивание runner по **последнему** релизу с GitHub API, `RUNNER_ALLOW_RUNASROOT=1` под root, `./config.sh` с `--unattended --replace`.
- **CI / Deploy:** шаг **Verify** — порт из `BIRDLENSE_PORT` в `app/.env` на сервере (иначе 8085), пауза 10 с и до **36** попыток `curl` с интервалом 5 с после `make pull` (старт контейнера и приложения). Smoke workflow — исправлен маппинг порта контейнера (8080, по умолчанию entrypoint).
- **Процесс / документация:** закрыт открытый хвост issues ([#114](https://github.com/Gfermoto/BirdLense-Hub/issues/114), [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118), [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125), [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163)–[#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167)): ворота UX-контекста для `area:web` в [CONTRIBUTING.md](CONTRIBUTING.md) / [RU](CONTRIBUTING.ru.md); E2E — итеративное расширение в [TESTING.md](docs/contributor/testing.md) / [RU](docs/ru/testing.ru.md); идеи зафиксированы в [ROADMAP.md](docs/contributor/roadmap.md) / [RU](docs/ROADMAP.ru.md) (новый issue при появлении объёма).

### Added

- **Settings / UI:** поля в веб-настройках для прокси и сети Telegram (`notifications.telegram_proxy_url`, API base, таймауты, сжатие фото); post-roll и блок «несколько камер + BirdNET MQTT» (`processor.*`); зарезервированные **весы** `integrations.scales.*` (топик сохраняется, обработка — позже, [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167)). Web: зависимость **`requests[socks]`** для SOCKS5h.
- **Processor ([#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157)):** `processor.post_record_seconds` — post-roll: увеличивает паузу без детекций перед остановкой записи (сумма с `max_inactive_seconds`).
- **Processor ([#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129)):** опционально `processor.birdnet_mqtt_auto_confidence` и параметры delta/floor — более низкий порог классификатора для видов из недавних сообщений BirdNET по MQTT (по умолчанию выкл.).
- **Processor ([#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153)):** `processor.multi_camera_groups` + `multi_camera_confidence_boost` — при Frigate-событиях одного вида с двух камер из группы прибавка к `confidence` после merge.
- **Roadmap:** пункт консилиума **№17** — стратегия детекции (two_stage vs single_stage+COCO, пороги в `user_config`, дообучение бинарника); блок в [ROADMAP.ru.md](docs/ROADMAP.ru.md) / [EN](docs/contributor/roadmap.md), связь с [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163). Дополнено: **чеклист «не забыть»** перед/после консилиума; раздел **«Завершение задач → тестирование оператором»** (`#completion-then-operator-testing`).
- **E2E ([#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118)):** `app/e2e/tests/migration.spec.ts` — фильтр года на Migration и сброс на «все годы»; [TESTING.md](docs/contributor/testing.md) / [RU](docs/ru/testing.ru.md) — отладка отдельного файла (`playwright test` / `--debug`).

## [0.2.9] - 2026-03-28

Релиз доступности и регрессионных проверок. Merge: [#187](https://github.com/Gfermoto/BirdLense-Hub/pull/187), закрыт [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117).

### Added

- **Accessibility ([#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117)):** skip link to `#main-content`, shared `:focus-visible` ring in the MUI theme, migration table `caption` and labeled filter region, status dots as `role="img"` with `aria-label`, darker Live button for WCAG contrast; E2E axe scans in `app/e2e/tests/a11y.spec.ts` (`@axe-core/playwright`); [A11Y.md](archive/internal/docs-legacy/A11Y.md) / [RU](archive/internal/docs-legacy/A11Y.ru.md). Follow-up: `filledPrimary` Chip color (#047857), info `Alert` link/button contrast, migration heatmap cells (border + light tint), `Avatar` `imgProps.alt`, default `aria-label` on `CircularProgress`, overview species legend chips (`data-testid` + keyboard) for stable E2E.

## [0.2.8] - 2026-03-28

Накопительный релиз после **v0.2.7**: страница «Система» (метрики, история, посетители), донаты в UI, eBird/датасет/реестр видов и волна багфиксов. Merge: [#185](https://github.com/Gfermoto/BirdLense-Hub/pull/185).

### Changed

- **Документация:** [FEATURES](docs/user/features.md) / [RU](docs/ru/features.ru.md) и [API](docs/contributor/api.md) / [RU](docs/ru/api.ru.md) — эндпоинты «Система»: live-метрики, `/system/metrics/history`, `/system/visitors`.

- **Система / UI:** метрики хоста (`GET /api/ui/system/metrics`) отделены от статистики посетителей (`GET /api/ui/system/visitors?days=…`); смена периода посетителей больше не перезапускает опрос CPU; на странице «Система» — накопительные графики за сессию просмотра (опрос 5 с); убраны карточки кодирования/MQTT; ссылка «Поддержать» в шапке и мобильном меню скрыта на главной (остаётся карточка «Корм» и пункт в меню шестерёнки). Prometheus `/metrics` не выполняет лишних запросов по посетителям.

- **Система / история метрик:** таблица `system_resource_sample`, фоновый sampler (~30 с, хранение 72 ч, отключается `DISABLE_SYSTEM_METRICS_SAMPLER`), `GET /api/ui/system/metrics/history`; графики на «Системе» — серия с сервера + «хвост» живого опроса, выбор окна 6/24/48 ч. Интервал и хранение: `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC`, `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS`; см. CONFIGURATION, `app/.env.example`.

- **Доки деплоя / MCP:** основная площадка в правилах и примерах — LAN **192.168.1.11:22**, UI **http://192.168.1.11:8085/**, MCP **`http://192.168.1.11:8085/mcp`**; публичный пример **`hub.example.com`** — в `deploy.local.sh.example` и MCP_SETUP (без реальных прод-хостов в репозитории).

### Added

- **Региональный топ eBird: авто-пороги классификатора ([#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128)):** процессор подмешивает в эффективные `species_confidence_overrides` виды из топа региона (после `ebird.species_mapping`) с порогом `max(floor, min_confidence_to_process − delta)`; ручные строки важнее; ключи `processor.ebird_regional_top_*`; `PYTHONPATH` процессора включает `/app/web`; см. [CONFIGURATION.md](docs/user/configuration.md).

- **eBird species mapping hints ([#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136)):** `GET /api/ui/settings/ebird-species-mapping-suggestions` и кнопка в настройках — подсказки строк для `ebird.species_mapping` по региональному топу eBird vs каталог; общий кэш топа с фильтром «Региональные» в `ebird_region_service`; см. [CONFIGURATION.md](docs/user/configuration.md).

- **Bird Directory regional filter ([#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132)):** «Региональные» строятся по топу eBird для региона из настроек (как Migration) и по видам с детекциями BirdNET MQTT; в ответе `GET /api/ui/species` — `regional_scope`; кэш списка eBird ~30 мин; дока в [CONFIGURATION.md](docs/user/configuration.md).

- **Donation / support surfaces ([#121](https://github.com/Gfermoto/BirdLense-Hub/issues/121)):** при заданном `general.donate_url` ссылка «Support» / «Поддержать» в шапке (desktop), в мобильном меню и в меню шестерёнки; общий кэш `feed-info` с карточкой Food на Overview; i18n EN/RU/DE; [CONFIGURATION](docs/user/configuration.md) / [ACCESS_CONTROL](docs/contributor/access-control.md).

- **Bird food catalog ([#134](https://github.com/Gfermoto/BirdLense-Hub/issues/134)):** расширен дефолтный список кормов (в т.ч. EU: fat balls, hemp seed, oats, mixes, rapeseed, apple); `seed_bird_food()` идемпотентно добавляет только отсутствующие по `name`; дока в [CONFIGURATION.md](docs/user/configuration.md) / [RU](docs/ru/configuration.ru.md); тест `test_bird_food_seed.py`.

- **Production secrets runbook ([#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)):** [SECRETS_ROTATION.md](archive/internal/docs-legacy/SECRETS_ROTATION.md) / [RU](archive/internal/docs-legacy/SECRETS_ROTATION.ru.md) — перечень env/YAML, порядок ротации, проверка, откат, шаблон экстренной заметки; ссылки из [SECURITY.md](docs/contributor/security.md), [CONFIGURATION.md](docs/user/configuration.md), MkDocs nav.

- **Release hygiene ([#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120)):** `scripts/check-docs-version.py` сверяет корневой `VERSION` с `mkdocs.yml`, `app/ui/package.json` и `app/web/openapi.yaml`; чеклист в [VERSIONING.ru.md](archive/internal/docs-legacy/VERSIONING.ru.md) / [EN](archive/internal/docs-legacy/VERSIONING.md); шаг в CI `openapi-contract`.

- **Species registry (backend):** сервис нормализации видов, API под админ/систему, smoke `test_species_registry.py` и шаг CI в `openapi-contract`; операторская дока в [TESTING.ru.md](docs/ru/testing.ru.md).
- **Dataset export (train-ready):** `dataset_info.json` v2 с `manifest` и `quality`, опциональный `test` split в UI, query `test_ratio` / `strict_quality` на `GET /api/ui/dataset/export`, smoke `test_dataset_export_service.py` в CI; описание в [DATASETS.ru.md](docs/DATASETS.ru.md).
- **Документация:** подготовительный чеклист перед реализацией [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) / [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) — [PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md](archive/internal/docs-legacy/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md) / [EN](archive/internal/docs-legacy/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md); ссылка из [ROADMAP](docs/ROADMAP.ru.md).
- **#54 (CI):** контрактный смоук OpenAPI — новый тест `app/web/tests/test_openapi_contract.py` и job `openapi-contract` в `.github/workflows/ci-pr.yml` (гейт на PR/push в `main`/`dev`).
- **#55 (Migration):** life list / «виды за год» покрывается самой таблицей миграции (фильтр по годам + строки и столбец Σ); отдельный дублирующий блок-чеклист на странице убран.
- **#81 (phase C):** единый журнал ручных правок Unknowns/Video — backend activity `species_correction` + endpoint `GET /api/ui/corrections/recent` + блок последних правок на странице Unknowns.

### Changed

- **Волна A (bugs):** [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) ретроэкспорт с периодом подхватывает сирот без `Video`; retention каскадно удаляет `VideoSpecies`/`SpeciesVisit` как при API удалении записи. [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) poll regenerate spectrograms/tracks с timeout 120s. [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) после удаления видео — возврат по `state.from` или на `/library`.
- **Dataset export:** при `strict_quality=1` и **ready_for_train** экспорт отменяется, если хотя бы один класс не прошёл `min_images_per_class` (явный отказ вместо тихого пропуска); чекбокс в Library; см. [DATASETS.ru.md](docs/DATASETS.ru.md).
- **CodeQL / code scanning:** устранены открытые Python-алерты без «принятия риска» — `urlparse` для источников метаданных, линейный разбор скобок вместо ReDoS-регекса, `_safe_image_path_or_none` для Telegram crop, `mkstemp` в спектрограмме, редактирование URL в логах go2RTC; тесты `test_util_metadata.py`; см. [CODEQL.ru.md](archive/internal/docs-legacy/CODEQL.ru.md).
- **Migration UI:** убран дублирующий блок «чеклист за год» над таблицей — те же виды и суммы уже есть в таблице миграции.
- **#56 (CORS config):** demo-host удалён из hardcoded CORS defaults; теперь базовые non-localhost origins задаются через `CORS_DEFAULT_ORIGINS` (и runtime `CORS_ORIGINS`), что безопаснее для self-hosting.

## [0.2.7] - 2026-03-23

### Changed

- **Отчётность:** без отдельных страниц `PROJECT_REPORTING*` — правила в [docs/contributor/roadmap.md](docs/contributor/roadmap.md) / [RU](docs/ROADMAP.ru.md) и [CONTRIBUTING](CONTRIBUTING.md) / [RU](CONTRIBUTING.ru.md); вести **Issues** и доску, не дублировать политикой в `docs/`.
- **Доки окружения:** примеры UI **https://hub.example.com/**, SSH **`203.0.113.10:2222`** (документационные значения) — [DEPLOY_SERVER](docs/user/deploy-server.md) / [RU](docs/ru/deploy-server.ru.md), [MCP_SETUP](docs/contributor/mcp-setup.md) / [RU](docs/ru/mcp-setup.ru.md), пример [`scripts/deploy.local.sh.example`](scripts/deploy.local.sh.example).
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
- **#47 (maintainer hygiene):** скрипт `scripts/security/scan_git_history_secrets.sh` для прохода по полной git-истории через Gitleaks (Docker) + документированный процесс в [SECURITY](docs/contributor/security.md) / [RU](docs/ru/security.ru.md).

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
- **CI: CodeQL** — workflow `.github/workflows/codeql.yml` (Python `app/web` + `app/processor`, TypeScript `app/ui/src`), конфиги `.github/codeql/`; доки [CODEQL](archive/internal/docs-legacy/CODEQL.md) / [RU](archive/internal/docs-legacy/CODEQL.ru.md), пункты в mkdocs и SITE_MAP; рекомендация расширения **GitHub.vscode-codeql** в `.vscode/extensions.json`; скрипт **`scripts/codeql-local.sh`**; `.gitignore`: **`.tools/`** (локальный CLI, БД, SARIF); в доке — пример triage последнего локального прогона.
- **#82**: на странице видео — кнопки «предыдущий / следующий» ролик за тот же календарный день UTC, что и `start_time`; API `GET /api/ui/videos/:id/neighbors` (`previous_id`, `next_id`, `index`, `total`, `day_utc`).
- Скрипт `scripts/github-project-mark-done.sh` — пометить issue на доске **BirdLense Hub — Roadmap** как **Done** (поля **Status** и **Поток**); см. [CONTRIBUTING](CONTRIBUTING.md).
- Примеры алертинга Prometheus: `examples/prometheus/birdlense.rules.yml`, `examples/prometheus/alertmanager.birdlense.example.yml`; раздел **Alerting** в [CONFIGURATION](docs/user/configuration.md) / RU — закрывает [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).
- `app/ui/package.json`: поле **`engines`** (Node **22.x**, минимум **22.13**; npm **>=10**) — согласовано с CI и UI Docker stage.
- `.vscode/extensions.json` — рекомендуемые расширения (ESLint, Prettier, Docker).
- CI: workflow **`E2E (Playwright)`** (`.github/workflows/e2e-scheduled.yml`) — раз в неделю + `workflow_dispatch`; **не** required в ruleset.
- CI: job **`docker-tests`** — сборка образа `birdlense` + `make test` + `make test-web` на каждый PR/push в `main` и `dev` (см. [TESTING](docs/contributor/testing.md)); в ruleset **Protect** на `main` required checks: **`ui-build`**, **`docs`**, **`docker-tests`**.
- Скрипты GitHub Project: `scripts/github-project-pat-hint.sh`, загрузка `scripts/.env.project`, шаблон `scripts/env.project.example` — **classic PAT** вместо OAuth refresh (без круга device-login).
- Roadmap: секция **Backlog consilium (March 2026)** + 11 активных GitHub Issues [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) для доски Project ([#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) ARM — вне скоупа).
- CI: workflow `prune-branches.yml` — опционально, только **`workflow_dispatch`**: снятие с `origin` веток кроме **`main`** и **`dev`** (без cron; обычная уборка — после merge PR).
- Скрипт `scripts/github-project-add-backlog-consilium.sh` — добавить issues **#46–#57** на доску Project, с пропуском **#49** по умолчанию (`GITHUB_BACKLOG_SKIP_ISSUES`; нужен scope `project` у `gh`).
- `.github/github-social-preview.png` — Open Graph / Social preview для репозитория (1280×640).

### Changed

- **Репозиторий:** расширена документация и шаблоны локального деплоя; в **`.gitignore`** по-прежнему не коммитятся персональные локальные файлы редактора и секреты.
- **CI: CodeQL** — `github/codeql-action` **v3 → v4** ([changelog GitHub](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/)): без предупреждений о Node 20 и deprecation v3 на раннере.
- **Доки CodeQL** (EN/RU): `workflow_dispatch`, **codeql-action@v4** в вводном абзаце; установка расширения в VS Code (CLI, VSIX, ID **`GitHub.vscode-codeql`**). **`.vscode/extensions.json`** — тот же ID издателя.
- ROADMAP (EN/RU): бэклог оператора — issues [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (галерея), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (коррекция видов Unknowns ↔ видео), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (навигация по видео); карточки на Project **BirdLense Hub — Roadmap**.
- Безопасность [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46): rate limit `POST /api/ui/settings/verify-password` — IP клиента за nginx (`client_ip_for_rate_limit`: `X-Real-IP`, `X-Forwarded-For`; nginx передаёт оба для `/api` и `/metrics`), сброс счётчика при успешном входе, **`Retry-After`** при **429**; pytest `TestVerifyPasswordRateLimit`; доки ACCESS_CONTROL / API / SECURITY / TESTING / OPEN_SOURCE_PREP / ROADMAP.
- Политика платформы: **официально только x86/amd64** (Intel/AMD); ARM / aarch64 не поддерживаются и не планируются — ROADMAP, доки, конфиг; бэклог без ARM64 Docker ([#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49)).
- ROADMAP (EN/RU): **триаж** Issue vs Discussion; **Future work candidates** (a11y, E2E, секреты, версии стека, community/donation UX); таблица идей переименована в **Shipped ideas (archive)**; UX-блок выровнен; [ACCESS_CONTROL](docs/contributor/access-control.md) ссылается на кандидатов.
- `chore(deps)`: **@mui/x-charts** 7.x → 8.x в `app/ui` ([#42](https://github.com/Gfermoto/BirdLense-Hub/pull/42)).
- `.gitignore`: `app/data/processor.log*` — ротированные логи процессора не коммитятся.
- GitHub: модель веток — **фича → PR в `dev`**, затем **PR `dev`→`main`**; CONTRIBUTING + шаблон PR; `delete_branch_on_merge=true` (фичи не копятся, `main`/`dev` защищены от удаления). `github-repo-bootstrap.sh` и [GITHUB_SETUP_GH.ru.md](archive/internal/docs-legacy/GITHUB_SETUP_GH.ru.md) §4 обновлены.
- Доки: INSTALL ↔ `scripts/deploy.sh` (контейнер `birdlense`, `DEPLOY_REMOTE_DIR`, rsync, Intel override, исключение **`.tools/`**); пример `deploy.local.sh.example` с `DEPLOY_REMOTE_DIR`; SCENARIOS.ru (Grafana) как в EN; OPEN_SOURCE_PREP.ru — актуальный блок про плейсхолдеры; README / I18N_STATUS / SITE_MAP — формулировки под MkDocs; пути клон `BirdLense-Hub` vs каталог на сервере.
- `app/Makefile`: комментарии деплоя и E2E без захардкоженного LAN IP.
- GitHub: ruleset **Protect** на default branch — обязательны успешные checks **`ui-build`** и **`docs`** (workflow CI); approvals по-прежнему 0 (solo).
- Dependabot — не больше **одного открытого PR на блок** (`open-pull-requests-limit: 1`).
- Локально: remote **`upstream`** к стороннему репозиторию не используется (репозиторий на GitHub — не форк).
- Доки: [LOCAL_DEV](docs/contributor/local-dev.md) / RU — Node 22 (nvm/fnm/Volta), WSL / VS Code, Python **3.11** (приложение) vs **3.12** (MkDocs), venv для доков, чеклист перед релизом; [TESTING](docs/contributor/testing.md) / RU — предупреждение про RAM и OOM при `make test`, workflow E2E по расписанию; [Documentation](docs/contributor/documentation.md) / RU — явное разделение Python для MkDocs и runtime; [CONTRIBUTING](CONTRIBUTING.md) / RU — PR: полный набор тестов; [README](README.md) / RU — блок **Developers**.

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

- Тесты `app/web/tests/test_gallery_upload.py`; смок галереи в [TESTING](docs/contributor/testing.md) §2.6 / [TESTING.ru](docs/ru/testing.ru.md) §8; troubleshooting в [CONFIGURATION](docs/user/configuration.md) → Gallery.
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

- **Роли доступа** — два пароля: `settings_password` (Admin), `contributor_password` (помощник). Contributor: коррекция видов, iNaturalist, отчёты, экспорт датасета. Admin: кормушка, настройки, система. Документ [ACCESS_CONTROL.md](docs/contributor/access-control.md).
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

- **Источник распознавания в UI** — полосы и карточки показывают YOLO, Frigate или BirdNET. Документация: `docs/user/features.md` (таблица Detection source).
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

[Unreleased]: https://github.com/Gfermoto/BirdLense-Hub/compare/v0.3.7...HEAD
[0.3.7]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.7
[0.3.6]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.6
[0.3.5]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.5
[0.3.4]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.3.4
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
