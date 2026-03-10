# Конфигурация BirdLense Hub

Конфиг: `app/app_config/user_config.yaml`

Значения по умолчанию в `default_config.yaml`. Пользовательский конфиг переопределяет их (merge).

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `DATA_DIR` | Каталог данных (/app/data в Docker) |
| `FLASK_SECRET_KEY` | Ключ сессии Flask (защита настроек) |
| `PROCESSOR_SECRET` | Защита API processor (X-Processor-Token) |
| `MCP_TOKEN` | Токен MCP (переопределяет mcp.token) |
| `BIRDLENSE_PORT` | Порт nginx (по умолчанию 8085) |
| `CORS_ORIGINS` | Доп. origins для CORS (через запятую) |
| `OPENWEATHER_API_KEY` | Ключ OpenWeather |
| `MQTT_BROKER`, `MQTT_PASSWORD` | MQTT (если не в конфиге) |
| `HA_TOKEN` | Токен Home Assistant |
| `GO2RTC_URL` | URL Go2RTC (если не в конфиге) |

См. `app/.env.example`. Секреты генерируются при `make setup` (вызывается из `make start`/`make pull`).

---

## General

| Ключ | Описание |
|------|----------|
| `enable_notifications` | Включить уведомления (глобально) |
| `settings_password` | Пароль для доступа к настройкам. Пусто — без пароля |
| `notification_excluded_species` | Виды, исключённые из уведомлений |

---

## Processor

| Ключ | Описание |
|------|----------|
| `tracker` | Конфиг трекера (bytetrack.yaml) |
| `max_record_seconds` | Макс. запись в секундах |
| `max_inactive_seconds` | Макс. пауза без детекций |
| `min_track_duration` | Мин. длительность трека (сек) |
| `spectrogram_px_per_sec` | Пикселей на секунду в спектрограмме |
| `regional_species` | Локальные виды для BirdNET (пусто — YOLO все классы) |
| `included_bird_families` | Список семейств для фильтра (Perching Birds, Squirrel и др.) |
| `save_images` | Сохранять кадры детекций |
| `detection_strategy` | `single_stage` или `two_stage` |
| `models.single_stage` | Путь к single-stage модели (NCNN) |
| `models.binary` | Путь к бинарному детектору (.pt) |
| `models.classifier` | Путь к классификатору (.pt) |

---

## Video

| Ключ | Описание |
|------|----------|
| `source` | `go2rtc` \| `pi_camera` \| `file` |
| `go2rtc_url` | URL Go2RTC (http://IP:1984) |
| `cameras` | Список: `{id, stream_name, name}` |
| `pre_record_seconds` | Предзапись перед триггером |
| `auto_reconnect` | Автопереподключение к потоку |
| `video_width`, `video_height` | Разрешение (для pi_camera/file) |

## Camera (Pi Camera, legacy)

| Ключ | Описание |
|------|----------|
| `video_width`, `video_height` | Разрешение |
| `hdr_mode` | HDR |
| `focus_mode` | Режим фокуса (manual/auto) |
| `lens_position` | Позиция линзы (manual) |

---

## Motion

| Ключ | Описание |
|------|----------|
| `source` | `opencv` \| `frigate` \| `mqtt` \| `esphome` |
| `frigate_camera_filter` | Камеры Frigate (из cameras) или пусто — все |
| `frigate_label_filter` | Метки Frigate для фильтра (bird, Bird) |
| `mqtt_topic` | Топик MQTT binary sensor (Tasmota PIR) |
| `esphome_url` | URL ESPHome |
| `esphome_sensor_id` | ID binary_sensor в ESPHome |

---

## MQTT

| Ключ | Описание |
|------|----------|
| `broker` | Адрес брокера |
| `port` | Порт (1883) |
| `frigate_topic` | Топик событий Frigate |
| `birdnet_topic` | Топик BirdNET |
| `publish_topic` | Топик публикации детекций BirdLense Hub |

---

## Feed

| Ключ | Описание |
|------|----------|
| `source` | `mqtt` \| `esphome` |
| `duration_seconds` | Длительность включения реле |
| `mqtt_topic` | Топик MQTT реле (Tasmota) |
| `esphome_url` | URL ESPHome |
| `esphome_switch_id` | ID switch/button |
| `esphome_type` | `switch` \| `button` |

---

## Weather

| Ключ | Описание |
|------|----------|
| `source` | `openweather` \| `homeassistant` |
| `ha_url` | URL Home Assistant |
| `ha_entity_id` | Entity погоды (weather.home) |

---

## Detection (слияние YOLO + Frigate + BirdNET)

| Ключ | Описание |
|------|----------|
| `merge_window_seconds` | Окно слияния детекций по времени |
| `dedup_window_seconds` | Окно дедупликации |
| `species_mapping` | Маппинг названий видов |

## Retention

| Ключ | Описание |
|------|----------|
| `days` | Удалять записи старше N дней |
| `max_gb` | Макс. размер в GB (по достижении — удалять старые, опционально) |

---

## Notifications (ntfy)

| Ключ | Описание |
|------|----------|
| `enabled` | Включить уведомления |
| `excluded_species` | Виды, исключённые из уведомлений |
| `rate_limit_per_minute` | Лимит уведомлений в минуту |

## MCP

| Ключ | Описание |
|------|----------|
| `enabled` | Включить MCP-сервер |
| `token` | Токен доступа (или MCP_TOKEN в env) |

---

## Secrets

Координаты и ключи. Рекомендуется хранить в env: `OPENWEATHER_API_KEY`, `secrets.latitude`, `secrets.longitude`.

---

См. также: [ARCHITECTURE.md](./ARCHITECTURE.md), [DEPLOYMENT.md](./DEPLOYMENT.md).
