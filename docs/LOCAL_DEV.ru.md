# Локальная сборка и тестирование BirdLense

[English](./LOCAL_DEV.md)

---

Полный цикл: сборка контейнера и запуск локально без доступа к серверу.

## Требования

- **Docker** и **Docker Compose**
- **Node.js 22** (LTS — как в CI и в UI stage `Dockerfile`)
- **npm** (для UI; в репо есть `app/ui/.nvmrc` и Volta в `package.json`)

Проверка:
```bash
docker --version && docker compose version
node --version && npm --version
```

## Быстрый старт

```bash
cd app
make local
```

Откроется UI: http://localhost:8085

## Что делает `make local`

1. **setup** — создаёт `app/.env` с PROCESSOR_SECRET и FLASK_SECRET_KEY (если нет)
2. **local-build** — собирает UI, затем Docker-образ
3. **start** — запускает контейнер

Без камер и Go2RTC процессор переходит в режим ожидания — веб-интерфейс и API работают.

## Ручной запуск

```bash
cd app

# 1. Секреты (один раз)
make setup

# 2. Сборка UI (обязательно до docker build — иначе npm в контейнере)
cd ui && npm ci && npm run build && cd ..

# 3. Сборка образа
docker compose build

# 4. Запуск
docker compose up -d

# 5. Логи
docker compose logs -f --tail=100
```

## Тестирование

### API-тесты (в контейнере)

```bash
cd app
make test-web
```

Или только часть:
```bash
docker compose run --rm -v $(pwd):/app birdlense python -m pytest web/tests/test_api.py -v -k "unknowns or overview"
```

### E2E (Playwright)

```bash
cd app
# Сначала запустить контейнер
make start
# Затем E2E
make test-e2e
# С паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=http://localhost:8085 make test-e2e
```

### Processor-тесты

```bash
cd app
make test
```

## Переопределение порта

Если 8085 занят, создайте `app/docker-compose.override.yml`:

```yaml
services:
  birdlense:
    ports:
      - "8086:8080"
```

Или: `BIRDLENSE_PORT=8086 make start`

## Остановка

```bash
cd app
make stop
```

## Данные

- `app/data/recordings/` — видео (пусто при первом запуске)
- `app/data/db/birdlense.db` — SQLite (создаётся автоматически)
- `app/app_config/user_config.yaml` — настройки (опционально)

Для импорта записей: System → «Сканировать и импортировать» (если есть видео в data/recordings/).

## Ограничения локального режима

- **Нет камер** — процессор ждёт настройки Go2RTC. UI и API работают.
- **Нет MQTT** — уведомления и Frigate/BirdNET не работают.
- **Порт 8085** — по умолчанию. Переопределить: `BIRDLENSE_PORT=8080 make start`

## Автодокументация

```bash
make docs          # Python (pdoc) + UI (TypeDoc)
make docs-python   # Только Python → docs/api/
make docs-ui       # Только UI → docs/ui/
make docs-check    # interrogate — проверка docstrings (порог 80%)
```

OpenAPI: `app/web/openapi.yaml`. Стиль: краткий docstring на русском, без Args/Returns для простых функций.

---

## Устранение неполадок

### Docker build падает на npm

Соберите UI до сборки образа:
```bash
cd app/ui && npm run build && cd ..
docker compose build
```

### Контейнер не стартует

```bash
docker compose logs birdlense
```

Проверьте, что порт свободен: `ss -tlnp | grep 8085`

### Тесты зависают

Тесты используют `:memory:` SQLite. Если зависают — проверьте `docker compose ps`, контейнер должен быть запущен для `make test-web`.
