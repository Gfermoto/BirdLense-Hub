# Деплой BirdLense Hub

## Быстрый старт

```bash
cd BirdLense
make deploy
```

Деплой выполняется на сервер из `scripts/deploy.local.sh` (см. `deploy.local.sh.example`).

## Требования

- SSH-доступ к серверу (`ssh birdlense` или `DEPLOY_HOST` в deploy.local.sh)
- Docker на сервере
- Локально: Node.js для сборки UI (npm run build)

## Что делает деплой

1. **Останавливает** старые контейнеры (если есть)
2. **Собирает UI локально** — `npm run build` в `app/ui` (обход ETIMEDOUT npm на сервере)
3. **Синхронизирует** код (rsync), исключая:
   - `app/data` — записи и БД
   - `app/app_config/user_config.yaml` — настройки на сервере
   - `scripts/deploy.local.sh` — локальные секреты
4. **Записывает** секреты в `app/.env` на сервере: PROCESSOR_SECRET, FLASK_SECRET_KEY, BIRDLENSE_ENV, MCP_TOKEN
5. **Собирает** Docker (использует pre-built UI) и **запускает** контейнер

## Локальные настройки

Создайте `scripts/deploy.local.sh` из `deploy.local.sh.example`:

```bash
export DEPLOY_HOST="birdlense"           # или IP
export DEPLOY_REMOTE_DIR="/root/BirdLense"
export DEPLOY_URL="https://birdlense.example.com"
export BIRDLENSE_ENV="production"
export FLASK_SECRET_KEY="случайная-строка-32+"
export PROCESSOR_SECRET="ваш-секрет-16+"
export MCP_TOKEN="ваш-mcp-токен"        # опционально
```

**Важно:** `deploy.local.sh` в .gitignore — не коммитится. Секреты не попадают в репозиторий.

## Автодеплой (GitHub Actions)

Push в `main` → автодеплой. Требует self-hosted runner на сервере.

```bash
# Однократная настройка на сервере
./scripts/setup-auto-deploy.sh
```

См. [.github/workflows/deploy.yml](../.github/workflows/deploy.yml).

## Развёртывание из готового образа (для пользователей)

Если нужно раздать BirdLense **без сборки** — только образ и конфиг: см. [DEPLOY_USER_STANDALONE.md](DEPLOY_USER_STANDALONE.md). Пользователь копирует `app/docker-compose.image.yml` и `.env.example`, заполняет `.env`, выполняет `docker compose -f docker-compose.image.yml up -d`. Образ можно публиковать в GitHub Container Registry или свой registry.

## Если сервер недоступен

- Соберите локально: `cd app && make build`
- При появлении доступа: `make deploy` — код синхронизируется, данные на сервере не трогаются
- Ручной перенос: скопируйте репозиторий (без `app/data`) на сервер и выполните `make build && make start` в `app/`

## После деплоя

- UI: `DEPLOY_URL` (например http://YOUR_HOST:8085)
- Записи не видны? System → «Сканировать и импортировать»
- CORS: при доступе с другого домена добавьте в `app/.env` на сервере: `CORS_ORIGINS=http://ваш-домен`

---

См. также: [INSTALL.md](./INSTALL.md), [CONFIGURATION.md](./CONFIGURATION.md), [TESTING.md](./TESTING.md), [MCP_SETUP.md](./MCP_SETUP.md).
