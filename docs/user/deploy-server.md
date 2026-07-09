# Деплой на сервер

## Одноразовый запуск

```bash
cd app && make build && make start
```

## Удалённый деплой (ssh + rsync)

1. Настроить `scripts/deploy.local.sh` (скопировать из `.example`)
2. Указать `DEPLOY_HOST`, `DEPLOY_URL`, опционально `DEPLOY_SSH_PORT`
3. Выполнить:

```bash
make deploy
```

`deploy.sh` синхронизирует код через rsync, собирает образ на сервере и запускает контейнеры.

## Данные не перезаписываются

- `app/data/` — записи и БД
- `app/app_config/user_config.yaml` — настройки

## После деплоя

```bash
make verify   # health check по DEPLOY_URL
```

См. [`runbooks.md`](runbooks.md).