# Установка и деплой BirdLense Hub

[English](./INSTALL.md)

BirdLense Hub — мониторинг кормушки: детекция птиц по видео и аудио, записи, аналитика. Docker только на **x86_64** (Intel или AMD).

**Сначала:** [OVERVIEW](./OVERVIEW.ru.md) · **Сценарии:** [SCENARIOS](./SCENARIOS.ru.md)

## Требования

| Компонент | Описание |
|-----------|----------|
| **Docker** | **x86_64 / amd64** (Intel или AMD), Compose v2 — ARM/aarch64 не поддерживаются |
| **Go2RTC** | Видеопотоки с IP-камер (standalone или Frigate) |
| **MQTT** (опционально) | Frigate events, BirdNET sightings |

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

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`. Файлы: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. Intel GPU: `cp docker-compose.intel.example.yml docker-compose.override.yml`.

---

## Первый запуск

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

**Два пути на VPS:** рабочий код и данные деплоя — под **`/root/BirdLense`** (или ваш `DEPLOY_REMOTE_DIR`). Каталог **`/opt/birdlense`** в старых заметках и скриптах — только исторический пример; отдельная копия БД там может остаться от прошлых установок — ориентируйтесь на каталог из `deploy.local.sh` и mount контейнера (`docker inspect birdlense` → `/app/data`).

**Логи контейнера:** сообщения **h264/rtsp** от декодера потока часто не критичны; уровень шума снижен через `OPENCV_*` в образе. Стартовое уведомление в Telegram отправляется с короткой задержкой после подъёма API, чтобы прокси успел подняться.

**Что делает:** останавливает и удаляет контейнер `birdlense`, собирает UI локально, rsync (без `app/data`, без `app/app_config/user_config.yaml`, без `.tools/` — локальный CodeQL, без venv и `site/`), дописывает секреты в `app/.env` на сервере, при Intel GPU выставляет override, на сервере в `app/` — `make build && make start`.

**Автодеплой:** `./scripts/setup-auto-deploy.sh` на сервере → push в main → workflow **Deploy** в GitHub Actions (self-hosted runner с метками `self-hosted`, `birdlense`). Если запуск долго **Queued** — runner не в сети или не зарегистрирован; до починки используйте **`make deploy`** с вашей машины.

**Сервер недоступен:** `cd app && make build` локально; при появлении доступа — `make deploy` (данные не трогаются).

**Пошаговый чеклист** (подготовка, проверка, типичные проблемы): [DEPLOY_SERVER.ru](./DEPLOY_SERVER.ru.md).

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

## Что дальше в бэклоге

Рекомендуемый следующий фокус (на выбор): [**#285**](https://github.com/Gfermoto/BirdLense-Hub/issues/285) — nginx / раздача записей (auth или allowlist); [**#297**](https://github.com/Gfermoto/BirdLense-Hub/issues/297) — CI, OpenAPI→TS, политика аудитов. Для жёсткой безопасности API смотрите открытые **P0/P1** в репозитории ([#279](https://github.com/Gfermoto/BirdLense-Hub/issues/279), [#278](https://github.com/Gfermoto/BirdLense-Hub/issues/278)).

---

См. также: [CONFIGURATION](./CONFIGURATION.ru.md) · [SCENARIOS](./SCENARIOS.ru.md) · [GLOSSARY](./GLOSSARY.ru.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.ru.md) · [политика безопасности](./project/security-policy.md).
