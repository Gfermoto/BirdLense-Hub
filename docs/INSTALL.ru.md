# Установка и деплой BirdLense Hub

[English](./INSTALL.md)

BirdLense Hub — мониторинг кормушки: детекция птиц по видео и аудио, записи, аналитика. Docker только на **x86_64** (Intel или AMD).

**Сначала:** [OVERVIEW](./OVERVIEW.ru.md) · **Сценарии:** [SCENARIOS](./SCENARIOS.ru.md)

## Требования

| Компонент | Описание |
|-----------|----------|
| **Docker** | **x86_64 / amd64** (Intel или AMD), Compose v2 — ARM/aarch64 не поддерживаются |
| **Go2RTC** | Видеопотоки с IP-камер (standalone или Frigate) |
| **MQTT** (опционально) | Frigate events; BirdNET (любой совместимый источник JSON, чаще BirdNET-Go или BirdNET-Pi) |

---

## Вариант 1: Одношаговая установка в Docker

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub
./install.sh
```

Скрипт сам проверит Docker, при необходимости поставит его, создаст `app/.env` и поднимет стек из контейнеров.

## Вариант 2: Готовый образ (рекомендуется)

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: http://localhost:8085

## Вариант 3: Сборка из исходников

```bash
cd BirdLense-Hub/app
make build && make start
```

## Вариант 4: Образ без сборки (для пользователей)

Без клонирования репо — только образ и конфиг:

```bash
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config
# .env: PROCESSOR_SECRET, FLASK_SECRET_KEY (openssl rand -hex 16)
# docker-compose.image.yml из репо app/
docker compose -f docker-compose.image.yml up -d
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. Файлы: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. **Intel GPU:** из каталога `app/` выполните `bash scripts/docker-compose-intel-override-gen.sh` (все `card*`/`renderD*`, `group_add` video/render, `CAP_PERFMON`) или см. `docker-compose.intel.example.yml` для ручной правки GID.

---

## Первый запуск

**Тома Docker и uid:** процессы в контейнере `birdlense` идут от пользователя **birdlense (uid 1000)**. При старте entrypoint от root делает `chown` на примонтированные `./data` и `./app_config`. Если `chown` на вашей ФС недоступен, с хоста из каталога `app/`: `chown -R 1000:1000 data app_config`.

1. **Секреты** — `make setup` создаёт `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). Вызывается при `make start`/`make pull`, а также из `./install.sh`.
2. **Конфиг** — `app/app_config/user_config.yaml`. Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`.
3. **Go2RTC** — Настройки → Видео: URL (`http://IP:1984`).
4. **Камеры** — Настройки → Камеры: stream names из Go2RTC.

---

## Деплой на сервер (make deploy)

```bash
cd BirdLense-Hub   # корень клона (имя после git clone; своё имя — нормально)
make deploy
```

Требуется: SSH (настройте `~/.ssh/config` или `DEPLOY_HOST`), Docker на сервере, локально Node.js для сборки UI.

**Настройки:** скопируйте `scripts/deploy.local.sh.example` в `deploy.local.sh` и задайте `DEPLOY_HOST`, `DEPLOY_URL`, секреты; при необходимости `DEPLOY_REMOTE_DIR`. Файл в .gitignore.

**Каталог на сервере:** в `scripts/deploy.sh` по умолчанию `DEPLOY_REMOTE_DIR=/root/BirdLense`. Имя локальной папки клона (`BirdLense-Hub` или своё) с этим не связано.

**Что делает:** останавливает и удаляет контейнер `birdlense`, собирает UI локально, rsync (без `app/data`, без `app/app_config/user_config.yaml`, без `.tools/` — локальный CodeQL, без venv и `site/`), дописывает секреты в `app/.env` на сервере (`MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, опционально **`BIRDLENSE_STRICT_API_AUTH`** / **`BIRDLENSE_UI_API_KEY`** — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md), [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md)), при наличии `/dev/dri/renderD*` запускает **`bash scripts/docker-compose-intel-override-gen.sh`** (VA-API + метрики GPU), на сервере в `app/` — `make build && make start`.

**Автодеплой:** `./scripts/setup-auto-deploy.sh` на сервере → push в main → workflow **Deploy** в GitHub Actions (self-hosted runner с метками `self-hosted`, `birdlense`). Если запуск долго **Queued** — runner не в сети или не зарегистрирован; до починки используйте **`make deploy`** с вашей машины.

**Сервер недоступен:** `cd app && make build` локально; при появлении доступа — `make deploy` (данные не трогаются).

**Пошаговый чеклист**, пути на VPS, логи и типичные сбои: [DEPLOY_SERVER.ru](./DEPLOY_SERVER.ru.md).

### HTTPS / nginx и большие upload (Библиотека → прогон с диска)

Если **413** при загрузке mp4, а в UI всё ещё «лимит 2048 МиБ» — на сервере старый `default_config`/`user_config` **или** **прокси** режет тело запроса **до** Flask. В образе хаба лимит тела запроса поднят (`MAX_CONTENT_LENGTH` в `web/config.py`, переопределение **`FLASK_MAX_CONTENT_LENGTH`** в байтах). Nginx **внутри** контейнера Hub уже задаёт **`client_max_body_size 64g`** (`app/nginx/docker-nginx-main.conf`). Если перед контейнером стоит **ещё один** reverse proxy (TLS на хосте и т.п.), поднимите лимит и там, например:

```nginx
location /api/ {
    client_max_body_size 16g;
    proxy_pass http://127.0.0.1:8085;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Подберите **client_max_body_size** под ваши ролики; в YAML смотрите **`video.file_test_max_upload_mb`** (по умолчанию в репозитории **10240** MiB после обновления).

### Telegram proxy autorotate (одной кнопкой)

После первого успешного `make deploy` (чтобы скрипты попали на сервер):

```bash
cd BirdLense-Hub
make proxy-rotation-install
```

Готово: на сервере будет cron, который раз в 6 часов подбирает рабочий SOCKS5-прокси для Telegram API и применяет его только при изменении.

Полезные команды:

```bash
make proxy-rotation-status   # показать расписание и последние логи
make proxy-rotation-remove   # отключить autorotate
make refresh-telegram-proxy  # разовый запуск подбора прямо сейчас
```

Если в `status` видно `not installed`, сначала проверьте `scripts/deploy.local.sh` (DEPLOY_HOST/DEPLOY_SSH_PORT) и повторите `make proxy-rotation-install`.

---

## Проверка

- **Health:** `curl http://localhost:8085/api/ui/health`
- **Камеры:** Настройки → Камеры
- **Live:** видеопоток с оверлеем
- **Бэкап БД:** System → Storage → «Скачать бэкап БД»

Записи не видны? System → «Сканировать и импортировать».

---

## Данные

| Путь | Содержимое |
|------|------------|
| `app/data/recordings/` | Видеозаписи (YYYY/MM/DD/HHMMSS/video.mp4) |
| `app/data/db/birdlense.db` | SQLite |
| `app/app_config/user_config.yaml` | Пользовательский конфиг |

---

См. также: [CONFIGURATION](./CONFIGURATION.ru.md) · [SCENARIOS](./SCENARIOS.ru.md) · [GLOSSARY](./GLOSSARY.ru.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) · [политика безопасности](./project/security-policy.md).
