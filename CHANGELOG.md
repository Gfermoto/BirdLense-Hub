# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **GitHub (репозиторий):** включены Discussions и Issues; метки `area:*`, `priority:*`, `triage`; вехи `v0.2.3`, `Backlog (no milestone)`; приветственная Discussion; скрипт `scripts/github-bootstrap-project.sh` для создания Project v2 после `gh auth refresh -s project`.
- **CI:** PR workflow builds `app/ui` and runs docs checks (`check-docs-version.py` + `mkdocs build --strict`).
- **Docs:** interactive OpenAPI (Redoc) pages under `docs/reference/`; nav entries in `mkdocs.yml`.
- **Community:** issue template `good_first_issue`, Discussions link in issue chooser; ROADMAP / CONTRIBUTING (EN+RU) — public priorities and `good first issue` guidance.

### Changed

- **GitHub Pages:** docs workflow triggers on `VERSION` and `scripts/check-docs-version.py` changes; build is strict.
- **GitHub Actions:** `actions/checkout@v6`, `setup-python@v6`, `setup-node@v6`, `upload-pages-artifact@v4`, `upload-artifact@v6`, Docker actions (buildx/login/metadata/build-push v4/v4/v6/v7) — актуальные рантаймы, меньше предупреждений про Node.js 20.

### Fixed

- **MkDocs:** баннер версии через `overrides/main.html` (`{% block announce %}`): в community Material `theme.announcement` в `mkdocs.yml` не рендерится — баннер был пустым; после деплоя отображается **v** из `extra.site_version`.
- **Docs (MkDocs strict):** ссылки на корень репозитория и `docs/archive/` — на blob GitHub, чтобы `mkdocs build --strict` проходил в CI.

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
