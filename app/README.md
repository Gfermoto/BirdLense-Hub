# BirdLense

Один контейнер. Подключается к Go2RTC (отдельно или в Frigate), MQTT (BirdNET, Frigate).

## Запуск

```bash
cd app
make build && make start
```

UI: http://localhost:8085

## Команды

| Команда | Описание |
|---------|----------|
| `make build` | Сборка образа |
| `make start` | Запуск |
| `make stop` | Остановка |
| `make logs` | Логи |
| `make deploy` | Деплой на 192.168.1.11 |

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

## Деплой

```bash
cd BirdLense
make deploy
```

Синхронизирует код на 192.168.1.11, **не трогает** data на сервере.

## Требования

- Go2RTC — укажите хост в Настройках (`http://IP:1984`)
- MQTT (опционально)
