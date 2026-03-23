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

## 3. Конфиг клиента (пример: Cursor)

Создайте `.cursor/mcp.json`:

```bash
mkdir -p .cursor
```

### 3a. API хаба (инструменты + OpenAPI)

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
- `YOUR_HOST:8085` — хост и порт Hub (путь **`/mcp`** — в старых инструкциях мог быть `/sse`, см. **Настройки → MCP**)
- `YOUR_MCP_TOKEN_HERE` — тот же токен, что в разделе MCP или `MCP_TOKEN` на сервере

**Прод (HTTPS):** например **`https://birdlense.eyera.info/mcp`** — веб-интерфейс [birdlense.eyera.info](https://birdlense.eyera.info/); SSH на сервер по-прежнему **185.218.111.196:2222**. Тот же Bearer-токен; снаружи nginx отдаёт TLS и проксирует на Hub.

**Важно:** `.cursor/` в `.gitignore` — токен не коммитится.

### 3b. Документация репозитория (GitMCP, только чтение)

Чтобы агент читал **Markdown из GitHub** (`docs/`, `README` и т.д.) без запущенного Hub, добавьте [GitMCP](https://gitmcp.io):

```json
{
  "mcpServers": {
    "BirdLense-Hub Docs": {
      "url": "https://gitmcp.io/Gfermoto/BirdLense-Hub"
    }
  }
}
```

Блоки **3a** и **3b** можно объединить в одном объекте `mcpServers`. GitMCP **не** вызывает ваш деплой — только содержимое репозитория для справки по докам.

**Токен из Настроек:** если MCP включён и токен задан в разделе «8. MCP», MCP-сервер передаёт его при вызовах API. Инструменты Get_app_settings, Update_app_settings и др. работают без ввода пароля настроек.

## 4. Перезапуск клиента

После изменения `mcp.json` перезапустите редактор или инструмент, использующий MCP.

## Проверка

В MCP-панели редактора должны быть активны настроенные серверы: **birdlense** (хаб) и при необходимости **BirdLense-Hub Docs** (GitMCP).

---

См. также: [INSTALL](./INSTALL.ru.md), [API](./API.md), [CONFIGURATION](./CONFIGURATION.ru.md).
