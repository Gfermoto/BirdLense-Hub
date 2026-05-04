# Настройка MCP BirdLense Hub

[English](./MCP_SETUP.md)

---

**Model Context Protocol (MCP)** — способ подключить **авторизованные MCP-клиенты** (автоматизация, расширения IDE, мониторинг, собственные интеграции) к инструментам BirdLense Hub поверх вашего OpenAPI, с токеном и вашим контролем.

## 1. MCP_TOKEN в .env на сервере

**Вариант А — через деплой (рекомендуется):**

В `scripts/deploy.local.sh` добавьте:

```bash
export MCP_TOKEN="your-secret-token-at-least-16-chars"
```

При `make deploy` токен попадает в `app/.env` на сервере (`scripts/deploy.sh`).

**Вариант Б — вручную на сервере:**

```bash
ssh YOUR_SSH_HOST "echo 'MCP_TOKEN=your-token' >> YOUR_REMOTE_DIR/app/.env"
# затем перезапуск: make stop && make start
```

## 2. Включить MCP в настройках

1. Откройте BirdLense Hub → Настройки
2. Раздел **8. MCP** → включите «Включить MCP-сервер»
3. Сохраните и перезапустите контейнер

## 3. Конфигурация клиента

Добавьте фрагмент в **приложение MCP-хоста** (путь к файлу конфигурации зависит от продукта). **Не коммить** токены.

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

**Публичный прод (HTTPS, другая площадка):** например **`https://hub.example.com/mcp`**; SSH, например **`root@203.0.113.10:2222`** (адрес из [TEST-NET-3](https://datatracker.ietf.org/doc/html/rfc5737) — подставьте свой хост). Тот же Bearer-токен; nginx отдаёт TLS и проксирует на Hub.

**Важно:** файл с секретами держите вне git (или в игнорируемом пути).

### 3b. Документация репозитория (GitMCP, только чтение)

По желанию: читать **Markdown из GitHub** (`docs/`, `README` и т.д.) без запущенного Hub через [GitMCP](https://gitmcp.io):

```json
{
  "mcpServers": {
    "BirdLense-Hub Docs": {
      "url": "https://gitmcp.io/Gfermoto/BirdLense-Hub"
    }
  }
}
```

Блоки **3a** и **3b** можно объединить в одном объекте `mcpServers`. GitMCP **не** вызывает ваш деплой — только зеркалирует документацию репозитория.

**Токен из Настроек:** если MCP включён и токен задан в разделе «8. MCP», MCP-сервер передаёт его при вызовах API. Инструменты Get_app_settings, Update_app_settings и др. работают без ввода пароля настроек.

## Ошибка «Connect Timeout» / `SSE error: fetch failed`

Сообщение вроде `Connect Timeout Error (hub.example.com:443, timeout: 10000ms)` означает, что **MCP-клиент не установил TCP/TLS до сервера** за отведённое время. Обычно это **сеть между вашим ПК и сервером**, а не неверный токен (до проверки Bearer запрос часто не доходит).

**Проверки на той же машине и в той же сети, где работает MCP-клиент:**

```bash
curl -m 15 -sS -o /dev/null -w '%{http_code}\n' https://hub.example.com/api/ui/health
curl -m 15 -sS -H "Authorization: Bearer ВАШ_MCP_TOKEN" -o /dev/null -w '%{http_code}\n' https://hub.example.com/mcp
```

- **curl тоже таймаут** — блокировка или плохой маршрут до HTTPS на сервере (провайдер, фаервол, офисная сеть). Попробуйте другую сеть, VPN или точку доступа.
- **curl быстро (200/401), клиент MCP — таймаут** — иногда мешают **системный прокси**, **IPv6** (битая AAAA) или изолированная сеть процесса клиента. Временно отключите прокси; при необходимости зафиксируйте IPv4 в `/etc/hosts` (Linux/macOS) или `C:\Windows\System32\drivers\etc\hosts`:  
  `203.0.113.10 hub.example.com`

**Обход через SSH**, если SSH до VPS стабилен, а прямой HTTPS с ПК — нет:

```bash
ssh -p 2222 -N -L 18085:127.0.0.1:8085 root@203.0.113.10
```

В MCP укажите **`http://127.0.0.1:18085/mcp`** и тот же заголовок `Authorization: Bearer …`. Пока эта сессия SSH открыта, трафик к хабу идёт через туннель.

**LAN:** если хаб в той же сети, можно `http://<LAN-IP>:8085/mcp` и тот же Bearer.

## 4. Перезапуск клиента

После изменения конфигурации MCP перезапустите клиент или редактор.

## Проверка

В MCP-панели редактора должны быть активны настроенные серверы: **birdlense** (хаб) и при необходимости **BirdLense-Hub Docs** (GitMCP).

---

См. также: [INSTALL](./INSTALL.ru.md), [API](./API.ru.md), [CONFIGURATION](./CONFIGURATION.ru.md).
