# Changelog

All notable changes to BirdLense Hub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Telegram-уведомления** — вместо ntfy: бот отправляет сообщения в канал или чат. Настройки: токен бота, chat_id, base_url для ссылок.
- **Расширения Telegram** — parse_mode HTML, кнопка «Open Live», тихие сообщения (disable_notification), protect_content, message_thread_id для топиков, link_preview отключён.
- **Telegram Bot API 9.4/9.5** — кнопки с эмодзи и стилем (primary), динамическое время `<tg-time format="r">`, опция `link_preview_large` для больших превью ссылок.
- **sendPhoto** — при `processor.save_images: true` отправляется фото детекции в Telegram.
- **sendPaidMedia** — раздельные настройки: Stars за просмотр (0–25000) и за пересылку/копирование (при бесплатном просмотре: 0=разрешить, >0=запретить).

### Changed

- **Уведомления** — ntfy полностью заменён на Telegram Bot API.

### Removed

- **ntfy** — убран из nginx (порт 8081), deploy.sh, UI.

### Fixed

- **Защита по паролю** — единая точка входа: пароль запрашивается при нажатии на иконку шестерёнки (настройки). После ввода пароля открывается меню «Настройки» и «Система», доступны обе страницы. Прямой переход по URL также защищён.
- **Картинки птиц (Wikipedia)** — регрессия в 7da0a06: код добавлял BASE_URL к image_url, ломая полные URL из Wikipedia. Добавлен resolveImageUrl(): абсолютные URL (http/https/data:) — как есть, относительные — с BASE_URL.
- **Распознавание (PROCESSOR_SECRET)** — в deploy.sh переменные были в одинарных кавычках, в .env попадало буквально `${PROCESSOR_SECRET}` вместо значения. Исправлено: двойные кавычки, printf для безопасной записи.
- **Деплой** — docker-compose: env_file + FLASK_SECRET_KEY; entrypoint: exit 1 при неудачном health check; deploy: предупреждение DEPLOY_URL, копирование .env.example при первом деплое; имена контейнеров приведены к текущей схеме (birdlense).
- **Processor API** — timeout 30s, retry при 5xx.
- **VideoPlayer** — сброс view при смене видео без спектрограммы.
- **MQTT** — reconnect при обрыве (aggregator, Frigate, feed_service).
- **Конфиг** — валидация YAML (логирование при ошибке, fallback на пустой dict).
- **get_go2rtc_upstream** — путь к конфигу через APP_CONFIG_DIR.

---

## [0.1.0-beta.1] - 2026-03-10

### Added

- **Coverage** — pytest-cov, `make test-coverage`, `make test-report`, `.coveragerc`
- **PROCESSOR_SECRET** — автогенерация при деплое, запись в `app/.env` на сервере
- Документация: заметка о смене пароля при утечке, E2E требует пароль при защите настроек

### Changed

- **util.py** — путь к `hierarchy_names.txt` через `__file__` (работает при любом cwd)
- **Makefile** — volume `-v $(pwd):/app` для test/test-web/test-coverage (локальный код)
- **TESTING.md** — приоритетные модули для расширения покрытия

### Removed

- **CPU temperature** — убрана из системных метрик (API, UI, OpenAPI)
- **Orphan containers** — удалены старые контейнеры (nginx, processor, web, ntfy)

### Fixed

- Web API тесты падали из-за `seed/hierarchy_names.txt` — исправлен путь

---

## [0.1.0-alpha.1]

Первый альфа-релиз. См. [README.md](./README.md) для обзора возможностей.

[0.1.0-beta.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-beta.1
[0.1.0-alpha.1]: https://github.com/Gfermoto/BirdLense-Hub/releases/tag/v0.1.0-alpha.1
