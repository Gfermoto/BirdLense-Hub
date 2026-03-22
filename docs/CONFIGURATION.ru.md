# Конфигурация BirdLense Hub

[English](./CONFIGURATION.md)

---

Конфиг: `app/app_config/user_config.yaml`

Значения по умолчанию в `app/app_config/default_config.yaml`. Пользовательский конфиг переопределяет их (merge).

**Приоритет настроек:** переменные окружения > `user_config.yaml` > `default_config.yaml`. Например, `GO2RTC_URL` в env переопределяет `video.go2rtc_url` в YAML.

**Настройки в UI:** большинство параметров можно менять через веб-интерфейс (Настройки → шестерёнка). YAML остаётся для продвинутых сценариев и переменных окружения.

**Связанные документы:** [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md) (уровни паролей), [API](./API.md) (HTTP), [GLOSSARY](./GLOSSARY.ru.md) (термины).

---

## Как читать ключи

- В таблицах — **точечные пути**, как в YAML: `video.go2rtc_url` → секция `video:`, поле `go2rtc_url:`.
- Поведение «пустой пароль = открытый хаб» см. [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md).

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
| `settings_password` | Пароль **Admin**: настройки, кормушка, система, перезапуск processor. Пусто — без блокировки (типично для дома) |
| `contributor_password` | Опционально пароль **Contributor**: правка видов, «Неизвестные», iNaturalist, экспорт датасета, отчёты — **без** настроек/кормушки/системы. Пусто — один уровень пароля (см. [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md)) |
| `enable_notifications` | Включить уведомления (глобально) |
| `notification_excluded_species` | Виды, исключённые из уведомлений |
| `donate_url` | Ссылка на пожертвования. Кнопка на Overview. Пусто — заглушка. |

**Платформы:** РФ — [Boosty](https://boosty.to), [DonationAlerts](https://donationalerts.com), [DONAT24](https://donat24.ru), ЮMoney. За рубежом — Ko-fi, GitHub Sponsors, Patreon. Настройки → General → вставить URL страницы.

---

## Processor

| Ключ | Описание |
|------|----------|
| `tracker` | Конфиг трекера (bytetrack.yaml) |
| `max_record_seconds` | Макс. запись в секундах |
| `max_inactive_seconds` | Макс. пауза без детекций |
| `min_track_duration` | Мин. длительность трека (сек). По умолчанию 2 — меньше ложных срабатываний |
| `min_confidence_to_process` | Мин. confidence трека (0.10 по умолчанию). 0.03 — больше детекций, 0.10 — строже |
| `species_confidence_overrides` | Пороги по видам: `{"Rare Bird": 0.05}` — для редких видов ниже порог |
| `spectrogram_px_per_sec` | Пикселей на секунду в спектрограмме (только при приходе события BirdNET в окне записи) |
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

Одно подключение — топики frigate и birdnet. Триггеры: Frigate, BirdNET (при MQTT), ESPHome, MQTT binary, OpenCV. YOLO распознаёт после триггера.

| Ключ | Описание |
|------|----------|
| `broker` | Адрес брокера |
| `port` | Порт (1883) |
| `frigate_topic` | Топик событий Frigate |
| `birdnet_topic` | Топик BirdNET |
| `publish_topic` | Топик публикации детекций BirdLense Hub |
| `ha_discovery` | Home Assistant MQTT Autodiscovery — Last Species, Bird at Feeder и др. По умолчанию true. |

**Топики:** `frigate/events` (Frigate), `birdnet` (BirdNET), `birdlense/detections` (публикация), `birdlense/sensor/last_species/state` (HA), `birdlense/binary_sensor/bird_detected/state` (HA). Реле кормушки: `homeassistant/switch/bird_feeder/command`.

**BirdNET:** `CommonName`, `Confidence`, `BeginTime` (для слияния), `ScientificName`, `BirdImage.URL`. **Frigate:** `after` — `camera`, `label`, `sub_label` (вид из Bird Classification), `frame_time`. `sub_label` — приоритет над `label`.

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

**Время последней выдачи:** Hub сохраняет в `data/feed_last_dispense.json` при успешном dispense (MQTT и ESPHome). На Overview в карточке «Управление кормушкой» показывается «Последняя выдача: дата, время».

---

## Weather

| Ключ | Описание |
|------|----------|
| `source` | `openweather` \| `homeassistant` |
| `ha_url` | URL Home Assistant |
| `ha_entity_id` | Entity погоды (weather.home) |

---

## Detection (слияние YOLO + Frigate + BirdNET)

**Источники:** YOLO (видео, EU ~491 вид), Frigate (`sub_label` из [Bird Classification](https://docs.frigate.video/configuration/bird_classification/)), BirdNET (аудио). В UI — полосы под видео, карточки видов: «Источник: YOLO», «Frigate», «BirdNET». Один результат на вид (max confidence).

**Канонические имена:** Common name (Eurasian Jay), не Scientific. `species_mapping` — маппинг вариантов. `species_canonical_mapping.txt` — для «Объединить дубликаты» (System → Записи). Формат: `variant|canonical`.

| Ключ | Описание |
|------|----------|
| `merge_window_seconds` | Окно слияния MQTT (8 сек) |
| `dedup_window_seconds` | Разрыв > N сек = разные визиты (60 сек) |
| `one_per_species` | Один результат на вид (true) |
| `source_priority` | При конфликте: `["yolo", "frigate", "birdnet"]` |
| `min_confidence_to_store` | Мин. confidence (0.05) |
| `species_mapping` | Маппинг названий видов |

**EU-модель:** `best.pt`. US — `best_US.pt`. Обучение: [TRAINING](./TRAINING.ru.md).

## Retention

| Ключ | Описание |
|------|----------|
| `days` | Удалять записи старше N дней |
| `max_gb` | Макс. размер в GB (опционально) |

---

## Gallery (публичная галерея)

Opt-in: при `enabled=true` и `upload_url` Hub загружает лучшие кадры на указанный URL. POST multipart/form-data: `image`, `species`, `confidence`, `timestamp`, `detection_id`, `video_id`, `latitude`, `longitude`. Фильтры: `min_confidence` (0.5), `only_manually_corrected`. Тест: `docker compose -f docker/gallery-test/docker-compose.yml up -d` → http://localhost:8086/api/upload.

| Ключ | Описание |
|------|----------|
| `enabled` | Включить загрузку |
| `upload_url` | URL API приёмника |
| `min_confidence` | Только детекции ≥ порога |
| `only_manually_corrected` | Только проверенные вручную |

**Разбор проблем**

- **«Были посещения», но в галерею пусто:** в Timeline/Overview учитываются и **audio** (BirdNET), и **video**. В галерею попадают **только** строки `VideoSpecies` с `source=video`, с **заполненным `frames`** (боксы трека от процессора) и `confidence >= gallery.min_confidence`. Чисто аудио-визит или видео без `frames` в JSON — **не загружаются**.
- **`min_confidence`:** по умолчанию **0.5**. Если модель даёт 0.35 — снизьте в `user_config.yaml`, например `gallery.min_confidence: 0.35`.
- **`only_manually_corrected: true`:** тогда загрузятся только детекции после ручной правки на Unknowns/видео; иначе галерея будет пустой до правок.
- **Адрес `upload_url`:** полный URL **POST** приёмника (multipart). Сервер должен отвечать **200, 201 или 204**. Проверьте с машины, где крутится Hub: `docker exec birdlense curl -sS -o /dev/null -w '%{http_code}' -X POST …` или временный тестовый контейнер из репозитория.
- **URL из Docker:** хост в `upload_url` должен быть доступен **из контейнера web** (например `http://gallery-test:5000/api/upload` с `docker-compose.gallery-test.yml`). **`http://127.0.0.1:…` на хосте** из контейнера часто указывает **на сам контейнер**, а не на ваш ПК.
- **Логи:** в логе web — `Gallery upload:` (успех), `Gallery upload failed` (код ответа), `Gallery: video N — нет строк для загрузки` (условия фильтра не выполнены), `Gallery upload thread failed` (исключение в потоке).

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
| `processor.save_dataset_crops` | При true — сохранять best_frame в `data/dataset/train/<Species>/` для экспорта и дообучения |
| `processor.dataset_min_confidence` | Мин. confidence (0.0–1.0) для сохранения кадра в датасет. По умолчанию 0.5 |

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

### Web Push

Push-уведомления в браузере (дополнение или альтернатива Telegram). Работает при HTTPS (или localhost).

| Ключ | Описание |
|------|----------|
| `web_push.enabled` | Включается автоматически при первой подписке через UI |
| `web_push.vapid_public_key` | Публичный VAPID-ключ (генерируется автоматически при первом использовании) |
| `web_push.vapid_private_key` | Приватный VAPID-ключ (секрет, маскируется в API) |

**Настройка:** Настройки → Уведомления → «Включить Web Push». Браузер запросит разрешение; подписка сохраняется на сервере. При детекции вида push отправляется всем подписчикам.

**Требования:** HTTPS (или localhost), включённые уведомления (`general.enable_notifications`), `notifications.base_url` для ссылки в push.

## UI

| Ключ | Описание | Где настраивать |
|------|----------|-----------------|
| `unknown_confidence_threshold` | Порог (0–1) для списка «Неизвестные»: детекции с confidence ниже попадают на страницу для ручной проверки. По умолчанию 0.5 | Настройки → Расширенные |

---

## Webhook

| Ключ | Описание |
|------|----------|
| `url` | URL для POST при каждой детекции. JSON: species, confidence, time, source. Для IFTTT, Zapier, своих скриптов |

---

## eBird

| Ключ | Описание |
|------|----------|
| `ebird.country` | Код страны (2 символа: US, RU и т.д.) |
| `ebird.state` | Регион (1–3 символа: NY, CA, MOS для Московской обл.) |
| `ebird.location_name` | Название локации для чеклиста |
| `ebird.protocol` | Stationary \| Traveling \| Incidental \| Historical |
| `ebird.species_mapping` | Маппинг eBird → BirdLense для «Сравнение с регионом». eBird использует Gray (US), BirdLense — Grey (EU). Пример: `Gray-headed Woodpecker: Grey-headed Woodpecker` |
| `secrets.ebird_api_key` | Ключ eBird API для карточки «Сравнение с регионом» на Overview. Получить: [ebird.org/api/keygen](https://ebird.org/api/keygen) |

Настройки → Расширенные. Экспорт «Экспорт для eBird» в Timeline не требует API ключа. Ключ нужен для фичи «Сравнение с регионом».

**Россия, Московская область:** `ebird.country=RU`, `ebird.state=MOS` (или `MO`). Регион для API: RU-MOS.

---

## MCP

| Ключ | Описание |
|------|----------|
| `enabled` | Включить MCP-сервер |
| `token` | Токен доступа (или MCP_TOKEN в env) |

---

## Prometheus / Grafana

Эндпоинты `GET /metrics` и `GET /api/metrics` — формат Prometheus.

**Prometheus** — в `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'birdlense'
    metrics_path: '/api/metrics'
    static_configs:
      - targets: ['birdlense:8085']  # или ваш хост:порт
    scrape_interval: 15s
```

**Метрики:** CPU, память, диск, GPU (если есть), `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total`.

**Grafana** — Prometheus datasource, дашборд по метрикам.

### Алертинг (Prometheus + Alertmanager)

Готовые примеры в репозитории (подстройте пороги и имя `job` под ваш `scrape_configs`):

| Файл | Назначение |
|------|------------|
| [`examples/prometheus/birdlense.rules.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/birdlense.rules.yml) | Алерты: таргет недоступен, диск/память/CPU, опционально «нет новых детекций за 24 ч» |
| [`examples/prometheus/alertmanager.birdlense.example.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/alertmanager.birdlense.example.yml) | Каркас Alertmanager: `route` / `receivers` |

**Prometheus** — добавьте `rule_files` рядом со `scrape_configs`:

```yaml
rule_files:
  - 'birdlense.rules.yml'   # путь к скопированному примеру
```

**Замечания:**

- Правила по умолчанию ожидают scrape с **`job_name: birdlense`** (см. `up{job="birdlense"}`). Если имя job другое — обновите матчеры в файле правил.
- **`BirdlenseDetectionsUnchanged24h`** — опционально: срабатывает в межсезонье или при выключенной кормушке; увеличьте `for`, замьте в Alertmanager или удалите группу `birdlense-optional-activity`.
- Отдельных правил по GPU нет: `birdlense_gpu_usage_percent` экспортируется только при доступной статистике GPU; «зависания» смотрите в **System → Processor logs** и `/api/ui/status`.

Задача: [issue #57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).

---

## Secrets

Координаты и ключи. Настройки → Расширенные. Рекомендуется env: `OPENWEATHER_API_KEY`.

| Ключ | Описание |
|------|----------|
| `openweather_api_key` | OpenWeather API для виджета погоды |
| `xeno_canto_api_key` | Xeno-canto API для воспроизведения птичьих песен (xeno-canto.org/account) |
| `ebird_api_key` | eBird API для сравнения с регионом (ebird.org/api/keygen) |
| `latitude`, `longitude` | Координаты для погоды и eBird |

---

## См. также

[INSTALL](./INSTALL.ru.md) · [ARCHITECTURE](./ARCHITECTURE.ru.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md) · [API](./API.ru.md) · [SCENARIOS](./SCENARIOS.ru.md) · [GLOSSARY](./GLOSSARY.ru.md)
