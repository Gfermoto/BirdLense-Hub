# Настройка MCP BirdLense Hub

[English](./MCP_SETUP.md)

---

**Model Context Protocol (MCP)** — стандартный способ подключить **внешние ИИ-ассистенты** (LLM в IDE, отдельные MCP-клиенты и т.п.) к инструментам BirdLense Hub поверх вашего OpenAPI, с токеном и вашим контролем.

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

## 3. Конфигурация клиента (ИИ / IDE)

Добавьте фрагмент в MCP-хост: Cursor, Claude Desktop, VS Code с MCP и т.д. (путь к файлу зависит от продукта). **Не коммить** токены.

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

**LAN (пример):** **`http://192.168.1.11:8085/mcp`** — тот же хост, что и UI (`http://192.168.1.11:8085/`).

**Публичный прод (HTTPS, другая площадка):** например **`https://birdlense.eyera.info/mcp`**; SSH, например **185.218.111.196:2222**, если этот сервер ещё используется. Тот же Bearer-токен; nginx отдаёт TLS и проксирует на Hub.

**Важно:** файл с секретами держите вне git (или в игнорируемом пути).

### 3b. Документация репозитория (GitMCP, только чтение)

Чтобы ИИ-клиент читал **Markdown из GitHub** (`docs/`, `README` и т.д.) без запущенного Hub, добавьте [GitMCP](https://gitmcp.io):

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

После изменения конфигурации MCP перезапустите клиент или редактор.

## Проверка

В MCP-панели редактора должны быть активны настроенные серверы: **birdlense** (хаб) и при необходимости **BirdLense-Hub Docs** (GitMCP).

---

См. также: [INSTALL](./INSTALL.ru.md), [API](./API.md), [CONFIGURATION](./CONFIGURATION.ru.md).
