# BirdLense Hub

Один контейнер. Подключается к Go2RTC (отдельно или в Frigate), MQTT (BirdNET, Frigate).

**Возможности:** Timeline (дата + время суток), экспорт CSV/JSON/eBird, PDF-отчёт, «Неизвестные», iNaturalist, Xeno-canto, Prometheus. См. [docs/FEATURES.md](../docs/FEATURES.md).

## Запуск

### Вариант 1: Готовый образ (рекомендуется)

```bash
cd app
make pull
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest` ([GitHub Packages](https://github.com/Gfermoto/BirdLense-Hub/pkgs/container/birdlense-hub))

### Вариант 2: Сборка из исходников

```bash
cd app
make build && make start
```

UI: http://localhost:8085

## Команды

| Команда | Описание |
|---------|----------|
| `make setup` | Создать app/.env с PROCESSOR_SECRET и FLASK_SECRET_KEY (вызывается автоматически) |
| `make build` | Сборка образа |
| `make start` | Запуск (после build) |
| `make pull` | Скачать и запустить готовый образ |
| `make stop` | Остановка |
| `make logs` | Логи |
| `make deploy` | Деплой на сервер (см. scripts/deploy.local.sh) |

## Конфигурация

- `app_config/user_config.yaml` — основной конфиг
- **Go2RTC URL:** Настройки → Видео — `http://IP:1984` (хост, где доступен Go2RTC)
- Камеры: Настройки → Камеры (stream name из Go2RTC)
- Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`

## Данные

- `./data/recordings/` — видео (YYYY/MM/DD/HHMMSS/video.mp4)
- `./data/db/birdlense.db` — SQLite
- `./app_config/` — конфиг

Записи не видны? System → «Сканировать и импортировать».

## MCP

Настройки → раздел 8. Подключение: [docs/MCP_SETUP.md](../docs/MCP_SETUP.md)

## Деплой

```bash
cd BirdLense
make deploy
```

Синхронизирует код на сервер (см. scripts/deploy.local.sh.example), **не трогает** data на сервере.

## Требования

- Go2RTC — укажите хост в Настройках (`http://IP:1984`)
- MQTT (опционально)
