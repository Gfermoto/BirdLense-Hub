# Настройка MCP BirdLense Hub

MCP (Model Context Protocol) позволяет внешним инструментам вызывать API BirdLense Hub.

## 1. MCP_TOKEN в .env на сервере

**Вариант А — через деплой (рекомендуется):**

В `scripts/deploy.local.sh` добавьте:

```bash
export MCP_TOKEN="ваш-секретный-токен-минимум-16-символов"
```

При `make deploy` токен автоматически попадёт в `app/.env` на сервере.

**Вариант Б — вручную на сервере:**

```bash
ssh birdlense "echo 'MCP_TOKEN=ваш-токен' >> /root/BirdLense/app/.env"
# затем перезапуск: make stop && make start
```

## 2. Включить MCP в настройках

1. Откройте BirdLense Hub → Настройки
2. Раздел **8. MCP** → включите «Включить MCP-сервер»
3. Сохраните и перезапустите контейнер

## 3. Добавить MCP-сервер с заголовком Authorization

Скопируйте шаблон и заполните:

```bash
mkdir -p .cursor
cp docs/mcp.json.example .cursor/mcp.json
# Отредактируйте .cursor/mcp.json: url и Authorization
```

Или создайте `.cursor/mcp.json` вручную:

```json
{
  "mcpServers": {
    "birdlense": {
      "url": "http://192.168.1.11:8085/mcp",
      "headers": {
        "Authorization": "Bearer ваш-секретный-токен"
      }
    }
  }
}
```

Замените:
- `192.168.1.11:8085` — IP и порт вашего BirdLense Hub
- `ваш-секретный-токен` — тот же токен, что в MCP_TOKEN на сервере

**Важно:** `.cursor/` в .gitignore — токен не попадёт в репозиторий.

## 4. Перезапуск клиента

После изменения `mcp.json` перезапустите редактор или инструмент, использующий MCP.

## Проверка

В настройках MCP-клиента сервер `birdlense` должен быть в списке и активен.

---

См. также: [DEPLOYMENT.md](./DEPLOYMENT.md), [API.md](./API.md), [CONFIGURATION.md](./CONFIGURATION.md).
