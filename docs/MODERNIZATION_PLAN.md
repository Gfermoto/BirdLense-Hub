# План модернизации BirdLense

## Резюме

Переработка проекта BirdLense для работы в Docker на x86 с интеграцией существующей инфраструктуры: BirdNET, Go2RTC, Home Assistant, Frigate, MQTT. Сохраняются идея, цели и UI; убирается привязка к Raspberry Pi.

---

## 1. Предварительная оценка текущего проекта

### 1.1 Архитектура (как есть)

| Компонент | Технологии | Зависимость от RPi |
|-----------|------------|-------------------|
| **Processor** | Python, YOLO (NCNN), BirdNET (birdnetlib), ByteTrack, Picamera2, ALSA | **Критическая** — камера, микрофон, GPIO |
| **Web** | Flask, SQLite, Gunicorn | Нет |
| **UI** | React, Vite, Material UI | Нет |
| **Nginx** | Reverse proxy, MJPEG | Нет |
| **Ntfy** | Push-уведомления | Нет |

### 1.2 Жёсткие зависимости от железа

| Элемент | Текущая реализация | Проблема |
|---------|-------------------|----------|
| **Видео** | Picamera2, libcamera, `/dev/video*` | Только Pi Camera |
| **Аудио** | ALSA `hw:1,0`, USB-микрофон | Только локальный USB |
| **Детекция движения** | PIR через GPIO (gpiozero, lgpio) | Только RPi |
| **Модели** | NCNN (оптимизация под ARM) | Желательна поддержка x86/ONNX |

### 1.3 Что сохраняем

- **UI**: дашборд, таймлайн, статистика видов, детали видео, спектрограммы, управление кормом
- **Логика**: двухэтапная детекция (бинарный детектор + классификатор), трекинг ByteTrack, LLM-верификация
- **Данные**: SQLite, модели видов, визиты, видео, спектрограммы
- **API**: структура эндпоинтов, MCP

---

## 2. Исследование сервисов для интеграции

### 2.1 BirdNET — MQTT

**Источник детекций:** только MQTT. BirdNET и Frigate отдают события по MQTT — этого достаточно.

**BirdNET MQTT:**
- Топик (типичный): `birdnet/sightings` (BirdNET-Pi и аналоги)
- Полезные поля: `comname` / `common_name`, `confidence`, `date`, `time`
- Конфиг: `mqtt.birdnet_topic`, при необходимости — маппинг полей

**Не требуется:** HTTP API, birdnetlib, отправка аудио, локальный анализ.

---

### 2.2 Go2RTC (поток с IP-камеры)

**Статус:** Уже развёрнут в сети. Камеру забираем готовым потоком — указываем URL и имя потока.

**Протоколы:** RTSP, HLS, WebRTC, MJPEG.

**Типичные URL:**
- RTSP: `rtsp://go2rtc-host:1984/camera1` (если камера добавлена как `camera1`)
- HLS: `http://go2rtc-host:1984/api/stream.m3u8?src=camera1`
- MJPEG: через WebSocket или встроенный MJPEG

**Интеграция:**
- `cv2.VideoCapture(rtsp_url)` — работает с RTSP
- FFmpeg для захвата HLS/RTSP и записи
- OpenCV/FFmpeg для извлечения кадров в реальном времени

**Рекомендация:** Новый источник `Go2RTCStreamSource(url, format='rtsp'|'hls')`, использующий `cv2.VideoCapture` или FFmpeg subprocess. Конфиг: `video.go2rtc_url`, `video.stream_name`.

**Ссылки:**
- [Go2RTC HTTP API](https://go2rtc.org/internal/api/)
- [Go2RTC Streams](https://go2rtc.org/internal/streams/)

---

### 2.3 Управление фидером (корм)

**Два варианта — выбор в конфиге:**

| Вариант | Описание | Когда использовать |
|---------|----------|---------------------|
| **MQTT** | Сущность в HA (через MQTT) или MQTT напрямую | Фидер в HA, управление через топики |
| **ESPHome API** | Прямой REST к устройству | Фидер на ESPHome без HA или быстрый доступ |

**MQTT (HA entity):**
- Публикация в топик: `homeassistant/switch/bird_feeder/command` → `ON`/`OFF`
- Или вызов HA REST API: `POST /api/services/switch/turn_on` с `entity_id`

**ESPHome REST API:**
- `POST http://feeder.local/switch/bird_feeder/turn_on`
- `POST http://feeder.local/switch/bird_feeder/turn_off`
- `POST http://feeder.local/switch/bird_feeder/toggle`
- Требуется: `web_server` в конфиге ESPHome

**Конфиг:** `feed.source: mqtt | esphome`, затем `feed.mqtt_topic` / `feed.ha_entity_id` или `feed.esphome_url`, `feed.esphome_switch_id`.

**Ссылки:** [ESPHome Web API](https://esphome.io/web-api/), [HA REST API](https://developers.home-assistant.io/docs/api/rest)

---

### 2.4 Frigate — MQTT

**Источник детекций:** только MQTT.

**Frigate MQTT:**
- Топик: `frigate/events` — события по объектам (new, update, end)
- Поля: `camera`, `label`, `sub_label` (вид при `classification.bird.enabled`), `score`, `start_time`, `end_time`, `has_snapshot`, `has_clip`

**Bird classification:** `classification.bird.enabled: true` → `sub_label` с названием вида.

**Ссылки:** [Frigate MQTT](https://docs.frigate.video/integrations/mqtt/)

---

### 2.5 MQTT — единая точка входа

**Подписки:**
- `frigate/events` — визуальные детекции (птицы, движение)
- `birdnet/sightings` (или аналог) — аудио-детекции BirdNET

**Публикация (опционально):** `birdlense/detections`, `birdlense/feed` для HA и др.

**Конфиг:** `mqtt.broker`, `mqtt.port`, `mqtt.birdnet_topic`, `mqtt.frigate_topic`.

---

## 3. Целевая архитектура

### 3.1 Режимы работы (выбор пользователя)

| Режим | Видео | Триггер движения | Детекция птиц | Подтверждения |
|-------|-------|------------------|---------------|---------------|
| **Hybrid** | Go2RTC | MQTT + OpenCV fallback | YOLO (основной) | Frigate + BirdNET по MQTT |

**Приоритет детекции:** YOLO — основной источник. BirdNET и Frigate по MQTT — дополнительные подтверждения (повышают уверенность, обогащают метаданные).

**Триггер записи:** MQTT (Frigate) при наличии, иначе OpenCV motion detection.

### 3.2 Новые компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│                        BirdLense (Docker x86)                     │
├─────────────────────────────────────────────────────────────────┤
│  Video Source                                                    │
│  ├── Go2RTCStreamSource (RTSP/HLS)         ← готовый поток       │
│  ├── Ring buffer (pre_record)              ← 5–15 сек до триггера │
│  └── Auto-reconnect                        ← при обрыве          │
├─────────────────────────────────────────────────────────────────┤
│  Motion Trigger (MQTT + OpenCV fallback)                          │
│  └── Graceful degradation при сбоях                               │
├─────────────────────────────────────────────────────────────────┤
│  Bird Detection                                                  │
│  ├── YOLO (ONNX) — основной                                      │
│  ├── DetectionMerger — окно слияния ±5 сек                        │
│  ├── SpeciesNormalizer — маппинг названий                         │
│  └── Deduplication — 30–60 сек по виду                           │
├─────────────────────────────────────────────────────────────────┤
│  MQTT (подписка + публикация)                                    │
│  ├── frigate/events, birdnet/sightings     ← подписка            │
│  └── birdlense/detections                  ← publish для HA      │
├─────────────────────────────────────────────────────────────────┤
│  Integrations                                                    │
│  ├── Feeder: MQTT / ESPHome                                       │
│  ├── Weather: OpenWeather / HA                                    │
│  ├── ntfy (rate limit, excluded_species)                          │
│  └── Retention (days / max_gb)                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Убрано:** birdnetlib, BirdNET HTTP, Picamera2, PIR, ALSA.

### 3.3 Конфигурация (default_config.yaml)

```yaml
# Видео — готовый поток из Go2RTC
video:
  go2rtc_url: "http://go2rtc-host:1984"
  stream_name: "bird_cam"
  pre_record_seconds: 5      # ring buffer: сек до триггера
  auto_reconnect: true       # переподключение при обрыве

# Триггер движения: MQTT + OpenCV fallback
motion:
  primary: mqtt
  fallback: opencv

# MQTT — Frigate и BirdNET
mqtt:
  broker: "mqtt.local"
  port: 1883
  frigate_topic: "frigate/events"
  birdnet_topic: "birdnet/sightings"
  publish_topic: "birdlense/detections"   # для HA-автоматизаций
  frigate_camera_filter: ["bird_cam"]
  frigate_label_filter: ["bird"]

# Слияние детекций (YOLO + Frigate + BirdNET)
detection:
  merge_window_seconds: 5     # окно слияния ±5 сек
  dedup_window_seconds: 45  # дедупликация по виду
  species_mapping: {}        # маппинг названий к эталону

# Управление фидером
feed:
  source: mqtt       # mqtt | esphome
  mqtt_topic: "homeassistant/switch/bird_feeder/command"
  esphome_url: "http://feeder.local"
  esphome_switch_id: "bird_feeder"

# Погода (опционально)
weather:
  source: openweather  # openweather | homeassistant
  ha_entity_id: "weather.home"

# Хранение
retention:
  days: 90            # или max_gb
  # max_gb: 50

# Уведомления (ntfy)
notifications:
  enabled: true
  excluded_species: []
  rate_limit_per_minute: 5

# Секреты — только через env (MQTT_PASSWORD, HA_TOKEN, OPENWEATHER_API_KEY)
```

---

## 4. План модернизации по этапам

### Этап 1: Инфраструктура и видео (2–3 дня)

**Цель:** Запуск на x86 без Pi-зависимостей.

1. **Docker**
   - Базовый образ: `python:3.11-slim` или `ultralytics/ultralytics` (amd64)
   - Убрать: `privileged`, устройства `/dev/video*`, `/dev/gpiochip*`, `/dev/snd`
   - Секреты через env: `MQTT_PASSWORD`, `HA_TOKEN`, `OPENWEATHER_API_KEY`

2. **Go2RTCStreamSource**
   - Класс в `sources/go2rtc_stream_source.py`
   - Поддержка RTSP и HLS через `cv2.VideoCapture` или FFmpeg
   - **Автореконнект** при обрыве (exponential backoff, health check)
   - Запись: FFmpeg из RTSP/HLS в файл (видео + аудио, если есть)

3. **Ring buffer (предзапись)**
   - Кольцевой буфер 5–15 сек до триггера
   - При триггере — сохранение «до + после» (как в CCTV)
   - Конфиг: `video.pre_record_seconds`

4. **Конфиг и Live-стрим**
   - Секция `video` с `go2rtc_url`, `stream_name`, `pre_record_seconds`
   - UI: поддержка HLS (hls.js), прокси или iframe

---

### Этап 2: Триггер движения — MQTT + OpenCV fallback (1–2 дня)

1. **MotionTrigger**
   - **Primary:** подписка на `frigate/events` — триггер записи при детекции
   - **Fallback:** OpenCVMotionDetector при отсутствии MQTT
   - **Graceful degradation:** при сбое MQTT — переключение на OpenCV без падения

2. **MQTTEventAggregator**
   - Подписка на `frigate/events` и `birdnet/sightings`
   - Парсинг payload, маппинг полей
   - **MQTT publish:** `birdlense/detections` при детекции (для HA-автоматизаций)
   - MQTT reconnect, last_will для отображения offline в HA

3. **Конфиг**
   - Секция `motion`, `mqtt` с `publish_topic`

---

### Этап 3: YOLO на x86 и слияние детекций (2–3 дня)

1. **YOLO на ONNX** — основной источник детекций
   - Экспорт моделей из NCNN в ONNX
   - Замена NCNN на ONNX Runtime (или Ultralytics)
   - Двухэтапная стратегия: binary + classifier
   - ByteTrack для трекинга

2. **Слияние и дедупликация**
   - **Временное окно** (±5 сек): YOLO + Frigate + BirdNET → одно событие
   - **Дедупликация** (30–60 сек): один вид в окне = один визит, обновление end_time
   - Правило: YOLO primary, MQTT повышает confidence или добавляет вид

3. **Нормализация видов**
   - `species_normalizer.py` — приведение к единому формату (IOC/eBird)
   - Конфиг `species_mapping` для маппинга Frigate/BirdNET → эталон
   - Сохранить Squirrel и не-птицы в фильтрации

4. **Спектрограммы** — опционально
   - Извлечение аудио из видео (FFmpeg) для визуализации в UI

---

### Этап 4: Управление фидером (1 день)

1. **FeedController** — выбор источника
   - **MQTT:** публикация в топик или вызов HA REST API
   - **ESPHome:** `POST {url}/switch/{id}/turn_on` и т.д.

2. **Конфиг**
   - `feed.source: mqtt | esphome`
   - Параметры для выбранного источника

3. **UI**
   - Кнопка «Подать корм» → вызов выбранного API
   - Отображение состояния (из MQTT/HA/ESPHome)

---

### Этап 5: Финальная сборка и документация (1–2 дня)

1. **docker-compose**
   - Профили: `hybrid`, `minimal`
   - Пример `.env.example` (без секретов)
   - Папка `configs/`: minimal, full, frigate-only

2. **Дополнительные фичи**
   - **Политика хранения:** `retention.days` / `retention.max_gb`, фоновое удаление
   - **Погода из HA:** опция `weather.source: homeassistant`
   - **ntfy:** сохранить, rate limit, `notification_excluded_species`
   - **LLM-верификация:** оставить опционально (при совпадении YOLO+MQTT — пропускать)

3. **UI**
   - **Статус компонентов:** индикаторы Video/MQTT/YOLO (green/red)
   - **Ручная коррекция вида:** кнопка «Исправить» на видео (опционально)

4. **Документация**
   - README с Mermaid-диаграммой архитектуры
   - Описание режимов, примеры конфигов, миграция с RPi

5. **Тесты**
   - `Go2RTCStreamSource` с mock, `--mock-mqtt` для разработки

---

## 5. Риски и митигация

| Риск | Митигация |
|------|-----------|
| Задержка/обрыв RTSP/HLS | Ring buffer, автореконнект, health check |
| Разный формат MQTT (BirdNET vs Frigate) | SpeciesNormalizer, `species_mapping` в конфиге |
| Frigate не детектирует птиц | `classification.bird.enabled` или YOLO-only |
| Секреты в конфиге | Только env: `MQTT_PASSWORD`, `HA_TOKEN`, `OPENWEATHER_API_KEY` |
| Переполнение диска | `retention.days` / `retention.max_gb`, фоновое удаление |
| Частичный сбой (MQTT/Go2RTC) | Graceful degradation, fallback на OpenCV |

---

## 6. Оценка трудозатрат

| Этап | Оценка |
|------|--------|
| 1. Инфраструктура и видео (Go2RTC) | 2–3 дня |
| 2. MQTT-агрегатор (Frigate + BirdNET) | 1–2 дня |
| 3. YOLO на x86 (основная детекция) | 2–3 дня |
| 4. Управление фидером | 1 день |
| 5. Сборка и документация | 1–2 дня |
| **Итого** | **8–12 дней** |

---

## 7. Дополнения по консилиуму

Интегрировано из [BRAINSTORM_CONSILIUM.md](BRAINSTORM_CONSILIUM.md):

| Находка | Включено в план |
|---------|-----------------|
| Ring buffer предзапись | Этап 1, `video.pre_record_seconds` |
| Автореконнект потока | Этап 1 |
| Временное окно слияния | Этап 3, `detection.merge_window_seconds` |
| Дедупликация по виду | Этап 3, `detection.dedup_window_seconds` |
| Нормализация видов | Этап 3, `species_normalizer.py` |
| MQTT publish для HA | Этап 2, `mqtt.publish_topic` |
| Политика хранения | Этап 5, `retention.days` |
| Погода из HA | Этап 5, `weather.source: homeassistant` |
| Статус компонентов в UI | Этап 5 |
| ntfy + rate limit | Этап 5, `notifications` |
| Graceful degradation | Этапы 1–2 |
| Секреты через env | Этап 1 |
| LLM опционально | Этап 5 |

**Отложено:** HA Add-on, экспорт в iNaturalist, ручная коррекция вида (низкий приоритет).

**Решённые вопросы:**
- Часовой пояс: UTC в БД, отображение в локальном (браузер)
- Squirrel: сохранить в regional species
- Один инстанс = одна кормушка (multi-tenancy — позже)

---

## 8. Рекомендуемая последовательность реализации

**Исходные условия:** Go2RTC развёрнут, Frigate и BirdNET отдают события по MQTT. Видеопоток — из Go2RTC.

### Оптимальный порядок

```
Этап 1 (видео)     →  Этап 2 (MQTT)       →  Этап 3 (YOLO)     →  Этап 4 (фидер)  →  Этап 5 (сборка)
     │                     │                      │                    │
     └─ Go2RTC              └─ триггер +          └─ основная          └─ MQTT или
        — готовый поток       подтверждения          детекция             ESPHome
```

**Обоснование:**
1. **Видео** — Go2RTC, забираем готовый поток.
2. **MQTT** — триггер движения (Frigate) + OpenCV fallback; Frigate/BirdNET как подтверждения.
3. **YOLO** — основной источник детекций, MQTT — дополнительные подтверждения.
4. **Фидер** — MQTT (HA entity) или ESPHome REST API.

### Старт

Начать с **Этапа 1**: Docker x86 + `Go2RTCStreamSource` + ring buffer + автореконнект.

---

## 9. Общее ревью перед стартом

### Чеклист готовности

| Критерий | Статус |
|----------|--------|
| Архитектура определена | ✅ YOLO + MQTT (Frigate, BirdNET), Go2RTC, фидер (MQTT/ESPHome) |
| Конфиг полный | ✅ video, motion, mqtt, detection, feed, weather, retention, notifications |
| Этапы последовательны | ✅ 1→2→3→4→5, зависимости учтены |
| Риски покрыты | ✅ автореконнект, graceful degradation, retention, секреты |
| Консилиум интегрирован | ✅ ring buffer, слияние, нормализация, статус UI |
| Оценка реалистична | ✅ 8–12 дней с учётом доп. фич |

### Зависимости перед стартом

- [ ] Go2RTC развёрнут, известен URL и имя потока
- [ ] MQTT брокер доступен (Frigate, BirdNET уже публикуют)
- [ ] HA (если фидер/погода через HA) — URL, token
- [ ] ESPHome (если фидер напрямую) — URL устройства, `web_server` включён

### Первый коммит

Рекомендуемый порядок первого коммита:
1. Обновить `default_config.yaml` (новая структура)
2. Создать `sources/go2rtc_stream_source.py` (скелет)
3. Обновить `Dockerfile` processor на amd64
4. Обновить `docker-compose` — убрать devices, privileged

### Критерии готовности Этапа 1

- [ ] BirdLense запускается в Docker на x86
- [ ] Захватывает кадры из Go2RTC (RTSP или HLS)
- [ ] При обрыве — переподключается
- [ ] Ring buffer сохраняет N сек до триггера (триггер пока FakeMotionDetector)
- [ ] Live-стрим отображается в UI

---

### Вердикт ревью

**План готов к реализации.** Все находки консилиума интегрированы, риски учтены, этапы выстроены. Рекомендуется начать с Этапа 1.
