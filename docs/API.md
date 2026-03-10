# API BirdLense Hub

Полная спецификация: [app/web/openapi.yaml](../app/web/openapi.yaml)

## Группы эндпоинтов

### UI API (`/api/ui/*`)

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка доступности |
| `/status` | GET | Статус компонентов (web, processor, mqtt, esphome, yolo) |
| `/cameras` | GET | Список камер |
| `/weather` | GET | Погода |
| `/timeline` | GET | Визиты по периоду |
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
| `/species/:id/summary` | GET | Сводка по виду |
| `/restart-processor` | POST | Перезапуск processor |

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
