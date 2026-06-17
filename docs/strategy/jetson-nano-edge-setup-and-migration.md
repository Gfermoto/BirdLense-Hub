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

### 3.5 Конвертация весов (на Jetson или x86 с trtexec для aarch64)

```bash
# Скрипт (план): scripts/convert_to_trt.sh
# Вход: trapper_ai_v02_2024.pt, classifier best.pt
# Выход: app/processor/models/detection/weights/*.engine
# FP16, фиксированный input под lores 704×576 (детектор) и 224×224 (классификатор)
```

Конвертацию **выполнять на целевом Jetson** (или в контейнере с тем же TRT), иначе engine несовместим.

---

## 4. Архитектура пайплайна (рекомендуемая)

Консультанты предлагали чистый DeepStream на 4 потока — **для Nano 4 ГБ это рискованно**. Согласовано с BirdLense:

### 4.1 «Сторож + охотник» (гибрид)

1. **Сторож (DeepStream):** только **2 потока lores** (по одному на камеру).  
   YOLO TensorRT FP16, `interval=3–4` (~7 FPS effective), NvDCF каждый кадр.  
   Probe → событие `TRIGGER_RECORD(camera_id, track_id, bbox, ts)`.

2. **Кольцевой буфер high-res:** лёгкий GStreamer `uridecodebin ! nvvidconv ! appsink` на main stream;  
   `deque` последних 60–90 кадров (~2–3 с). **Не** пишем на диск до триггера.

3. **Охотник (Python):** по триггеру — pre-roll из deque + post-roll 8–10 с → **NVENC** → mp4 на SSD.  
   Один репрезентативный кроп → TensorRT classifier + embedder → JSON рядом с mp4.

4. **Hub persist:** существующий API/SQLite — ingest метаданных и путь к файлу (адаптер, не переписывать UI с нуля).

### 4.2 Альтернатива (фаза 2): один high-res поток на камеру в DeepStream

Primary GIE `network-width/height=704×576` на **main** stream — без рассинхрона lores/main.  
Требует больше GPU на decode; оценить на полевом тесте после MVP сторожа.

### 4.3 Что сохраняем из текущего Hub

- `feeder_close` / `feeder_far`, `camera_tuning_by_role`, geometry contract (`frame_shape.py`)
- Linear stages: trigger → detect_track → classify → persist (реализация стадий разная)
- Frigate MQTT как **триггер-подсказка**, не замена детектора
- OpenAPI, UI, Telegram, visit model

---

## 5. Настройка камер (2× dual stream)

| Поток | Назначение | Разрешение | FPS |
|-------|------------|------------|-----|
| Substream / detect | DeepStream сторож | 704×576 (или близко) | 7–15 |
| Main | Ring buffer + запись по событию | 1080p типично | 15–25 |

- Оба **H.264**, согласованный GOP (I-frame каждые 2–4 с).
- NTP на камере — для PTS и `sync-inputs` если понадобится DeepStream mux.
- В `video.cameras[]`: `tuning_role: feeder_close|feeder_far`, `detect_stream_name` / main URL через go2rtc.

---

## 6. Чек-лист перед боем на площадке

- [ ] 5V/4A barrel, вентилятор, SSD
- [ ] `nvpmodel -m 0`, `jetson_clocks`, ZRAM, headless
- [ ] `nvidia-smi` / `tegrastats` в контейнере
- [ ] `.engine` детектор + классификатор собраны **на этом Jetson**
- [ ] go2rtc/MQTT/камеры в LAN (не IP VPS)
- [ ] `BIRDLENSE_PLATFORM=jetson_nano`, OpenVINO отключён
- [ ] Smoke: health OK, одна тестовая запись с persist
- [ ] Мониторинг: `jtop`, Hub `yolo_frames_with_tracks`, температура

---

## 7. Риски и эскалация железа

| Симптом | Действие |
|---------|----------|
| OOM / swap | уменьшить ring buffer, `interval`, отключить ReID live |
| GPU throttle | охлаждение, снизить `binary_imgsz` до 640 |
| 2 камеры не тянут | event-only high-res обязателен; иначе **Orin Nano 8GB** |
| Engine mismatch | пересобрать TRT на устройстве |

---

## 8. Ссылки

- `deploy/profiles/jetson-nano/`
- `app/Dockerfile.jetson`, `app/docker-compose.jetson.yml`
- `scripts/platform-profile.sh`
- Epic GitHub: «Jetson NVIDIA-native pipeline» (родительский issue)
