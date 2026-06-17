# Jetson Nano B01 — аппаратная и программная настройка под BirdLense Hub

**Статус:** Draft (2026-06-17)  
**Связано:** [ADR platform profiles](adr-platform-profiles-intel-jetson.md), epic «Jetson NVIDIA-native pipeline»

---

## 1. Роль Jetson в проекте

Jetson Nano B01 (4 ГБ) — **вторая боевая платформа** BirdLense Hub (рядом с Intel NUC). Цель:

- детекция и трекинг на **lores** (704×576) с минимальной нагрузкой на CPU;
- **event-triggered** запись main/high-res (не непрерывный dual-stream decode);
- классификация и эмбеддинг **по требованию** на кропах;
- общая логика (визиты, MQTT, UI, геометрия) — **тот же код**, платформа через `BIRDLENSE_PLATFORM=jetson_nano`.

**Не цель:** запустить текущий Intel-пайплайн «как есть» на CPU/torch — это уже доказало перегрузку и слепоту на слабом железе.

---

## 2. Аппаратная подготовка (обязательно)

### 2.1 Питание и охлаждение

| Компонент | Требование | Почему |
|-----------|------------|--------|
| БП | **5 В / 4 А (20 Вт)**, barrel jack 5.5×2.1 мм | micro-USB не даёт MAXN; троттлинг GPU |
| Радиатор + вентилятор | активное охлаждение SoC и RAM | при `jetson_clocks` >75°C → сброс частот |
| Накопитель | **USB 3.0 SSD** или NVMe через HAT (не дешёвая microSD) | запись клипов + wear; swap на SD убить |

### 2.2 Режимы мощности

После каждой загрузки (или через systemd unit):

```bash
sudo nvpmodel -m 0          # 10W MAXN
sudo jetson_clocks          # фикс. макс. частоты (нужен вентилятор!)
```

Проверка: `jtop` (пакет `jetson-stats`) — GPU ~921 MHz, CPU ~1479 MHz, TEMP <80°C.

### 2.3 Память (4 ГБ — узкое место)

```bash
sudo apt install -y zram-config
sudo systemctl enable zram-config
```

- **Headless:** `sudo systemctl set-default multi-user.target` (+300–500 МБ RAM).
- **Не использовать** swap на microSD для постоянной нагрузки.
- Ожидаемый бюджет RAM (2 камеры, event pipeline):
  - DeepStream сторож (2× lores): ~0.8 ГБ
  - Ring buffer high-res (2× ~2 с I420): ~0.2–0.4 ГБ (с ZRAM меньше)
  - Пик записи NVENC + classifier: до ~1.5 ГБ на 10 с
  - ОС + Hub API/UI: ~0.5–1 ГБ  
  **Итого:** укладываемся при headless + ZRAM + лимите контейнера 3 ГБ.

---

## 3. Программная база

### 3.1 ОС и JetPack

- Рекомендуется **JetPack 4.6.x** (L4T R32.7) на Nano B01 — проверенная связка с DeepStream 6.x.
- Docker + **NVIDIA Container Toolkit** (`runtime: nvidia`).
- Пользователь в группе `docker`.

### 3.2 Стек BirdLense на Jetson (целевой)

| Слой | Технология | Статус в репо |
|------|------------|---------------|
| Hub UI/API | существующий Flask + nginx в контейнере | `Dockerfile.jetson` (эволюция → DeepStream base) |
| Live detect/track | **DeepStream** Primary GIE + NvDCF | план |
| Inference weights | **TensorRT FP16** `.engine` | `tensorrt` в `selector.py` — planned |
| Live decode lores | NVDEC / DeepStream | `ffmpeg_nvdec` — planned |
| High-res capture | Ring buffer + event trigger | новый модуль |
| Record encode | **NVENC** (`nvv4l2h264enc`) | `video.encoding: nvidia` — planned |
| Classifier / ReID | Secondary GIE или TRT на 1 кроп/событие | план |
| Offline regen | существующий `track_regenerator` на `.pt`/`.engine` | общий код |

### 3.3 Переменные окружения (Jetson)

```bash
export BIRDLENSE_PLATFORM=jetson_nano
export BIRDLENSE_INFERENCE_BACKEND=tensorrt   # после реализации
export BIRDLENSE_OPENVINO_BINARY_ENABLED=0
export BIRDLENSE_INFERENCE_DEVICE=cuda
# GO2RTC_URL — на площадке (LAN), не копировать с VPS без правки
```

Overlay: `deploy/profiles/jetson-nano/config.overlay.yaml`, `.env.example`.

### 3.4 Сборка и деплой

```bash
# Локально на Jetson
cd app
BIRDLENSE_PLATFORM=jetson_nano docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d --build

# С dev-машины
# scripts/deploy.local.sh:
export BIRDLENSE_PLATFORM=jetson_nano
export DEPLOY_HOST="gfer@192.168.8.199"
export DEPLOY_URL="http://192.168.8.199:8085"
make deploy
```

### 3.5 Конвертация весов — **те же модели, другой runtime**

**Принцип:** не меняем обученные сети на «лёгкие замены» (MobileNet/OSNet из чужих гайдов). Меняем только **backend экспорта**: `.pt` → TensorRT `.engine` на Jetson.

| Роль | Текущая модель (prod Intel) | Путь в репо | Jetson export |
|------|----------------------------|-------------|---------------|
| **Детектор** | `trapper_ai_v02_2024` (YOLO binary) | `processor/models/detection/weights/trapper_ai_v02_2024.pt` | TRT FP16, input **704×576** (letterbox как сейчас) |
| **Классификатор** | Birder EU `convnext_v2_tiny_eu-common256px` | `processor/models/classification/weights/convnext_v2_tiny_eu-common256px.pt` | TRT FP16, input **256×256** (не 224) |
| **Эмбеддинг / ReID** | DINOv2 (runtime hub cache) | `processor.reid.*`, `models/reid/hub_cache` | TRT или torch+cuda на 1 кроп/событие; **не** заменять на OSNet без A/B |

OpenVINO IR (`*_openvino_model/`) на Jetson **не используем** — только как эталон parity при конвертации.

```bash
# План: scripts/convert_to_trt.sh
# --detector trapper_ai_v02_2024.pt --imgsz 704,576
# --classifier convnext_v2_tiny_eu-common256px.pt --imgsz 256
# --reid dinov2 (опционально, фаза 2)
```

Конвертацию **выполнять на целевом Jetson** (или в контейнере с тем же TRT), иначе engine несовместим.

---

## 4. RTSP и сеть (замечания ревью, адаптировано под BirdLense)

### 4.0 Источник потоков: go2rtc vs прямой RTSP

На площадке Hub уже использует **go2rtc** (`video.go2rtc_url`, RTSP substream/main). На Jetson:

- **Предпочтительно:** RTSP URL из go2rtc на LAN (`rtsp://<go2rtc>:8554/...`) — единая точка как на Intel.
- **Альтернатива:** прямой RTSP с камеры в DeepStream/GStreamer — если go2rtc не нужен на Nano.

`/dev/video0` в Docker **не нужен** для RTSP.

### 4.1 Docker: `network_mode: host`

Ревьювер прав: RTSP/RTP использует динамические UDP-порты; проброс через bridge болезненен.

| Режим | Плюсы | Минусы для Hub |
|-------|-------|----------------|
| **`network_mode: host`** | нулевая NAT-задержка, проще RTSP | нет `ports: 8085:8080` — UI на **8080** хоста или `BIRDLENSE_PORT=8080` |
| **bridge** (как сейчас) | изоляция, проброс 8085 | RTSP из контейнера к LAN-камерам обычно ок; RTP иногда ломается |

**Решение для E0:** профиль `deploy/profiles/jetson-nano/compose.host-network.yml` (опционально) с `network_mode: host`; дефолт — bridge до полевого теста.

### 4.2 GStreamer / DeepStream для RTSP

Параметры из ревью — принимаем:

- `rtspsrc latency=300 drop-on-latency=true`
- `nvv4l2decoder enable-max-performance=1`
- `appsink sync=false` для ring buffer
- DeepStream `type=4`, `latency=300`, `cudadec-memtype=0`

Пример lores (704×576):

```bash
gst-launch-1.0 rtspsrc location=rtsp://.../lores latency=300 drop-on-latency=true ! \
  rtph264depay ! h264parse ! nvv4l2decoder enable-max-performance=1 ! \
  nvvidconv ! video/x-raw,format=NV12,width=704,height=576 ! \
  appsink name=lores_sink sync=false
```

### 4.3 Синхронизация lores ↔ high-res

Не frame-index, а **timestamp/PTS**: ring buffer `get_frame_at(lores_timestamp)` с допуском ≤200–500 ms (см. ревью `RingBufferSync`).

### 4.4 RTSP reconnect и мониторинг (новый этап E9)

- Exponential backoff реконнект при обрыве (`max_retries`, base delay 1s).
- Health: `gst-discoverer-1.0` или probe «кадр за N сек» каждые 60s.
- 3 fail подряд → алерт (Telegram / Hub activity log).

Задача: GitHub **#655** (E9), связана с E1/E7.

---

## 5. Архитектура пайплайна (рекомендуемая)

Консультанты предлагали чистый DeepStream на 4 потока — **для Nano 4 ГБ это рискованно**. Согласовано с BirdLense:

### 5.1 «Сторож + охотник» (гибрид)

1. **Сторож (DeepStream):** только **2 потока lores** (по одному на камеру).  
   YOLO TensorRT FP16, `interval=3–4` (~7 FPS effective), NvDCF каждый кадр.  
   Probe → событие `TRIGGER_RECORD(camera_id, track_id, bbox, ts)`.

2. **Кольцевой буфер high-res:** лёгкий GStreamer `uridecodebin ! nvvidconv ! appsink` на main stream;  
   `deque` последних 60–90 кадров (~2–3 с). **Не** пишем на диск до триггера.

3. **Охотник (Python):** по триггеру — pre-roll из deque + post-roll 8–10 с → **NVENC** → mp4 на SSD.  
   Один репрезентативный кроп → **тот же** Birder convnext + DINOv2 ReID (TRT/torch), не замена моделей.

4. **Hub persist:** существующий API/SQLite — ingest метаданных и путь к файлу (адаптер, не переписывать UI с нуля).

### 5.2 Альтернатива (фаза 2): один high-res поток на камеру в DeepStream

Primary GIE `network-width/height=704×576` на **main** stream — без рассинхрона lores/main.  
Требует больше GPU на decode; оценить на полевом тесте после MVP сторожа.

### 5.3 Что сохраняем из текущего Hub

- `feeder_close` / `feeder_far`, `camera_tuning_by_role`, geometry contract (`frame_shape.py`)
- Linear stages: trigger → detect_track → classify → persist (реализация стадий разная)
- Frigate MQTT как **триггер-подсказка**, не замена детектора
- **Модели:** trapper детектор, Birder convnext классификатор, DINOv2 ReID — те же веса, TRT-обёртка
- OpenAPI, UI, Telegram, visit model

---

## 6. Настройка камер (2× dual stream)

| Поток | Назначение | Разрешение | FPS |
|-------|------------|------------|-----|
| Substream / detect | DeepStream сторож | 704×576 (или близко) | 7–15 |
| Main | Ring buffer + запись по событию | 1080p типично | 15–25 |

- Оба **H.264**, согласованный GOP (I-frame каждые 2–4 с).
- NTP на камере — для PTS и `sync-inputs` если понадобится DeepStream mux.
- В `video.cameras[]`: `tuning_role: feeder_close|feeder_far`, `detect_stream_name` / main URL через go2rtc.

---

## 7. Чек-лист перед боем на площадке

- [ ] 5V/4A barrel, вентилятор, SSD
- [ ] `nvpmodel -m 0`, `jetson_clocks`, ZRAM, headless
- [ ] `nvidia-smi` / `tegrastats` в контейнере
- [ ] `.engine` для **trapper + convnext** собраны на этом Jetson
- [ ] go2rtc/MQTT/камеры в LAN (не IP VPS)
- [ ] RTSP: `latency=300`, health-check, reconnect policy
- [ ] `BIRDLENSE_PLATFORM=jetson_nano`, OpenVINO отключён
- [ ] Smoke: health OK, одна тестовая запись с persist
- [ ] Мониторинг: `jtop`, Hub `yolo_frames_with_tracks`, температура

---

## 8. Риски и эскалация железа

| Симптом | Действие |
|---------|----------|
| OOM / swap | уменьшить ring buffer, `interval`, отключить ReID live |
| GPU throttle | охлаждение, снизить `binary_imgsz` до 640 |
| 2 камеры не тянут | event-only high-res обязателен; иначе **Orin Nano 8GB** |
| Engine mismatch | пересобрать TRT на устройстве |

---

## 9. Ссылки

- `deploy/profiles/jetson-nano/`
- `app/Dockerfile.jetson`, `app/docker-compose.jetson.yml`
- `scripts/platform-profile.sh`
- Epic GitHub: [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645)
- RTSP monitoring: [#655](https://github.com/Gfermoto/BirdLense-Hub/issues/655) (E9)
