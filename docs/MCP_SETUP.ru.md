# Настройка MCP BirdLense Hub

[English](./MCP_SETUP.md)

---

MCP (Model Context Protocol) позволяет внешним инструментам вызывать API BirdLense Hub.

## 1. MCP_TOKEN в .env на сервере

**Вариант А — через деплой (рекомендуется):**

В `scripts/deploy.local.sh` добавьте:

```bash
export MCP_TOKEN="your-secret-token-at-least-16-chars"
```

При `make deploy` токен автоматически попадёт в `app/.env` на сервере.

**Вариант Б — вручную на сервере:**

```bash
ssh YOUR_SSH_HOST "echo 'MCP_TOKEN=your-token' >> YOUR_REMOTE_DIR/app/.env"
# затем перезапуск: make stop && make start
```

## 2. Включить MCP в настройках

1. Откройте BirdLense Hub → Настройки
2. Раздел **8. MCP** → включите «Включить MCP-сервер»
3. Сохраните и перезапустите контейнер

## 3. Добавить MCP-сервер с заголовком Authorization

Создайте `.cursor/mcp.json`:

```bash
mkdir -p .cursor
```

Содержимое `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "birdlense": {
      "url": "http://YOUR_HOST:8085/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN_HERE"
      }
    }
  }
}
```

Замените:
- `YOUR_HOST:8085` — hostname или IP и порт вашего BirdLense Hub
- `YOUR_MCP_TOKEN_HERE` — тот же токен, что в Настройках (MCP) или MCP_TOKEN на сервере

**Важно:** `.cursor/` в .gitignore — токен не попадёт в репозиторий.

**Токен из Настроек:** если MCP включён и токен задан в разделе «8. MCP», MCP-сервер передаёт его при вызовах API. Инструменты Get_app_settings, Update_app_settings и др. работают без ввода пароля настроек.

## 4. Перезапуск клиента

После изменения `mcp.json` перезапустите редактор или инструмент, использующий MCP.

## Проверка

В настройках MCP-клиента сервер `birdlense` должен быть в списке и активен.

---

См. также: [INSTALL](./INSTALL.ru.md), [API](./API.md), [CONFIGURATION](./CONFIGURATION.ru.md).
