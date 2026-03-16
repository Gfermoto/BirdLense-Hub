# API BirdLense Hub

**Версия:** 0.1.5

Полная спецификация: [app/web/openapi.yaml](../app/web/openapi.yaml)

## Группы эндпоинтов

### UI API (`/api/ui/*`)

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
| `/unknowns` | GET | Детекции с низкой confidence для ручной проверки (params: start_time, end_time, limit) |
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
| `/metrics` | GET | Метрики в формате Prometheus: `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total` |

См. [CONFIGURATION.md](./CONFIGURATION.md) — раздел Prometheus / Grafana.

### System API (`/api/ui/system/*`)

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/system/metrics` | GET | CPU, память, диск |
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

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [ARCHITECTURE.md](./ARCHITECTURE.md).
