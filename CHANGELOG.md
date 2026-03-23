# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

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

- **[AGENTS.md](AGENTS.md)** — инструкция для агентов: доводить задачи до конца (тесты, CHANGELOG/docs, push, PR на `main`, `make deploy`); ссылка из [CONTRIBUTING.md](CONTRIBUTING.md).
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

- **Репозиторий:** в git добавлено **`.cursor/rules/deploy.mdc`** (правило деплоя для Cursor); в **`.gitignore`** — исключение только для этого файла, остальной `.cursor/` по-прежнему не коммитится.
- **CI: CodeQL** — `github/codeql-action` **v3 → v4** ([changelog GitHub](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/)): без предупреждений о Node 20 и deprecation v3 на раннере.
- **Доки CodeQL** (EN/RU): `workflow_dispatch`, **codeql-action@v4** в вводном абзаце; установка расширения в Cursor/VS Code (CLI, VSIX, ID **`GitHub.vscode-codeql`**). **`.vscode/extensions.json`** — тот же ID издателя.
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
- Доки: [LOCAL_DEV](docs/LOCAL_DEV.md) / RU — Node 22 (nvm/fnm/Volta), WSL/Cursor, Python **3.11** (приложение) vs **3.12** (MkDocs), venv для доков, чеклист перед релизом; [TESTING](docs/TESTING.md) / RU — предупреждение про RAM и OOM при `make test`, workflow E2E по расписанию; [Documentation](docs/Documentation.md) / RU — явное разделение Python для MkDocs и runtime; [CONTRIBUTING](CONTRIBUTING.md) / RU — PR: полный набор тестов; [README](README.md) / RU — блок **Developers**.

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
- **Сообщество:** `GOVERNANCE`, `CODEOWNERS`, шаблон PR; инструкция настройки репозитория через `gh` (`GITHUB_SETUP_GH`); `WIKI_AUTOMATION`; черновик материала в `article/habr.md`.

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
