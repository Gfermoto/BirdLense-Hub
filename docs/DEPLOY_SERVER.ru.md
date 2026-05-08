# Деплой BirdLense Hub на сервер (RU)

Короткая рабочая инструкция для прод-сервера без лишних шагов. Контекст и ссылки: [INSTALL.ru](./INSTALL.ru.md) § *Деплой на сервер*.

[English](./DEPLOY_SERVER.md)

## 1) Подготовка

- На локальной машине должен быть доступ к серверу по SSH.
- В корне репозитория создайте `scripts/deploy.local.sh` (можно копией из `scripts/deploy.local.sh.example`).
- Минимум нужно задать:
  - `DEPLOY_HOST` — SSH-цель (удобно alias из `~/.ssh/config`)
  - `DEPLOY_URL` — базовый URL хаба для **`scripts/verify-stack.sh`** после деплоя (например `http://192.168.1.11:8085` или `https://ваш.домен/`)
  - при необходимости `DEPLOY_REMOTE_DIR` (на сервере по умолчанию **`/root/BirdLense`**)
  - при необходимости **`DEPLOY_SSH_PORT`**, если SSH не на порту 22

Пример:

```bash
export DEPLOY_HOST="root@192.168.1.11"
export DEPLOY_URL="http://192.168.1.11:8085"
```

### Сначала IP:порт; домен и reverse proxy — позже

Заходите на хаб по **`http://<хост>:<порт>`** (в контейнере nginx слушает **8080**, на хосте проброс через **`BIRDLENSE_PORT`**, часто **8085**). **`DEPLOY_URL`**, а при ошибках CORS в браузере — **`CORS_ORIGINS`** в **`app/.env`** на сервере, задайте **ровно этим же URL** (схема + хост + порт).

Отдельный **reverse proxy** перед стеком и **DNS-имя** для работы **не обязательны**: контейнер сам отвечает по HTTP на выбранном порту. Когда появятся **домен и TLS** (и при желании внешний прокси), поменяйте **`DEPLOY_URL`**, **`CORS_ORIGINS`** и публичные URL в интеграциях; если TLS обрывает доверенный прокси — **`TRUSTED_PROXY=1`**, см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

### 1.5 Pre-flight: окружение production (VPS / публичный URL)

При **`BIRDLENSE_ENV=production`** проверьте **`app/.env`** на сервере (или локально до rsync) на соответствие production gates в [AGENTS.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/AGENTS.md) — длина **`FLASK_SECRET_KEY`** / **`PROCESSOR_SECRET`**, **`BIRDLENSE_STRICT_API_AUTH=1`**, при необходимости токен MCP для `/mcp`:

```bash
./scripts/verify-prod-env.sh --env-file app/.env
# или: ENV_FILE=/путь/к/.env make verify-prod-env
```

Если **`BIRDLENSE_ENV`** ещё не `production`, задайте **`VERIFY_PROD_ENV=1`** для тех же проверок. Для обязательного MCP: **`./scripts/verify-prod-env.sh --require-mcp-token`**.

Для **UI с другого origin** (другой хост/порт, чем API) задайте **`CORS_ORIGINS`** / **`CORS_DEFAULT_ORIGINS`** / **`CORS_LOCAL_DEV_ORIGINS`** — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

## 2) Деплой

Из корня репозитория:

```bash
make deploy
```

Что делает команда (см. `scripts/deploy.sh`):

1. Останавливает и удаляет контейнер **`birdlense`** (если есть **`birdlense-redis`**, его не трогает).
2. На **вашей машине** выполняет **`npm ci && npm run build`** в **`app/ui`** — нужны **Node.js 22** и **npm 10+**.
3. **rsync** кода на сервер (без `app/data`, `datasets/`, `app/.env`, `user_config.yaml`, `.venv-ci`, `.venv-docs`, `.tools/`, кэшей и т.д.).
4. На сервере в `app/`: **`make stop`**, **`make build`**, **`make start`**.
5. Запускает **`scripts/verify-stack.sh`** с **`BASE_URL=${DEPLOY_URL}`** (health, readiness, status, камеры при доступности).

## 3) Проверка после деплоя

- Откройте UI по вашему **`DEPLOY_URL`** (порт **8085**, если не меняли **`BIRDLENSE_PORT`**).
- Из **корня репозитория** на ноутбуке — тот же контракт, что после **`make deploy`**:

```bash
BASE_URL=http://<server>:8085 make verify
```

(`make verify` вызывает **`scripts/verify-stack.sh`**.)

- Или вручную:

```bash
curl -sS http://<server>:8085/api/ui/health
curl -sS http://<server>:8085/api/ui/readiness
curl -sS http://<server>:8085/api/ui/status
```

Для **health** ожидается `{"status":"ok"}`, для **readiness** — `"ready": true`, для **status** — `"web": "ok"`.

## 4) Важно про данные

При стандартном деплое не перезаписываются:

- `app/data/` (записи и БД),
- `app/app_config/user_config.yaml` (пользовательские настройки).

## 5) Частые проблемы

- **`Password required` в system API**  
  Нужна авторизованная сессия (через UI или `verify-password` endpoint).
- **UI показывает старую версию**  
  Очистите кэш PWA/Service Worker в браузере и перезагрузите страницу.
- **Порт занят**  
  Проверьте значение `BIRDLENSE_PORT` и занятые порты на сервере.

## 6) Каталог на сервере

- Рабочий корень после `make deploy` — **`/root/BirdLense`** (или значение `DEPLOY_REMOTE_DIR` в `deploy.local.sh`). Проверка: `docker inspect birdlense` → монтирование **`/app/data`** должно указывать на `…/app/data` этого каталога.
- В старых инструкциях встречался путь **`/opt/birdlense`** — это не дефолт скриптов репозитория; вторая копия `birdlense.db` там может остаться от прошлой установки. Ориентируйтесь на `deploy.local.sh`, а не на произвольный каталог на диске.

## 7) Логи контейнера

- Сообщения **h264 / rtsp** в логах часто идут от декодера видеопотока и не означают сбой веб-части; в образе заданы переменные **`OPENCV_*`** для снижения шума.
- Стартовое уведомление в **Telegram** отправляется с небольшой задержкой после подъёма API, чтобы успел подняться SOCKS/прокси (см. код `notify_app_startup`).

## 8) Прямые URL к записям (`/data/recordings/`)

По умолчанию nginx отдаёт **`/data/recordings/`** как статику без отдельной HTTP-auth. Для публичного доступа задайте **`BIRDLENSE_HIDE_DIRECT_RECORDINGS=1`** в `app/.env` — хаб не добавит этот `location`, анонимный **`GET /data/recordings/...`** → **403**; в UI клипы идут через **`/api/ui/videos/:id/stream`**.

Иные варианты (allowlist по IP, только reverse-proxy) — [SECURITY.ru.md §3](./SECURITY.ru.md) и `app/nginx/examples/recordings_allowlist.conf.snippet`.
