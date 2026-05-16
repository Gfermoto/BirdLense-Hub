# Установка и деплой BirdLense Hub

[English](../user/install.md)

BirdLense Hub — мониторинг кормушки: детекция птиц по видео и аудио, записи, аналитика. Docker только на **x86_64** (Intel или AMD).

**Сначала:** [OVERVIEW](./overview.ru.md) · **Сценарии:** [SCENARIOS](./scenarios.ru.md)

## Требования

| Компонент | Описание |
|-----------|----------|
| **Docker** | **x86_64 / amd64** (Intel или AMD), Compose v2 — ARM/aarch64 не поддерживаются |
| **Go2RTC** | Видеопотоки с IP-камер (standalone или Frigate) |
| **MQTT** (опционально) | Frigate events; BirdNET (любой совместимый источник JSON, чаще BirdNET-Go или BirdNET-Pi) |

---

## Вариант 1: Одна команда из корня репозитория (рекомендуется)

**Без обязательного `make`** на первом шаге:

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub
./install.sh
```

Скрипт: Docker → `app/scripts/setup-env.sh` (`app/.env`) → сборка и запуск стека → **`scripts/verify-stack.sh`**.

**Готовый образ** (без локальной сборки Docker-образа):

```bash
./install.sh --pull
```

То же: `make install` / `make install-pull` из корня репозитория.

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: `http://127.0.0.1:8085` (или `BIRDLENSE_PORT`).

## Вариант 2: Только через Make (эквивалент варианту 1)

```bash
cd BirdLense-Hub
make install
# или
make install-pull
```

## Вариант 3: Сборка из исходников

```bash
cd BirdLense-Hub/app
make build && make start
```

Проверка из корня репозитория:

```bash
cd ..
make verify
```

## Вариант 4: Образ без сборки (для пользователей)

Без клонирования репо — только образ и конфиг (**один** сервис `birdlense` в `docker-compose.image.yml`). Полный **git clone** использует **`app/docker-compose.yml`**, где дополнительно поднимается **Redis** (`birdlense-redis`) под дефолтный `REDIS_URL`; в этом минимальном варианте Redis **нет**:

```bash
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config
# Скачайте из репозитория файлы app/docker-compose.image.yml и app/.env.example, затем:
cp .env.example .env
# Заполните .env: PROCESSOR_SECRET, FLASK_SECRET_KEY (например openssl rand -hex 16).
# Опционально: BIRDLENSE_IMAGE=… для своего registry (см. docker-compose.image.yml).
docker compose -f docker-compose.image.yml up -d
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. Файлы: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. **Intel GPU:** из каталога `app/` выполните `bash scripts/docker-compose-intel-override-gen.sh` (все `card*`/`renderD*`, `group_add` video/render, `CAP_PERFMON`) или см. `docker-compose.intel.example.yml` для ручной правки GID. Если в логах **`Failed to initialize PMU`** при этом уже есть `PERFMON` в compose — на **хосте** (не в контейнере) ослабьте **`kernel.perf_event_paranoid`**: `make deploy` и CI при наличии `docker-compose.override.yml` пишут **`/etc/sysctl.d/99-birdlense-perf.conf`** со значением **0** и вызывают `sysctl -p` (дефолт **3** на части VPS режет perf; если **0** мало — вручную **`sudo sysctl kernel.perf_event_paranoid=-1`** или контейнер с **`privileged: true`** в override).

---

## Первый запуск

**Тома Docker и uid:** процессы в контейнере `birdlense` идут от пользователя **birdlense (uid 1000)**. При старте entrypoint от root делает `chown` на примонтированные `./data` и `./app_config`. Если `chown` на вашей ФС недоступен, с хоста из каталога `app/`: `chown -R 1000:1000 data app_config`.

1. **Секреты** — `app/scripts/setup-env.sh` создаёт `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). Его вызывает `./install.sh`; также он задействован в `make setup` / `make start` / `make pull`.
2. **Конфиг** — `app/app_config/user_config.yaml`. Пример из каталога **`app/`** репозитория: `cp configs/minimal.yaml app_config/user_config.yaml`.
3. **Go2RTC** — Настройки → Видео: URL (`http://IP:1984`).
4. **Камеры** — Настройки → Камеры: stream names из Go2RTC.

---

## Деплой на сервер (make deploy)

```bash
cd BirdLense-Hub   # корень клона (имя после git clone; своё имя — нормально)
make deploy
```

Требуется: SSH (`~/.ssh/config` или `DEPLOY_HOST`, при необходимости **`DEPLOY_SSH_PORT`**), Docker на сервере, локально **Node.js 22 и npm 10+** — `scripts/deploy.sh` выполняет **`npm ci && npm run build`** в `app/ui` на вашей машине до rsync.

**Настройки:** скопируйте `scripts/deploy.local.sh.example` в `deploy.local.sh` и задайте `DEPLOY_HOST`, `DEPLOY_URL`, секреты; при необходимости `DEPLOY_REMOTE_DIR`. Файл в .gitignore.

**Каталог на сервере:** в `scripts/deploy.sh` по умолчанию `DEPLOY_REMOTE_DIR=/root/BirdLense`. Имя локальной папки клона (`BirdLense-Hub` или своё) с этим не связано.

**Что делает:** останавливает и удаляет контейнер **`birdlense`** (контейнер **`birdlense-redis`** не трогает), собирает UI **локально**, **rsync** с исключениями как в `scripts/deploy.sh` (в т.ч. **`datasets/`**, **`app/data/`**, **`app/.env`**, **`app/app_config/user_config.yaml`**, **`.tools/`**, **`.venv-ci`** / **`.venv-docs`**, `app/.venv`, `site/`, кэши ruff/pytest), дописывает секреты в **`app/.env`** на сервере (`MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, опционально **`BIRDLENSE_STRICT_API_AUTH`** / **`BIRDLENSE_UI_API_KEY`** — см. [CONFIGURATION.ru.md](./configuration.ru.md), [SECRETS_ROTATION.ru.md](../../archive/internal/docs-legacy/SECRETS_ROTATION.ru.md)), при наличии `/dev/dri/renderD*` — **`bash scripts/docker-compose-intel-override-gen.sh`**, на сервере в `app/` — **`make build && make start`**, затем **`scripts/verify-stack.sh`** для **`DEPLOY_URL`** (health, readiness, status, камеры при доступности).

**Автодеплой:** `./scripts/setup-auto-deploy.sh` на сервере → push в main → workflow **Deploy** в GitHub Actions (self-hosted runner с метками `self-hosted`, `birdlense`). Если запуск долго **Queued** — runner не в сети или не зарегистрирован; до починки используйте **`make deploy`** с вашей машины.

**Сервер недоступен:** `cd app && make build` локально; при появлении доступа — `make deploy` (данные не трогаются).

**Пошаговый чеклист**, пути на VPS, логи и типичные сбои: [DEPLOY_SERVER.ru](./deploy-server.ru.md).

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

См. также: [CONFIGURATION](./configuration.ru.md) · [SCENARIOS](./scenarios.ru.md) · [GLOSSARY](./glossary.ru.md) · [TROUBLESHOOTING](./troubleshooting.ru.md) · [политика безопасности](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SECURITY.md).
