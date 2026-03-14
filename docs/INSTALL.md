# Установка BirdLense Hub

## Требования

| Компонент | Описание |
|-----------|----------|
| **Docker** | x86/amd64, Compose v2 |
| **Go2RTC** | Видеопотоки с IP-камер. Standalone или в составе Frigate |
| **MQTT** (опционально) | Frigate events, BirdNET sightings |

## Вариант 1: Готовый образ (рекомендуется)

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```

Образ: `ghcr.io/gfermoto/birdlense-hub:latest`

UI: http://localhost:8085

## Вариант 2: Сборка из исходников

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make build && make start
```

## Первый запуск

1. **Секреты** — `make setup` создаёт `app/.env` с `PROCESSOR_SECRET` и `FLASK_SECRET_KEY` (вызывается автоматически при `make start` или `make pull`).

2. **Конфиг** — `app/app_config/user_config.yaml`. Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`.

3. **Go2RTC** — в Настройках → Видео укажите URL (`http://IP:1984`).

4. **Камеры** — в Настройках → Камеры добавьте stream names из Go2RTC.

## Деплой на сервер

```bash
cd BirdLense-Hub
make deploy
```

Требуется:
- SSH-доступ к серверу
- Docker на сервере

Локальные настройки: скопируйте `scripts/deploy.local.sh.example` в `scripts/deploy.local.sh` и задайте `DEPLOY_HOST`, `DEPLOY_URL`, `PROCESSOR_SECRET`.

Подробнее: [DEPLOYMENT.md](./DEPLOYMENT.md).

## Проверка

- **Health:** `curl http://localhost:8085/api/ui/health`
- **Камеры:** Настройки → Камеры (должны отображаться потоки)
- **Live:** страница Live — видеопоток с оверлеем детекций

## Данные

| Путь | Содержимое |
|------|------------|
| `app/data/recordings/` | Видеозаписи (YYYY/MM/DD/HHMMSS/video.mp4) |
| `app/data/db/birdlense.db` | SQLite |
| `app/app_config/user_config.yaml` | Пользовательский конфиг |

Записи не видны? System → «Сканировать и импортировать».

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [SCENARIOS.md](./SCENARIOS.md), [DEPLOYMENT.md](./DEPLOYMENT.md), [SECURITY.md](./SECURITY.md).
