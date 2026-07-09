# Быстрый старт

## Минимальный запуск

```bash
cd app
cp .env.example .env
# отредактировать FLASK_SECRET_KEY и PROCESSOR_SECRET
make build && make start
```

## Проверка

```bash
# Health check
curl http://localhost:8085/api/health
# или
make verify
```

## Веб-интерфейс

Откройте `http://<orin-ip>:8085/` в браузере.

## Первичная настройка

1. System → «Сканировать и импортировать» — найти записи
2. Настроить источники (RTSP) в конфиге
3. Проверить, что GPU используется: `docker exec birdlense-hub nvidia-smi`

## Makefile команды

| Команда | Описание |
|---------|----------|
| `make build` | Собрать Docker образ |
| `make start` | Запустить контейнеры |
| `make stop` | Остановить контейнеры |
| `make logs` | Логи контейнера |
| `make verify` | Health check |
| `make deploy` | Деплой на удалённый хост |

См. [`install.md`](install.md) · [`overview.md`](overview.md).