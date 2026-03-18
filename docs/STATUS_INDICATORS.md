# Статусы индикаторов (Overview)

## Реальные проверки

| Индикатор | Как проверяется |
|-----------|-----------------|
| **Video** | `check_video_reachable()` — HTTP GET snapshot первой камеры через go2rtc (`/api/frame.jpeg?src=...`). ok/error/not_configured. |
| **MQTT** | `check_mqtt_connected()` — подключение к брокеру (feed_service). Показывается при настроенном `mqtt.broker` (Frigate + BirdNET всегда используют MQTT). |
| **ESPHome** | `check_esphome_reachable()` — HTTP-запрос к URL устройства. Показывается при `feed.source=esphome`. |
| **YOLO** | Процессор шлёт в heartbeat `last_yolo_ok_at` при каждом успешном run. ok если в пределах 5 мин, иначе unknown. |
| **Processor** | Последний heartbeat в ActivityLog (процессор шлёт каждые 60 сек). |

## Триггер (motion)

- **Отображение**: при `motion.source=frigate` показывается `mqtt` (триггер идёт через MQTT).
- **Подсказки**: Frigate и BirdNET — всегда триггер и слияние при MQTT, не только слияние.
