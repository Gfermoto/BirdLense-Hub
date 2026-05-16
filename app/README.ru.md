# BirdLense Hub

[English](./README.md)

Один контейнер. Подключается к Go2RTC (отдельно или в Frigate), MQTT (BirdNET, Frigate).

**Возможности:** Timeline (дата + время суток), экспорт CSV/JSON/eBird, PDF-отчёт, «Неизвестные», iNaturalist, Xeno-canto, Prometheus. См. [docs/ru/features.ru.md](../docs/ru/features.ru.md).

## Запуск

### Локальная разработка (без сервера)

```bash
cd app
make local
```

См. [docs/ru/local-dev.ru.md](../docs/ru/local-dev.ru.md) — полная сборка, тесты, E2E.

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
| `make deploy` | Деплой на сервер (из корня репо; см. [docs/ru/install.ru.md](../docs/ru/install.ru.md)) |

## Конфигурация

- `app_config/default_config.yaml` — значения по умолчанию из образа/репозитория (базовая линия).
- `app_config/user_config.yaml` — **пользовательские настройки** (глубокий merge поверх default); основной файл для сохранения настроек из UI. При деплое на сервер не перезаписываются живые `data/` и `user_config.yaml` (см. [docs/ru/install.ru.md](../docs/ru/install.ru.md) и правила deploy в репозитории).
- **Переменные окружения** — слой рантайма для секретов и инфраструктуры: `DATA_DIR`, `MQTT_BROKER`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `GO2RTC_URL`, `PROCESSOR_SECRET`, `FLASK_SECRET_KEY`, `BIRDLENSE_*`, `MCP_TOKEN` и др. Во многих местах порядок **сначала env, потом YAML** (например брокер MQTT в bootstrap процессора и части UI).
- При загрузке выполняется проверка **типов верхнеуровневых секций** merged-конфига (известные секции должны быть mapping, не скаляр). Ошибки пишутся в лог; `BIRDLENSE_STRICT_CONFIG=1` — **падать при старте**, если валидация не прошла.

- **Go2RTC URL:** Настройки → Видео — `http://IP:1984` (хост, где доступен Go2RTC)
- Камеры: Настройки → Камеры (stream name из Go2RTC)
- Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`

## Данные

- `./data/recordings/` — видео (YYYY/MM/DD/HHMMSS/video.mp4)
- `./data/db/birdlense.db` — SQLite
- `./app_config/` — конфиг

Записи не видны? System → «Сканировать и импортировать».

## MCP

Настройки → раздел 8. Подключение: [docs/ru/mcp-setup.ru.md](../docs/ru/mcp-setup.ru.md)

## Деплой

```bash
cd BirdLense
make deploy
```

Синхронизирует код на сервер (см. scripts/deploy.local.sh.example), **не трогает** data на сервере.

## Требования

- Go2RTC — укажите хост в Настройках (`http://IP:1984`)
- MQTT (опционально)
