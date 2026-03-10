# MQTT и триггеры BirdLense Hub

## Архитектура триггеров

- **Одно MQTT-подключение** — забираем два топика (frigate, birdnet), если настроены.
- **Триггеры по умолчанию:** Frigate и BirdNET — когда MQTT настроен. Метаданные: кто сработал и что распознал.
- **Дополнительные триггеры:** ESPHome, MQTT (binary), OpenCV.
- **YOLO** — распознаёт и пишет только после триггера и только если что-то распознал в кадре. Добавляет в метаданные свою пометку.

---

# Обнаруженные MQTT-топики (брокер 192.168.1.10)

Подключение к вашему брокеру показало:

## BirdLense Hub — релевантные

| Топик | Назначение | В конфиге |
|-------|------------|-----------|
| `frigate/events` | События Frigate (new/update/end) | `mqtt.frigate_topic` ✓ |
| `frigate/back/*` | Состояние камеры Frigate "back" | — |
| `birdnet` | BirdNET — детекции | `mqtt.birdnet_topic` |
| `birdnet/status` | Статус BirdNET (offline/online) | — |
| `birdnet/soundlevel` | Уровень звука BirdNET-Go | — |
| `birdlense/status` | Статус BirdLense Hub (online) | — |

## Формат BirdNET (топик `birdnet`)

Пример сообщения:

```json
{
  "ID": 13904,
  "SourceNode": "BirdNET-Go",
  "Date": "2026-02-28",
  "Time": "20:49:44",
  "Source": {"id": "audio_card_8f08c61c", "displayName": "Loopback, Loopback PCM"},
  "BeginTime": "2026-02-28T20:49:33.423197398+03:00",
  "EndTime": "2026-02-28T20:49:45.423197398+03:00",
  "SpeciesCode": "cowpig1",
  "ScientificName": "Columba palumbus",
  "CommonName": "Вяхирь",
  "Confidence": 0.53,
  "Latitude": 55.934,
  "Longitude": 36.61,
  "ClipName": "2026/02/columba_palumbus_53p_20260228T204946Z.wav",
  "BirdImage": {
    "URL": "https://upload.wikimedia.org/...",
    "ScientificName": "Columba palumbus",
    "LicenseName": "CC BY 2.0"
  }
}
```

BirdLense Hub извлекает: `CommonName`, `Confidence`, `BeginTime` (для слияния по времени), `ScientificName`, `BirdImage.URL`.

## Формат Frigate (топик `frigate/events`)

События с полями `before`, `after`, `type` (new/update/end). BirdLense Hub использует `after`:
`camera`, `label`, `sub_label` (вид птицы), `top_score`, `frame_time` (Unix timestamp для слияния).

## Рекомендация

```yaml
mqtt:
  birdnet_topic: "birdnet"
```

## Другие топики на брокере

- `tasmota/discovery/*` — Tasmota
- `homeassistant/switch/bird_feeder/command` — реле кормушки (feed)
- `double-take/cameras/*` — Double Take
- `home/sensor1` — сенсор
