# API BirdLense Hub

[English](./API.md)

---

**Версия:** 0.2.1

Полная спецификация: [OpenAPI YAML](./project/openapi.md)

## Группы эндпоинтов

### UI API (`/api/ui/*`)

Пути в таблице — суффикс после `/api/ui` (например `/health` → `GET /api/ui/health`).

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка доступности |
| `/status` | GET | Статус компонентов (web, processor, mqtt, esphome, yolo). Значения: ok, error, not_configured, not_used, unknown |
| `/cameras` | GET | Список камер |
| `/weather` | GET | Погода |
| `/timeline` | GET | Визиты по периоду (params: start_time, end_time) |
| `/timeline/export` | GET | Экспорт визитов в CSV, JSON или eBird (params: start_time, end_time, format=csv\|json\|ebird) |
| `/videos/:id` | GET | Детали видео |
| `/overview` | GET | Данные для Overview |
| `/species` | GET | Список видов |
| `/birdfood` | GET/POST | Список и добавление корма |
| `/birdfood/:id/toggle` | PATCH | Переключить активность корма |
| `/bird_families` | GET | Список семейств птиц |
| `/feed/dispense` | POST | Выдать корм |
| `/settings` | GET/PATCH | Настройки |
| `/settings/requires-password` | GET | Проверка, требуется ли пароль |
| `/settings/verify-password` | POST | Разблокировка настроек |
| `/settings/check-access` | GET | Проверка разблокировки (200/403) |
| `/unknowns` | GET | Детекции с низкой confidence (params: start_time, end_time, limit) |
| `/region-comparison` | GET | Сравнение видов с топом eBird региона (требует secrets.ebird_api_key) |
| `/detections/:id` | PATCH | Исправить вид детекции (body: `{species_id}`). Требует пароль настроек |
| `/detections/:id/crop` | GET | Кадр из видео для экспорта в iNaturalist. Возвращает JPEG |
| `/dataset/export` | GET | Экспорт датасета (ZIP: train/val + dataset_info.json). Требует пароль |
| `/push/vapid-public` | GET | Публичный ключ VAPID для Web Push подписки |
| `/push/subscribe` | POST | Регистрация Web Push подписки (body: `{subscription}`) |
| `/report/pdf` | GET | Месячный PDF-отчёт (params: month=YYYY-MM или start_time, end_time) |
| `/migration-calendar` | GET | Агрегация визитов по виду и месяцу (species, month_labels, monthly_counts) |
| `/species/:id/xeno-canto` | GET | Записи птичьих песен из Xeno-canto для вида |
| `/species/:id/summary` | GET | Сводка по виду |
| `/restart-processor` | POST | Перезапуск processor |

### Prometheus

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/metrics` | GET | Prometheus: CPU, память, диск, GPU, detections, species, videos |
| `/api/metrics` | GET | То же (для Grafana) |

См. [CONFIGURATION](./CONFIGURATION.ru.md) — раздел Prometheus / Grafana.

### System API (`/api/ui/system/*`)

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/system/metrics` | GET | CPU, память, диск, GPU, encoding |
| `/system/activity` | GET | Активность по дням |
| `/storage/stats` | GET | Статистика записей |
| `/storage/purge` | POST | Удаление записей по дате |
| `/system/retention` | POST | Запуск политики retention |
| `/system/regenerate-spectrograms` | POST | Регенерация спектрограмм |
| `/system/regenerate-spectrograms/status` | GET | Статус регенерации спектрограмм |
| `/system/regenerate-tracks` | POST | Регенерация треков |
| `/system/regenerate-tracks/status` | GET | Статус регенерации треков |
| `/system/recordings/scan` | POST | Сканирование и импорт записей |
| `/system/logs` | GET | Логи процессора (последние N строк, ?lines=100) |

### Processor API (`/api/processor/*`)

Внутренний API для processor. Защищён `X-Processor-Token` при заданном `PROCESSOR_SECRET`.

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/videos` | POST | Создание записи с детекциями |
| `/species/active` | PUT | Установка активных видов |
| `/notify/detections` | POST | Уведомление о детекции |
| `/notify/motion` | POST | Уведомление о движении |
| `/activity_log` | POST | Heartbeat, статус processor |

## Аутентификация

- **По умолчанию** — нет. Доступ ко всем эндпоинтам открыт.
- **Настройки** — опционально `settings_password` в конфиге. При заданном пароле `/settings`, `/storage/purge`, `/restart-processor` и др. требуют разблокировки через `verify-password`.
- **MCP** — опционально `MCP_TOKEN` в env. Заголовок `Authorization: Bearer <token>`.
- **Processor API** — опционально `PROCESSOR_SECRET` в env. Заголовок `X-Processor-Token`.

---

См. также: [CONFIGURATION](./CONFIGURATION.ru.md), [ARCHITECTURE](./ARCHITECTURE.ru.md), [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md), [GLOSSARY](./GLOSSARY.ru.md).
