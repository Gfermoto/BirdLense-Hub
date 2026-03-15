# Отчёт о тщательной проверке BirdLense Hub

**Дата:** 14 марта 2026  
**Версия:** 0.1.5  
**Цель:** Сервер 192.168.1.11 (рабочая установка после деплоя)

## Методы проверки

| Метод | Использовано | Результат |
|-------|---------------|-----------|
| **curl/API** | Health, status, cameras на 192.168.1.11:8085 | ✅ |
| **Path traversal** | `curl --path-as-is` на сервере | ✅ 403 |
| **Web unit тесты** | pytest в Docker | ✅ 36 passed |
| **Processor unit тесты** | unittest в Docker | ✅ 8 passed |
| **E2E тесты** | Playwright против 192.168.1.11 (E2E_SETTINGS_PASSWORD) | ✅ 14/14 |
| **EU-модель** | verify-eu-model.sh (491 класс, best.pt) | ✅ |
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
web/tests:     36 passed
processor/tests: 8 passed
```

---

## 4. E2E тесты (Playwright против 192.168.1.11)

**Команда:** `BASE_URL=http://192.168.1.11:8085 E2E_SETTINGS_PASSWORD=xxx npm test`

**Результат:** 14 passed (полный прогон с паролем)

**Без пароля:** 9 passed, 5 skipped (Settings form tests, GET /api/ui/settings).

---

## 5. Деплой на 192.168.1.11

- **SSH:** Доступен
- **Контейнер:** birdlense запущен
- **UI:** http://192.168.1.11:8085
- **deploy.sh:** rsync (автоустановка на сервере), повторы при сбое (SYNC_RETRIES=3, BUILD_RETRIES=2), SSH keepalive

---

## 6. Полный тест установки

```bash
# 1. API + path traversal + E2E (с паролем для Settings)
BASE_URL=http://192.168.1.11:8085 E2E_SETTINGS_PASSWORD=xxx ./scripts/verify-release.sh

# 2. EU-модель на сервере
./scripts/verify-eu-model.sh

# 3. Unit тесты (Docker)
cd app && make test && make test-web
```

## 7. Итог

| Компонент | Статус |
|-----------|--------|
| API (сервер) | ✅ |
| Path traversal (сервер) | ✅ 403 |
| Web тесты | ✅ 36 passed |
| Processor тесты | ✅ 8 passed |
| E2E (против сервера) | ✅ 14/14 |
| EU-модель | ✅ 491 класс |
| Деплой | ✅ |
