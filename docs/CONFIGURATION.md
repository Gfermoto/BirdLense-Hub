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
| `source` | `go2rtc` (file — только через CLI) |
| `go2rtc_url` | URL Go2RTC (http://IP:1984) |
| `cameras` | Список: `{id, stream_name, name}` |
| `pre_record_seconds` | Предзапись перед триггером |
| `auto_reconnect` | Автопереподключение к потоку |
| `video_width`, `video_height` | Разрешение |

---

## Motion

| Ключ | Описание |
|------|----------|
| `source` | `opencv` \| `frigate` \| `mqtt` \| `esphome` |
| `frigate_camera_filter` | Камеры Frigate (из cameras) или пусто — все |
| `frigate_label_filter` | Метки Frigate для фильтра (bird, Bird) |
| `frigate_label_exclude` | Метки для игнорирования (cat, dog — мышь как кошка) |
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

**Источники видов:**
- **YOLO** — видео, классификация (NABirds, в основном североамериканские)
- **Frigate** — видео, `sub_label` из [Bird Classification](https://docs.frigate.video/configuration/bird_classification/) (MobileNet INat), если включено в Frigate
- **BirdNET** — аудио, распознавание по голосу

**Европейские птицы:** изначально в модели не было. Пока используем Frigate + BirdNET. Планируем дообучить на [birds-525](https://huggingface.co/datasets/34data/birds-525-species) и [iNaturalist Europe](https://api.inaturalist.org/v1/docs/) — см. [FINETUNE_OPEN_DATASETS.md](./FINETUNE_OPEN_DATASETS.md).

## Retention

| Ключ | Описание |
|------|----------|
| `days` | Удалять записи старше N дней |
| `max_gb` | Макс. размер в GB (по достижении — удалять старые, опционально) |

---

## Notifications (Telegram)

| Ключ | Описание |
|------|----------|
| `general.enable_notifications` | Включить уведомления |
| `notifications.telegram_bot_token` | Токен бота (@BotFather → /newbot) |
| `notifications.telegram_chat_id` | ID чата или канала (например -1001234567890) |
| `notifications.base_url` | URL Hub для ссылок (кнопка «Open Live») |
| `notifications.message_thread_id` | ID топика в канале с форумом |
| `notifications.disable_notification` | Тихие сообщения (без звука) |
| `notifications.protect_content` | Запретить пересылку и сохранение |
| `notifications.link_preview_large` | true: большие превью ссылок (Bot API 9.4), ссылка добавляется в текст |
| `notifications.use_custom_emoji` | true: icon_custom_emoji_id на кнопках (требует Premium у владельца бота) |
| `notifications.custom_emoji_id_bird` | ID кастомного эмодзи для птиц (из @Stickers) |
| `notifications.custom_emoji_id_chipmunk` | ID для белок |
| `notifications.custom_emoji_id_open_live` | ID для кнопки Open Live |
| `notifications.paid_media_view_star_count` | Stars за просмотр фото (0=бесплатно, 1–25000). sendPaidMedia |
| `notifications.paid_media_forward_star_count` | При бесплатном просмотре: 0=разрешить пересылку, >0=запретить. При платном — пересылка включена. |
| `general.notification_excluded_species` | Виды, исключённые из уведомлений |
| `processor.save_images` | При true — отправлять фото детекции в Telegram |

**Telegram Bot API 9.4/9.5:** кнопки с эмодзи и стилем (primary), динамическое время `<tg-time format="r">`, большие превью ссылок (`link_preview_large`).

### Кастомные эмодзи на кнопках (Premium)

Переключатель `use_custom_emoji` и поля ID управляют отображением эмодзи на кнопках в сообщениях:

| Режим | Поведение |
|-------|-----------|
| **Выкл** (по умолчанию) | Unicode-эмодзи (🐦, 🐿️, 📺) — видны всем подписчикам |
| **Вкл** | `icon_custom_emoji_id` (Bot API 9.4) — требует **Telegram Premium у владельца бота** |

При включённом переключателе отображаются поля для ID:

- `custom_emoji_id_bird` — для уведомлений о птицах
- `custom_emoji_id_chipmunk` — для белок/мышей
- `custom_emoji_id_open_live` — для кнопки «Open Live» (старт приложения, общие сообщения)

Если ID не указан — используется обычный Unicode-эмодзи.

**Как получить ID кастомного эмодзи:**

1. Отправьте сообщение с нужным кастомным эмодзи в чат с ботом [@RawDataBot](https://t.me/RawDataBot) — в ответе будет `custom_emoji_id`.
2. Либо используйте бота [@Stickers](https://t.me/Stickers) для получения ID из стикерпаков.
3. Вставьте числовой ID (например, `5368324170671202286`) в соответствующее поле настроек.

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
