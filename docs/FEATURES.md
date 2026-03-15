# Возможности BirdLense Hub (для разработчиков)

Полный список фич по версиям. См. [CHANGELOG.md](../CHANGELOG.md) для деталей.

---

## Ядро (всегда)

| Фича | Описание |
|------|----------|
| **Live video** | Go2RTC, MJPEG overlay с детекциями |
| **YOLO + ByteTrack** | Двухэтапная стратегия: binary detector + species classifier |
| **EU-модель** | ~491 вид (birds-525 + iNaturalist). US (NABirds) — резерв |
| **Триггеры** | OpenCV, Frigate, MQTT, ESPHome |
| **BirdNET** | Слияние аудио-детекций через MQTT |
| **Frigate** | Bird Classification sub_label в слиянии |
| **Timeline** | Визиты по дате, воспроизведение видео, спектрограммы |
| **Overview** | Статистика, графики активности |
| **Species** | Дерево видов, сводка по виду |
| **Погода** | OpenWeather, Home Assistant |
| **Telegram** | Уведомления при детекции |
| **Кормушка** | Реле (MQTT/ESPHome) при детекции |
| **MCP** | Model Context Protocol для внешних инструментов |

---

## Экспорт и аналитика

| Фича | API / UI | Версия |
|------|----------|--------|
| **CSV/JSON** | `GET /api/ui/timeline/export?format=csv\|json` | 0.1.2 |
| **eBird** | `GET /api/ui/timeline/export?format=ebird` | 0.1.4 |
| **PDF-отчёт** | `GET /api/ui/report/pdf?month=YYYY-MM` | 0.1.3 |
| **Prometheus** | `GET /metrics` | 0.1.3 |
| **iNaturalist** | `GET /api/ui/detections/:id/crop` | 0.1.4 |

---

## UI

| Фича | Описание |
|------|----------|
| **Timeline: дата + время суток** | DatePicker, фильтр: Утро, День, Вечер, Ночь (22–06) |
| **Неизвестные** | `/unknowns` — детекции с confidence < порога, ручная коррекция |
| **Playback speed** | 0.5x, 2x в видеоплеере |
| **Виджет «Последняя птица»** | На Overview |
| **PWA** | Install prompt, offline cache |
| **Источник детекции** | YOLO / Frigate / BirdNET в карточках |
| **Xeno-canto** | Песни птиц на странице вида |
| **Confidence по виду** | `processor.species_confidence_overrides` |

---

## Интеграции

| Фича | Конфиг | Описание |
|------|--------|----------|
| **Webhook** | `webhook.url` | POST при детекции (IFTTT, Zapier) |
| **eBird** | `ebird.country`, `ebird.state`, `ebird.location_name` | Экспорт чеклиста |
| **Home Assistant** | `mqtt.ha_discovery`, `mqtt.broker` | MQTT Autodiscovery — Last Species, Bird at Feeder и др. |
| **Grafana** | Prometheus scrape | Метрики для дашбордов |

---

## Конфигурация (ключевые ключи)

| Секция | Ключи |
|--------|-------|
| `processor` | `species_confidence_overrides`, `min_confidence_to_process` |
| `ui` | `unknown_confidence_threshold` |
| `webhook` | `url` |
| `ebird` | `country`, `state`, `location_name` |
| `secrets` | `xeno_canto_api_key` |

---

## API (основные эндпоинты)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/ui/health` | Health check |
| GET | `/api/ui/timeline` | Визиты за период |
| GET | `/api/ui/timeline/export` | CSV, JSON, eBird |
| GET | `/api/ui/unknowns` | Низкая confidence |
| PATCH | `/api/ui/detections/:id` | Исправить вид |
| GET | `/api/ui/detections/:id/crop` | Кадр для iNaturalist |
| GET | `/api/ui/report/pdf` | PDF-отчёт |
| GET | `/api/ui/species/:id/xeno-canto` | Записи Xeno-canto |
| GET | `/metrics` | Prometheus |

Полная спецификация: [openapi.yaml](../app/web/openapi.yaml).

---

См. также: [API.md](./API.md), [CONFIGURATION.md](./CONFIGURATION.md), [ROADMAP.md](./ROADMAP.md).
