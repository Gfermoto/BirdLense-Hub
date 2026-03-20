# Установка и деплой BirdLense Hub

[English](./INSTALL.md)

BirdLense Hub — мониторинг кормушки: детекция птиц по видео и аудио, записи, аналитика. Docker на x86.

**Сначала:** [OVERVIEW](./OVERVIEW.ru.md) · **Сценарии:** [SCENARIOS](./SCENARIOS.ru.md)

## Требования

| Компонент | Описание |
|-----------|----------|
| **Docker** | x86/amd64, Compose v2 |
| **Go2RTC** | Видеопотоки с IP-камер (standalone или Frigate) |
| **MQTT** (опционально) | Frigate events, BirdNET sightings |

---

## Вариант 1: Готовый образ (рекомендуется)

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: http://localhost:8085

## Вариант 2: Сборка из исходников

```bash
cd BirdLense-Hub/app
make build && make start
```

## Вариант 3: Образ без сборки (для пользователей)

Без клонирования репо — только образ и конфиг:

```bash
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config
# .env: PROCESSOR_SECRET, FLASK_SECRET_KEY (openssl rand -hex 16)
# docker-compose.image.yml из репо app/
docker compose -f docker-compose.image.yml up -d
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. Файлы: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. Intel GPU: `cp docker-compose.intel.example.yml docker-compose.override.yml`.

---

## Первый запуск

1. **Секреты** — `make setup` создаёт `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). Вызывается при `make start`/`make pull`.
2. **Конфиг** — `app/app_config/user_config.yaml`. Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`.
3. **Go2RTC** — Настройки → Видео: URL (`http://IP:1984`).
4. **Камеры** — Настройки → Камеры: stream names из Go2RTC.

---

## Деплой на сервер (make deploy)

```bash
cd BirdLense
make deploy
```

Требуется: SSH (настройте `~/.ssh/config` или `DEPLOY_HOST`), Docker на сервере, локально Node.js для сборки UI.

**Настройки:** скопируйте `scripts/deploy.local.sh.example` в `deploy.local.sh` и задайте DEPLOY_HOST, DEPLOY_REMOTE_DIR, DEPLOY_URL, секреты. Файл в .gitignore.

**Что делает:** останавливает контейнеры, собирает UI локально, rsync (исключая data, user_config), записывает секреты в .env, собирает Docker, запускает.

**Автодеплой:** `./scripts/setup-auto-deploy.sh` на сервере → push в main → автодеплой (self-hosted runner).

**Сервер недоступен:** `cd app && make build` локально; при появлении доступа — `make deploy` (данные не трогаются).

---

## Проверка

- **Health:** `curl http://localhost:8085/api/ui/health`
- **Камеры:** Настройки → Камеры
- **Live:** видеопоток с оверлеем

Записи не видны? System → «Сканировать и импортировать».

---

## Данные

| Путь | Содержимое |
|------|------------|
| `app/data/recordings/` | Видеозаписи (YYYY/MM/DD/HHMMSS/video.mp4) |
| `app/data/db/birdlense.db` | SQLite |
| `app/app_config/user_config.yaml` | Пользовательский конфиг |

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [SCENARIOS.md](./SCENARIOS.md), [TROUBLESHOOTING.md](./TROUBLESHOOTING.md), [SECURITY.md](./SECURITY.md).
