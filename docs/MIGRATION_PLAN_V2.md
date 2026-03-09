# План миграции BirdLense v2

## Резюме

Точная архитектура на основе исследования форматов и топиков. Источники: Frigate MQTT docs, BirdNET-Pi/Go, Go2RTC, Tasmota, ESPHome, Telegram Bot API, ntfy, OpenWeather.

---

## 1. Видео — Go2RTC

### 1.1 Получение потоков

| Способ | URL | Примечание |
|-------|-----|------------|
| RTSP | `rtsp://host:8554/{stream_name}` | Go2RTC: HTTP=1984, RTSP=8554 |
| HLS | `http://host:1984/api/stream.m3u8?src={stream_name}` | Для браузера |
| WebRTC | через go2rtc WebSocket API | Live view |

**Конфиг:** `video.go2rtc_url`, `video.stream_name`, `video.cameras[]` (id, stream_name, name).

**Множество камер:** список `cameras` с `id` = имя во Frigate/Go2RTC, `stream_name` = поток.

---

## 2. Триггеры записи

| Источник | MQTT топик / API | Формат | Когда срабатывает |
|----------|------------------|--------|-------------------|
| **OpenCV** | — | — | Анализ каждого кадра, motion в изображении |
| **Frigate events** | `frigate/events` | JSON (type, before, after) | Детекция объекта (bird, Bird и др.) |
| **Frigate motion** | `frigate/{camera}/motion` | `ON` / `OFF` | Движение на камере (без классификации) |
| **BirdNET** | `birdnet/sightings` | JSON | Аудио-детекция птицы |
| **MQTT датчик** | настраиваемый | `ON`/`1`/`true` | Tasmota PIR, Shelly, HA binary_sensor |
| **ESPHome** | HTTP `GET /binary_sensor/{id}` | JSON `state: ON` | Бинарный датчик по IP |

### 2.1 Frigate MQTT — события

**Топик:** `frigate/events` (префикс `frigate` настраивается в Frigate).

**Payload (JSON):**
```json
{
  "type": "new" | "update" | "end",
  "before": { ... },
  "after": {
    "id": "1607123955.475377-mxklsc",
    "camera": "front_door",
    "label": "person",
    "sub_label": ["John Smith", 0.79],
    "top_score": 0.958984375,
    "score": 0.87890625,
    "start_time": 1607123955.475377,
    "end_time": null,
    "box": [432, 496, 544, 854],
    "current_zones": ["yard", "driveway"],
    ...
  }
}
```

**Поля для BirdLense:** `camera`, `label`, `sub_label` (вид при classification.bird), `top_score`/`score`, `start_time`.

**Доп. топики Frigate:**
- `frigate/{camera}/motion` — `ON`/`OFF` (движение без объекта)
- `frigate/available` — `online`/`offline`

### 2.2 BirdNET MQTT

**BirdNET-Pi топик:** `birdnet/sightings`

**Payload (JSON):**
```json
{
  "Common_Name": "House Sparrow",
  "Scientific_Name": "Passer domesticus",
  "Confidence_Score": "0.91",
  "Date": "2024-01-15",
  "Time": "14:30:22",
  "Latitude": "55.75",
  "Longitude": "37.62",
  "link": "http://...",
  "Image": "http://..."
}
```

**Альтернативные поля:** `comname`, `common_name`, `confidence`, `species` — маппинг в коде.

**BirdNET-Go топик:** `birdnet` (другой формат: ID, SourceNode, Date, Time, BeginTime, EndTime).

**Конфиг:** `mqtt.birdnet_topic` (по умолчанию `birdnet/sightings`), поддержка обоих форматов.

### 2.3 MQTT бинарный датчик (Tasmota PIR, Shelly)

| Устройство | Топик | Payload |
|------------|-------|---------|
| Tasmota PIR | `stat/{topic}/PIR1` или `stat/{topic}/MOTION` | `ON` / `OFF` |
| Tasmota Rule | настраиваемый | `ON` / `1` / `true` |
| ESPHome MQTT | `{main_topic}/binary_sensor/{id}/state` | `ON` / `OFF` |
| Home Assistant | `homeassistant/binary_sensor/.../state` | `ON` / `OFF` |

**Конфиг:** `motion.source: mqtt`, `motion.mqtt_topic`.

### 2.4 ESPHome бинарный датчик (HTTP)

**URL:** `GET http://{host}/binary_sensor/{sensor_id}` (web_server в ESPHome).

**Ответ:** `{"state": "ON", "value": true}` или `{"state": "OFF"}`.

**Конфиг:** `motion.source: esphome`, `motion.esphome_url`, `motion.esphome_sensor_id`.

---

## 3. Распознавание (детекция видов)

| Источник | Тип | Данные |
|----------|-----|--------|
| **YOLO** | локальный | bbox, species, confidence из кадров |
| **Frigate** | MQTT `frigate/events` | label, sub_label (при classification.bird), score |
| **BirdNET** | MQTT `birdnet/sightings` | Common_Name, Confidence_Score |

**Слияние:** окно ±5 сек, дедупликация 30–60 сек, нормализация названий (species_mapping).

---

## 4. Оповещения

| Канал | Протокол | Конфиг |
|-------|----------|--------|
| **Telegram** | HTTP `POST https://api.telegram.org/bot{token}/sendMessage` | `notifications.telegram_bot_token`, `notifications.telegram_chat_id` |
| **MQTT** | Publish в `birdlense/detections` | `mqtt.publish_topic` (для HA, Node-RED, mqttwarn) |
| **ntfy** | HTTP `POST/PUT {ntfy_url}/{topic}` | `notifications.ntfy_url`, `notifications.ntfy_topic` |

### 4.1 Telegram Bot API

```
POST https://api.telegram.org/bot<TOKEN>/sendMessage
Content-Type: application/json

{
  "chat_id": "<CHAT_ID>",
  "text": "🦜 House Sparrow (0.92) at 14:30",
  "parse_mode": "HTML"
}
```

**chat_id:** получить через @userinfobot или при первом сообщении боту.

### 4.2 ntfy

- **HTTP:** `curl -d "message" https://ntfy.sh/mytopic` или локальный `http://host:8086/birdlense`
- **MQTT:** ntfy не поддерживает MQTT напрямую; мост через mqttwarn: MQTT → mqttwarn → ntfy HTTP

### 4.3 MQTT publish

**Топик:** `birdlense/detections` (или настраиваемый).

**Payload:**
```json
{
  "species": "House Sparrow",
  "confidence": 0.92,
  "source": "yolo",
  "timestamp": "2024-01-15T14:30:22Z",
  "camera": "bird_cam"
}
```

---

## 5. Погода

**OpenWeather API:** `https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}`

**Конфиг:** `secrets.openweather_api_key`, `secrets.latitude`, `secrets.longitude`.

---

## 6. Дополнительно

| Компонент | Описание |
|-----------|----------|
| **Реле подкормки** | MQTT (Tasmota) или ESPHome REST — `turn_on`/`turn_off` |
| **Хранение** | `retention.days`, фоновое удаление старых записей |
| **Статус** | `birdlense/status` — `online`/`offline` (MQTT LWT) |
| **Множество камер** | `video.cameras[]`, фильтр Frigate по `camera` |

---

## 7. Сводная таблица MQTT топиков

| Назначение | Топик | Направление |
|------------|-------|-------------|
| События Frigate | `frigate/events` | Subscribe |
| Движение Frigate | `frigate/{camera}/motion` | Subscribe |
| BirdNET-Pi | `birdnet/sightings` | Subscribe |
| BirdNET-Go | `birdnet` | Subscribe |
| Детекции BirdLense | `birdlense/detections` | Publish |
| Статус BirdLense | `birdlense/status` | Publish (LWT) |
| Tasmota PIR | `stat/{device}/PIR1` | Subscribe |
| Реле Tasmota | `cmnd/{device}/Power` | Publish |

---

## 8. Конфиг (обновлённый)

```yaml
video:
  go2rtc_url: "http://frigate:1984"
  stream_name: "bird_cam"
  cameras: []  # или [{id, stream_name, name}]

motion:
  source: opencv  # opencv | frigate | frigate_motion | birdnet | mqtt | esphome
  frigate_topic: "frigate/events"
  frigate_motion_topic: "frigate/+/motion"  # опционально
  birdnet_topic: "birdnet/sightings"
  mqtt_topic: ""  # для Tasmota PIR
  esphome_url: ""
  esphome_sensor_id: ""
  frigate_camera_filter: []
  frigate_label_filter: ["bird", "Bird"]

mqtt:
  broker: ""
  port: 1883
  publish_topic: "birdlense/detections"

notifications:
  enabled: true
  telegram_bot_token: ""
  telegram_chat_id: ""
  ntfy_url: "http://birdlense.local:8086"
  ntfy_topic: "birdlense"
  publish_mqtt: true  # дублировать в birdlense/detections
  excluded_species: []
  rate_limit_per_minute: 5

feed:
  source: none  # none | mqtt | esphome
  mqtt_topic: "cmnd/bird_feeder/Power"
  esphome_url: "http://feeder.local"
  esphome_switch_id: "bird_feeder"
  duration_seconds: 3

weather:
  source: openweather
```

---

## 9. Что реализовать

1. **Триггер Frigate motion** — подписка на `frigate/{camera}/motion`, ON = запись (без ожидания объекта).
2. **Триггер BirdNET** — подписка на `birdnet/sightings` как отдельный триггер (аудио-детекция без видео).
3. **Telegram** — отправка при детекции через Bot API.
4. **Маппинг BirdNET-Pi/Go** — единый парсер для обоих форматов.
5. **Настройки** — UI для Telegram (token, chat_id), ntfy, MQTT publish.
