# Тестирование BirdLense Hub

## Unit-тесты (processor)

```bash
cd app && make test
```

Запускает `unittest` для processor (detection strategy, decision maker). Требуется Python 3 и зависимости processor.

## API-тесты (web)

```bash
cd app && make test-web
```

Запускает pytest для web API в Docker (health, status, settings, feed, cameras).

Перед первым запуском: `make build`. Тесты выполняются в контейнере.

## E2E-тесты (Playwright)

E2E проверяют UI и API на работающем экземпляре.

### Запуск

1. Запустите приложение:
   ```bash
   cd app && make start
   ```

2. Запустите E2E:
   ```bash
   cd app && make test-e2e
   ```

3. Против другого хоста (например, 192.168.1.11:8085):
   ```bash
   cd app && E2E_SETTINGS_PASSWORD=xxx BASE_URL=http://192.168.1.11:8085 make test-e2e
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
