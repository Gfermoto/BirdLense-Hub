# Тестирование BirdLense

## Unit-тесты (processor)

```bash
cd app && make test
```

Запускает `unittest` для processor (detection strategy, decision maker).

## API-тесты (web)

```bash
cd app && make test-web
```

Запускает pytest для web API в Docker (health, status, settings, feed, cameras).

Если образ не обновлён после добавления pytest: `make build-dev` или пересоберите web.

## E2E-тесты (Playwright)

E2E-тесты проверяют UI и API на работающем экземпляре приложения.

### Запуск

1. Запустите приложение (Docker или локально):
   ```bash
   cd app && make start-dev
   # или make start для prod
   ```

2. Запустите E2E:
   ```bash
   cd app && make test-e2e
   ```

3. Для тестов против другого хоста (например, 192.168.1.11:8085):
   ```bash
   cd app/e2e && BASE_URL=http://192.168.1.11:8085 npm test
   ```

### Что проверяют E2E

- **smoke.spec.ts**: загрузка главной, навигация, Settings, Live
- **api.spec.ts**: `/api/ui/health`, `/api/ui/status`, `/api/ui/settings`, `/api/ui/cameras`, `/api/ui/weather`, `/api/ui/feed/dispense`
- **settings.spec.ts**: форма настроек, секции Video/MQTT, Feed

### Только API-тесты (без браузера)

```bash
cd app/e2e && npm test -- --grep @api
```

## Статус MQTT и ESPHome

Эндпоинт `/api/ui/status` возвращает:

- `mqtt`: `ok` | `error` | `not_configured` | `not_used`
- `esphome`: `ok` | `error` | `not_configured` | `not_used`

Когда `feed.source` = `mqtt`, проверяется подключение к MQTT-брокеру.  
Когда `feed.source` = `esphome`, проверяется доступность URL кормушки.

Индикаторы отображаются в навигации (StatusIndicator).
