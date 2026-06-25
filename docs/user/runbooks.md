# Runbook оператора

## Ежедневные проверки

```bash
# Health
make verify

# Логи
make logs

# GPU
docker exec birdlense nvidia-smi
```

## Еженедельно

```bash
# Проверить свободное место
df -h /app/data

# Очистить старые записи (через веб-UI)
```

## Обновление

```bash
git pull
cd app && make build && make stop && make start
```

## Деплой на удалённый Orin

```bash
# 1. Проверить deploy.local.sh
# 2. Запустить
make deploy
```

## Полная перезагрузка стека

```bash
cd app
make stop
docker system prune -f
make build && make start
```

## Бэкапы

```bash
# БД
cp app/data/db/birdlense.db app/data/db/birdlense.db.bak.$(date +%Y%m%d)

# Конфиг (автоматически)
# user_config.yaml.bak.* создаётся при изменении
```

См. [`../RUNBOOKS.md`](../RUNBOOKS.md) · [`troubleshooting.md`](troubleshooting.md).