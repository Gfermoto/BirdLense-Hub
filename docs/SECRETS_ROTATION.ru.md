# Секреты в проде — runbook по ротации

[English](./SECRETS_ROTATION.md)

Операционное руководство для self-hosted BirdLense Hub: где лежат секреты, как безопасно ротировать, проверить и откатиться. Дополняет [SECURITY.ru.md](./SECURITY.ru.md) (риски) и [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) (ключи).

---

## Где хранятся секреты

| Место | Назначение | Заметки |
|-------|------------|---------|
| **`app/.env` на сервере** | Переменные окружения контейнера (`env_file` в Docker Compose) | При деплое **не** перезаписывается rsync (исключён). Скрипт деплоя **дописывает** в `app/.env` значения `MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET` из локального **`scripts/deploy.local.sh`**, если они заданы — см. [INSTALL.ru.md](./INSTALL.ru.md). |
| **`app/app_config/user_config.yaml`** | Сохранение настроек из UI | Файл на диске в открытом виде. В проде предпочтительнее env ([SECURITY.ru.md](./SECURITY.ru.md) §2). |
| **`scripts/deploy.local.sh`** (не в git) | Значения, которые при `make deploy` попадают в серверный `app/.env` | Держите здесь эталон для ключей, которыми управляет деплой, чтобы следующий деплой не подменил секрет неожиданно. |

---

## Перечень (runtime)

### Обязательно в production (`BIRDLENSE_ENV=production`)

| Секрет / переменная | Роль | Эффект ротации |
|---------------------|------|----------------|
| **`FLASK_SECRET_KEY`** | Подпись cookie сессии Flask | **Сбрасываются все сессии** — повторный вход в Настройки. |
| **`PROCESSOR_SECRET`** | Заголовок `X-Processor-Token` для processor → web | При рассинхроне: **403** в логах процессора; см. статус. Одно значение в `.env` (один контейнер). |

### Часто используются

| Секрет / переменная | Роль | Эффект ротации |
|---------------------|------|----------------|
| **`MCP_TOKEN`** | Доступ к `/mcp` при включённом MCP | Старые клиенты теряют доступ. |
| **`MQTT_PASSWORD`** | Авторизация на MQTT | При необходимости обновить ACL на брокере; перезапуск контейнера. |
| **`HA_TOKEN`** | Long-lived token Home Assistant | Погода/кормушки до обновления не работают. |
| **`OPENWEATHER_API_KEY`** | Виджет погоды | Ошибки виджета до замены ключа. |
| **`GO2RTC_URL`** | Не секрет; часто меняется вместе с сетью | Неверный URL — нет стрима. |

### В настройках / YAML (предпочитать env)

| Путь в конфиге | Роль |
|----------------|------|
| `general.settings_password` | Доступ к настройкам |
| `general.telegram_bot_token` | Telegram |
| `mqtt.password` | Если не используете `MQTT_PASSWORD` в env |
| `secrets.*` | Ключи API (дублирование с env — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md)) |
| `weather.ha_token` | Если не `HA_TOKEN` в env |
| `mcp.token` | Если не `MCP_TOKEN` в env |
| `web_push.vapid_private_key` | Web Push |

Примеры env: `XENO_CANTO_API_KEY` — см. `app/.env.example`.

---

## Стандартная процедура

1. **Подготовка**
   - Для `FLASK_SECRET_KEY` выберите окно с минимумом активных сессий.
   - Скопируйте **`app/.env`** и при необходимости **`user_config.yaml`** в **приватный** бэкап (шифрование; не в репозиторий).

2. **Применение**
   - Правка серверного `app/.env` или UI для полей из YAML.
   - Если секрет входит в набор, который мержит деплой: обновите **`scripts/deploy.local.sh`** на машине, с которой делаете `make deploy`, **до** следующего деплоя.
   - Перезапуск: на сервере `cd app && make stop && make start` или полный `make deploy` с dev-машины.

3. **Проверка**
   - `curl -sf http://127.0.0.1:8085/api/ui/health` (или публичный URL) → 200.
   - UI: Настройки (повторная авторизация после смены `FLASK_SECRET_KEY` или пароля).
   - Логи процессора: нет повторяющихся **403** / `PROCESSOR_SECRET`.
   - Опционально: `GET /api/ui/status` — `processor_secret_configured: true`, если задан секрет.

4. **Откат**
   - Восстановить `.env` (и YAML) из бэкапа.
   - Снова перезапустить контейнер.
   - Повторить проверки из п.3.

---

## Заметки по отдельным секретам

### `PROCESSOR_SECRET`

- Генерация: `openssl rand -hex 16`.
- Web и processor в одном контейнере читают **один** `.env` — одна ротация, один перезапуск.

### `FLASK_SECRET_KEY`

- Генерация: `openssl rand -hex 32` (или аналог по силе).
- Все сессии настроек сбрасываются.

### `MCP_TOKEN`

- Длина — по требованиям приложения; используйте длинную случайную строку.
- См. приоритет env vs YAML в [MCP_SETUP.ru.md](./MCP_SETUP.ru.md).

### Telegram / MQTT / HA / API keys

- Предпочтительно env на сервере и очистка дублей в YAML.
- После правок YAML — перезапуск контейнера.

---

## Деплой и `.env`

`scripts/deploy.sh` при `make deploy` пересобирает на сервере строки `MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET` из **локального** окружения. Экспорты держите в **`deploy.local.sh`**, чтобы ротация пережила следующий деплой.

Если **`PROCESSOR_SECRET` не задан** локально, деплой **генерирует новый** случайный и выводит подсказку — риск случайной ротации; в проде задавайте явно в `deploy.local.sh`.

---

## Экстренная ротация — шаблон заметки

```text
Дата / часовой пояс:
Кто выполнил:
Причина (утечка / политика / запрос вендора):

Что меняли:
  - [ ] FLASK_SECRET_KEY
  - [ ] PROCESSOR_SECRET
  - [ ] MCP_TOKEN
  - [ ] MQTT_*
  - [ ] HA_TOKEN
  - [ ] API-ключи (перечень):
  - [ ] пароль настроек / Telegram / прочее:

Где бэкап (шифрованно):
deploy.local.sh обновлён (Д/Н):
Перезапуск контейнера:
Health OK (Д/Н):
Логи процессора чистые (Д/Н):
Откат выполнен (Д/Н):
```

---

## См. также

[SECURITY.ru.md](./SECURITY.ru.md) · [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) · [ACCESS_CONTROL.ru.md](./ACCESS_CONTROL.ru.md) · [TESTING.ru.md](./TESTING.ru.md) · [INSTALL.ru.md](./INSTALL.ru.md) · [RECOVERY_CONFIG.ru.md](./RECOVERY_CONFIG.ru.md)

Issue: [#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)
