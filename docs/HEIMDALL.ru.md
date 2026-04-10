# Плитки Heimdall для BirdLense Hub

Как добавить **BirdLense** (и соседние сервисы) в дашборд **[linuxserver/Heimdall](https://github.com/linuxserver/Heimdall)** v2. Проверка **с Hub на Heimdall** (`heimdall_url`) — в [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) (раздел про метрики и Heimdall).

[English](./HEIMDALL.md)

---

## Есть ли импорт списка плиток в Heimdall?

**Через веб-интерфейс — нет.** Запросы на импорт/экспорт ([#294](https://github.com/linuxserver/Heimdall/issues/294), [#383](https://github.com/linuxserver/Heimdall/issues/383)) не привели к готовой функции. Для **полного переноса** дашборда в сообществе обычно копируют **SQLite БД** при остановленном Heimdall (см. [#831](https://github.com/linuxserver/Heimdall/issues/831)).

Здесь описан **ручной путь**: взять URL из таблицы и добавить плитки через **Items → Add**.

---

## Плейсхолдеры

| Токен | Смысл |
|-------|--------|
| `YOUR_HUB_HOST` | Хост или IP, с которого **браузер** открывает Hub. |
| `YOUR_HUB_PORT` | Порт HTTP (по умолчанию **8085** или ваш `BIRDLENSE_PORT` / прокси). |
| `YOUR_HUB_BASE` | Удобно: `http://YOUR_HUB_HOST:YOUR_HUB_PORT` (или `https://` за reverse proxy). |

Опционально:

| Токен | Смысл |
|-------|--------|
| `YOUR_FRIGATE_URL` | UI Frigate, если есть. |
| `YOUR_BIRDNET_URL` | Как в настройках Hub **`birdnet_url`**, если задано. |

---

## Рекомендуемые плитки

В Heimdall: **Items → Add**. Обычно тип — обычная ссылка, если не подходит готовое приложение из каталога Heimdall.

| Название плитки | URL | Примечание |
|-----------------|-----|------------|
| BirdLense Hub | `YOUR_HUB_BASE/` | Основной UI. |
| BirdLense health | `YOUR_HUB_BASE/api/ui/health` | Быстрая проверка «API жив». |
| Метрики (Prometheus) | `YOUR_HUB_BASE/metrics` | Текст; удобно открыть вкладкой. |
| Метрики (JSON) | `YOUR_HUB_BASE/api/metrics/summary` | Сводка JSON. |

### Соседи (по желанию)

| Название | URL |
|----------|-----|
| Frigate | `YOUR_FRIGATE_URL/` |
| BirdNET | `YOUR_BIRDNET_URL/` |

---

## `BIRDLENSE_METRICS_TOKEN` и ссылки

Если на Hub задан **`BIRDLENSE_METRICS_TOKEN`**, для **`/metrics`**, **`/api/metrics`** и **`/api/metrics/summary`** нужен заголовок **`Authorization: Bearer`**. Плитка Heimdall **не отправляет** заголовки. Тогда для мониторинга из дашборда логичнее плитка на **`/api/ui/health`**, а метрики — в браузере/Prometheus с токеном. Подробнее — [SECURITY.ru.md](./SECURITY.ru.md).

---

## Пошагово

1. Откройте Hub в браузере, скопируйте origin → это `YOUR_HUB_BASE`.
2. Добавьте плитку **BirdLense Hub** → `YOUR_HUB_BASE/`.
3. Добавьте **BirdLense health** → `YOUR_HUB_BASE/api/ui/health`.
4. При необходимости — строки метрик из таблицы (если токен метрик не включён).
5. По желанию — Frigate и BirdNET своими URL.

Итог: **вставил URL — получил плитки**, без формата импорта, который Heimdall v2 не поддерживает в UI.

---

## Опционально: HTML закладок для **браузера**

Heimdall этот файл **не импортирует**. Для импорта закладок в **Firefox / Chrome** можно отредактировать и использовать:

- [examples/heimdall/birdlense-bookmarks.html](./examples/heimdall/birdlense-bookmarks.html)

Замените в файле `YOUR_HUB_HOST` и `YOUR_HUB_PORT` (`8085` по умолчанию).

---

## См. также

- [CONFIGURATION.ru.md](./CONFIGURATION.ru.md) — `heimdall_url`, `birdnet_url`, метрики.
- [SCENARIOS.ru.md](./SCENARIOS.ru.md) — сценарии стека.
