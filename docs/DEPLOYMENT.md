# Деплой BirdLense Hub

## Быстрый старт

```bash
cd BirdLense
make deploy
```

Деплой выполняется на сервер из `.cursor/rules/deploy.mdc` (по умолчанию 192.168.1.11).

## Требования

- SSH-доступ к серверу (`ssh birdlense` или `DEPLOY_HOST` в deploy.local.sh)
- Docker на сервере

## Что делает деплой

1. **Останавливает** старые контейнеры (если есть)
2. **Синхронизирует** код (tar по SSH), исключая:
   - `app/data` — записи и БД
   - `app/app_config/user_config.yaml` — настройки на сервере
   - `scripts/deploy.local.sh` — локальные секреты
3. **Записывает** секреты в `app/.env` (PROCESSOR_SECRET, MCP_TOKEN)
4. **Собирает** и **запускает** контейнер

## Локальные настройки

Создайте `scripts/deploy.local.sh` из `deploy.local.sh.example`:

```bash
export DEPLOY_HOST="birdlense"           # или IP
export DEPLOY_REMOTE_DIR="/root/BirdLense"
export DEPLOY_URL="http://192.168.1.11:8085"
export PROCESSOR_SECRET="ваш-секрет-16+"
export MCP_TOKEN="ваш-mcp-токен"        # опционально
```

**Важно:** `deploy.local.sh` в .gitignore — не коммитится.

## Автодеплой (GitHub Actions)

Push в `main` → автодеплой. Требует self-hosted runner на сервере.

```bash
# Однократная настройка на сервере
./scripts/setup-auto-deploy.sh
```

См. [.github/workflows/deploy.yml](../.github/workflows/deploy.yml).

## Если сервер недоступен

- Соберите локально: `cd app && make build`
- При появлении доступа: `make deploy` — код синхронизируется, данные на сервере не трогаются
- Ручной перенос: скопируйте репозиторий (без `app/data`) на сервер и выполните `make build && make start` в `app/`

## После деплоя

- UI: `DEPLOY_URL` (например http://192.168.1.11:8085)
- Записи не видны? System → «Сканировать и импортировать»
- CORS: при доступе с другого домена добавьте в `app/.env` на сервере: `CORS_ORIGINS=http://ваш-домен`

---

См. также: [INSTALL.md](./INSTALL.md), [CONFIGURATION.md](./CONFIGURATION.md), [TESTING.md](./TESTING.md), [MCP_SETUP.md](./MCP_SETUP.md).
