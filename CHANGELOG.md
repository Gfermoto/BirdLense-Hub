# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

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

[0.1.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.1
[0.1.0]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0
[0.1.0-beta.2]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.1
[0.1.0-alpha.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-alpha.1
