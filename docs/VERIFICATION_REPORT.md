# Отчёт о тщательной проверке BirdLense Hub

**Дата:** 14 марта 2026  
**Цель:** Сервер 192.168.1.11 (рабочая установка после деплоя)

## Методы проверки

| Метод | Использовано | Результат |
|-------|---------------|-----------|
| **curl/API** | Health, status, cameras на 192.168.1.11:8085 | ✅ |
| **Path traversal** | `curl --path-as-is` на сервере | ✅ 403 |
| **Web unit тесты** | pytest в Docker | ✅ 7/7 |
| **Processor unit тесты** | unittest в Docker | ✅ 7/7 |
| **E2E тесты** | Playwright против 192.168.1.11 | ✅ 9/14 (5 skip — нужен пароль) |
| **SSH** | 192.168.1.11 | ✅ Деплой успешен |

---

## 1. API (192.168.1.11:8085)

| Эндпоинт | Статус |
|----------|--------|
| `GET /api/ui/health` | ✅ `{"status":"ok"}` |
| `GET /api/ui/status` | ✅ processor, video, web, yolo, mqtt, esphome ok |
| `GET /api/ui/cameras` | ✅ BirdBox, Forest, Termal_forest |
| `GET /api/ui/settings/requires-password` | ✅ `{"requires":true}` |

---

## 2. Безопасность (192.168.1.11)

### Path traversal (nginx)

- **Запрос:** `curl -sI --path-as-is "http://192.168.1.11:8085/data/../.env"`
- **Результат:** `HTTP/1.1 403 Forbidden` ✅

### Маскирование секретов

- **Тест:** Добавлены `settings_password` и `telegram_bot_token` в user_config
- **GET /api/ui/settings:** Оба возвращают `***` ✅
- **PATCH с `***`:** Реальное значение не перезаписывается ✅

---

## 3. Unit тесты

```
web/tests:     7 passed
processor/tests: 7 passed
```

---

## 4. E2E тесты (Playwright против 192.168.1.11)

**Команда:** `BASE_URL=http://192.168.1.11:8085 npm test`

**Результат:** 9 passed, 5 skipped

**Успешные:** API health, status, cameras, timeline, live, species, navigation links, Settings page loads.

**Пропущены (требуется E2E_SETTINGS_PASSWORD):** Settings form tests, GET /api/ui/settings.

---

## 5. Деплой на 192.168.1.11

- **SSH:** Доступен
- **Контейнер:** birdlense запущен
- **UI:** http://192.168.1.11:8085
- **Исправление:** Добавлен SSH keepalive в deploy.sh (ServerAliveInterval) — устраняет «Broken pipe» при длительной сборке

---

## 6. Итог

| Компонент | Статус |
|-----------|--------|
| API (сервер) | ✅ |
| Path traversal (сервер) | ✅ 403 |
| Web тесты | ✅ |
| Processor тесты | ✅ |
| E2E (против сервера) | ✅ 9 pass, 5 skip |
| Деплой | ✅ |
