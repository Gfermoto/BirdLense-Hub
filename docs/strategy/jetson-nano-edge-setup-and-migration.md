# Jetson Nano B01 — аппаратная и программная настройка под BirdLense Hub

**Статус:** Final review plan (2026-06-17)  
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

### 2.4 Performance budget и graceful degradation

Nano нельзя вести как «маленький сервер». Для него нужен бюджет, который enforced кодом:

| Ресурс | Бюджет MVP | Если вышли за бюджет |
|--------|------------|----------------------|
| RAM container | ≤3.0 ГБ sustained, без OOM | уменьшить ring buffer, отключить ReID live, classifier keyframes=1 |
| GPU | ≤80–85% sustained | поднять `interval`, снизить detector input до 640, отключить secondary live |
| CPU | ≤250% sustained (из 4 cores) | убрать OpenCV hot path, только GStreamer/DS metadata |
| Температура | <75–80°C | fan/jetson_clocks policy, снизить FPS/interval |
| Latency event | pre-roll 2–3 c + post-roll 8–10 c | сохранять клип даже без classifier/ReID, enrich позже |

**Правило:** если ML-обогащение не укладывается, сохраняем видео + bbox metadata, а classification/ReID переносим в deferred job. Потеря вида лучше, чем потеря события.

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

### 3.5 E0 — Ручные шаги подготовки железа (Manual Provisioning)

**Цель:** Надежная база — SSD под систему/данные, SD только для загрузчика. Время: ~30–45 мин.

#### 1. Образ ОС
- **Базовый:** **NVIDIA JetPack 4.6.1 (L4T R32.7.1)** — установить на SD-карту.
- Скачать: [JetPack 4.6.1 SD Card Image](https://developer.nvidia.com/embedded/jetpack-sdk-461) → `jetson-nano-sd-r32.7.1.img.zip`.
- Записать на microSD (минимум 16 ГБ, класс A2/V30): `balenaEtcher` / `dd`.

#### 2. Обновление до JetPack 4.6.4 через пакетный менеджер
После первой загрузки с базовой SD:

```bash
# Обновить доступные пакеты L4T/JetPack из NVIDIA apt repo
sudo apt update
sudo apt update && sudo apt full-upgrade -y

# Поставить/обновить JetPack meta-package без переустановки образа
sudo apt install -y nvidia-jetpack

# Проверка версии
cat /etc/nv_tegra_release
```

Ожидаемо: `R32.7.x`; если apt не поднимает до `R32.7.4`, фиксируем фактическую `L4T`-версию в deployment notes и не смешиваем DeepStream/JetPack версии.

#### 3. Первичная загрузка (на SD)
```bash
# Включить Jetson с SD, пройти OEM config (locale, user, pass, hostname)
# Пользователь: gfer (как на проде), пароль: <ваш>
# Hostname: birdlense-jetson
# Включить SSH: sudo systemctl enable ssh --now
```

#### 4. Подключение и подготовка SSD (USB 3.0 или NVMe через HAT)
```bash
# Определить диск (обычно /dev/sda или /dev/nvme0n1)
lsblk

# Разметка: одна partition ext4 на весь диск
sudo parted /dev/sda mklabel gpt
sudo parted /dev/sda mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L birdlense-data /dev/sda1
```

#### 5. Перенос rootfs на SSD (rootfs-on-SSD способ — надежнее symlink)
```bash
# Смонтировать SSD
sudo mkdir /mnt/ssd
sudo mount /dev/sda1 /mnt/ssd

# rsync текущей системы (исключаем /mnt, /proc, /sys, /dev, /run, /tmp)
sudo rsync -aAXv --exclude={"/mnt/*","/proc/*","/sys/*","/dev/*","/run/*","/tmp/*","/lost+found"} / /mnt/ssd/

# Редактировать /mnt/ssd/etc/fstab: добавить запись для SSD как /
# UUID=<ssd-uuid>  /  ext4  defaults,noatime  0  1
# (UUID узнать: blkid /dev/sda1)

# Обновить extlinux.conf на SD для загрузки с SSD
# Файл: /boot/extlinux/extlinux.conf (на SD)
# В APPEND строку ядра добавить: root=PARTUUID=<partuuid-of-ssd-partition> rootwait
# PARTUUID: blkid -s PARTUUID -o value /dev/sda1

# Перезагрузка — должна загрузиться с SSD
sudo reboot
```

#### 6. Проверка и настройка после перезагрузки
```bash
# Проверить, что корень на SSD
df -h /          # должен показывать /dev/sda1
lsblk            # SD (mmcblk0) — только /boot, SSD (sda) — /

# Форматировать SD в FAT32 для загрузчика (опционально, оставить как есть — тоже ок)
# Основное: на SD больше нет записей — износ минимален.
```

#### 7. Docker data-root на SSD (критично для надежности контейнеров)
```bash
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "data-root": "/var/lib/docker",
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
EOF
sudo systemctl restart docker
```

#### 8. Jetson-специфичные настройки (автоматизировать через systemd unit)
```bash
# /etc/systemd/system/jetson-performance.service
cat <<EOF | sudo tee /etc/systemd/system/jetson-performance.service
[Unit]
Description=Jetson MAXN Performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nvpmodel -m 0
ExecStart=/usr/bin/jetson_clocks
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now jetson-performance
```

#### 9. ZRAM и headless (как в разделе 2.3/2.4)
```bash
sudo apt update && sudo apt install -y zram-config
sudo systemctl enable zram-config
sudo systemctl set-default multi-user.target   # headless, +300–500 MB RAM
```

#### 10. Проверка перед деплоем кода
```bash
# Должно показать: GPU 921 MHz, CPU 1479 MHz, Temp <50°C в idle
jtop

# Docker + nvidia runtime на Jetson Nano проверяем через L4T image, не nvidia-smi
docker run --rm --runtime nvidia nvcr.io/nvidia/l4t-base:r32.7.1 bash -lc 'ls /usr/local/cuda && echo OK'

# DeepStream/NVENC plugins (после установки DeepStream base/runtime)
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc
```

---

**После E0 ручной части:** Jetson загружается с SSD, Docker хранит образы/контейнеры на SSD, система в MAXN, headless, ZRAM активен. Готово к `make deploy`.

### 3.6 Конвертация весов — **те же модели, другой runtime**

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

На площадке Hub уже использует **go2rtc** (`video.go2rtc_url`). На Jetson — **гибрид**:

| Поток | Маршрут | Зачем |
|-------|---------|-------|
| **main / high-res** | `rtsp://<go2rtc>:8554/...` | одно подключение к камере на main; ring buffer + NVENC |
| **lores / detect** | **прямой RTSP камеры** | минимальная задержка для DeepStream сторожа |

`/dev/video0` в Docker **не нужен** для RTSP.

### 4.1 Docker: `network_mode: host`

Jetson полностью отдан под Hub — **`network_mode: host` по умолчанию** (проще RTSP/RTP, без NAT).

| Режим | Когда |
|-------|-------|
| **`network_mode: host`** | **дефолт Jetson** — UI на порту хоста (`BIRDLENSE_PORT`, обычно 8085 или 8080) |
| **bridge** | только для отладки изоляции |

Профиль: `deploy/profiles/jetson-nano/compose.host-network.yml`.

### 4.2 GStreamer / DeepStream для RTSP

Параметры из ревью — принимаем, но не как жёсткие константы:

- `rtspsrc latency=200–500`; стартовое значение 300 ms
- `drop-on-latency=true` только для live detect; для high-res ring buffer включать после теста (может портить поток при jitter)
- `nvv4l2decoder enable-max-performance=1`
- `low-latency-mode=true` только если камеры не используют B-frames
- `num-extra-surfaces`: не ставить «0 всегда»; 0 снижает latency, но при сетевом jitter даёт stutter. Старт: 1–2.
- после decoder ставить `queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0`
- `appsink sync=false` для ring buffer
- DeepStream `type=4`, `latency=300`, `live-source=1`, sink `sync=0`

Пример lores (704×576):

```bash
gst-launch-1.0 rtspsrc location=rtsp://.../lores latency=300 drop-on-latency=true ! \
  rtph264depay ! h264parse ! nvv4l2decoder enable-max-performance=1 ! \
  queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! \
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

### 5.1.A Топология потоков, триггеры и подсказки

**Сеть:** `network_mode: host` — основной профиль Jetson (устройство целиком под Hub; проще RTSP/RTP, меньше NAT).

**Потоки (как на Intel, с уточнением):**

| Поток | Источник | Назначение |
|-------|----------|------------|
| **lores / detect** | **прямой RTSP камеры** | DeepStream сторож, YOLO, трекер |
| **main / high-res** | **через Go2RTC** | ring buffer, запись клипа, NVENC |

Go2RTC разгружает камеру от множества подключений к main; lores идёт напрямую — меньше задержка и проще сторож.

**Две камеры на одной локации:** `feeder_close` / `feeder_far` в `video.cameras[]` + `camera_tuning_by_role`; `multi_camera_groups` — только для подсказок fusion, не для блокировки записи.

---

#### Триггеры (старт записи) — отдельный слой

Триггеры **не опциональны** в смысле контракта: без них запись не стартует. Источники — как в Hub (`triggers.*`, ADR #634, `trigger_graph`):

| Источник | Роль | Конфиг |
|----------|------|--------|
| **opencv** | motion на lores (MOG2 / frame_diff / hybrid) | `triggers.opencv` |
| **frigate** | MQTT-событие движения/объекта | `triggers.frigate` |
| **motion_sensor** | PIR / MQTT | `triggers.motion_sensor` |
| **scales** | скачок веса кормушки | `triggers.scales` |

На Jetson по умолчанию: `recording_gate_mode: motion_immediate` — триггер **сразу** открывает main + ring buffer; YOLO/DeepStream работает **внутри** сессии (как Frigate/NVR).

**Не путать:** DeepStream probe → `TRIGGER_RECORD` — это не «подсказка», а внутренний путь сторожа после уже начатой или подтверждённой сессии; внешние MQTT-источники не подменяют этот контракт.

Анти-дребезг: `trigger_moratorium_seconds`, `min_seconds_between_recordings`, `frigate_activity_hold_seconds` (удержание клипа, не единственный старт).

---

#### Подсказки (hints) — опциональный слой

Подсказки **всегда опциональны**: если источника нет — Hub работает как раньше. **Нет иерархии приоритетов** между подсказками; они не «перебивают» друг друга и **не могут** стартовать запись (ADR [#634](adr-classifier-hints-only.md), `classifier_hints/`).

| Подсказка | Когда есть | Что делает | Чего не делает |
|-----------|------------|------------|----------------|
| **BirdNET MQTT** | аудио на площадке | FIFO 24h, prior/confidence bias для классификатора | не создаёт финальный вид, не стартует запись |
| **eBird regional** | API key + регион | снижает пороги для типичных видов региона | не фильтрует детектор жёстко |
| **Frigate label/sub_label** | MQTT в окне сессии | species prior, fusion bonus | не substitute за отсутствие YOLO anchor (кроме legacy `detect_first`) |
| **multicam group** | `multi_camera_groups` | boost confidence, hint scope между close/far | не блокирует параллельную запись второй камеры |
| **adaptive_profiles** (night/day) | по освещению | пороги, трекер, preprocess | не триггер |
| **camera_tuning_by_role** | feeder_close/far | geometry, thresholds | не триггер |
| **weather** | интеграция | enrichment, аналитика | не триггер |
| **photogrammetry / geometry** | `frame_geometry` | sanity bbox, px/m | не триггер |

Сборка: `collect_hints()` → scorer → fusion/classifier. Веса (`birdnet_prior`, `regional_prior`, …) — **взвешивание при наличии**, не ранжирование «кто главный».

**Behavior 3D-CNN** (опционально, фаза 2+): только на готовом high-res клипе охотника; метки `feeding`, `perching`, `flying_away`, …; результат в `event.enrichment.behavior`, может догонять persist.

4. **Hub persist:** существующий API/SQLite — ingest метаданных и путь к файлу (адаптер, не переписывать UI с нуля).

### 5.2 Альтернатива (фаза 2): один high-res поток на камеру в DeepStream

Primary GIE `network-width/height=704×576` на **main** stream — без рассинхрона lores/main.  
Требует больше GPU на decode; оценить на полевом тесте после MVP сторожа.

### 5.3 Что сохраняем из текущего Hub

 - `feeder_close` / `feeder_far`, `camera_tuning_by_role`, geometry contract (`frame_shape.py`)
 - Linear stages: trigger → detect_track → classify → persist (реализация стадий разная)
 - **Контракт триггеров vs подсказок** (ADR #634): Frigate/BirdNET/eBird/multicam — **только hints** для classifier/fusion; Frigate **может** быть триггером записи (`triggers.frigate`), но label/species Frigate — не замена YOLO при `motion_immediate`
 - **Модели:** trapper детектор, Birder convnext классификатор, DINOv2 ReID — те же веса, TRT-обёртка
 - OpenAPI, UI, Telegram, visit model

### 5.7 Лучшие практики из экосистемы (adopted)

- **Motion gate first** (BirdWatcher, HUMBIRDY): до 90% экономии CPU. RTSP motion уже в DeepStream, но для сторожа lores добавить `gstreamer:motioncells` или простую метрику.
- **YOLO interval + tracker fill** (NVIDIA bench): `interval=3–5`, NvDCF/NvSORT заполняет промежутки.
- **Shared backbone для classifier/ReID** (Ornimetrics): один кроп → DINOv2 → species+welfare+ReID. На Nano: ConvNeXt достаточно; DINOv2 ReID оставить deferred/lazy.
- **Fine-tune на yard data** (BirdClass-NA, Backyard watcher): 20–30 кропов/вид обязательны до деплоя. Dataset: `gfermoto/birdlense-annotations`.
- **Pre-roll buffer** (Orpheus): гарантированный pre-roll 1–2 c до события. Ring buffer реализует эту практику.
- **MegaDetector/Wildlife Insights pattern:** animal/empty filtering, uncertainty routing, HITL review. В BirdLense это не runtime-модель, а benchmark/reference gate: наши detector+trigger графы должны давать сопоставимый FN/FP профиль на golden clips.
- **Active learning:** неизвестные, low-margin и конфликтные случаи не прячем; отправляем в review queue/dataset export. Цель — уменьшать ручную разметку, не «доверять AI вслепую».
- **FAIR / Camtrap DP:** внутренний формат Hub сохраняется, но внешний экспорт должен быть совместим с Camtrap DP/Darwin Core/Audubon Core.

### 5.8 Много-modal & Power-aware распространение

**Acoustic+Visual fusion** (SPARROW, Orpheus): BirdNET-Audio может работать на отдельном SBC/ESP32-S3, результаты через MQTT/LoRaWAN присоединяться к визуальному событию. Это даёт 2-й шанс на идентификацию.

**Data standards** (GBIF, TDWG):
- **Camtrap DP** — основной формат обмена данными (особенно для GBIF)
- **Darwin Core** — транслировать в DwC-A для внешних платформ
- **Audubon Core** — метаданные медиафайлов (dc:identifier, ac:subject, dc:created)

**Human-in-the-loop** (HITL):
- Маловероятные/низкие confidence случаи → UI подтверждение → переобучение
- Ensemble benchmark: MegaDetector (animal) + BirdNET (audio) + classifier (species)
- Citizen science: MammalWeb, iNaturalist integration

**Continual learning** (SmartTrap):
- Не обучать тяжёлые модели на Nano по умолчанию. Nano собирает hard examples и metadata; training/fine-tune идёт на dev/GPU host.
- Experience replay для предотвращения catastrophic forgetting.
- Parameter-efficient fine-tune/LoRA допускается только после baseline parity и manual validation.

### 5.9 Publication / reserve-ready gates

Чтобы результат был пригоден для научного сообщества и заповедников, каждая платформа должна проходить не только smoke, но и полевой протокол:

| Gate | Минимум для принятия |
|------|----------------------|
| **Reproducibility** | версия JetPack/L4T, DeepStream, TensorRT, model hashes, config snapshot, camera firmware |
| **Golden clips** | feeder_close + feeder_far, день/ночь/IR, дождь/ветер, empty negatives, rodent/intrusion |
| **Detector quality** | recall drop TRT vs PT ≤5%, IoU ≥0.85 на matched boxes, FP empty monitored через trigger_graph |
| **Classifier quality** | top-1/top-5, entropy/margin, Unknown allowed; rare/visually similar species routed to review |
| **HITL** | все low-margin/conflict cases экспортируются в review queue и dataset crops |
| **Uncertainty** | хранить raw confidence, entropy, margin, source hints, manual label; не превращать confidence в «истину» |
| **FAIR export** | Camtrap DP + Darwin Core/Audubon Core mapping; сохранять внутренний CSV/eBird export |
| **Operational** | 24h soak: no OOM, GPU ≤85%, temp <80°C, reconnect работает, no SD writes кроме boot |
| **Ethics/privacy** | people/vehicle detections не публиковать как biodiversity records; локальные retention rules |

Научный результат строится не на «самой умной модели», а на воспроизводимом полевом протоколе: сырой клип + bbox + confidence + подсказки + manual validation + экспорт в стандартизированный формат.

### 5.4 Jetson execution contract — не повторять Intel hot path

Сохраняем модели, но меняем **когда** они вызываются:

| Стадия | Intel текущий путь | Jetson контракт |
|--------|--------------------|-----------------|
| Detector | YOLO/OpenVINO на detect frames | Trapper TRT FP16, lores only, `interval=3–5`; tracker закрывает промежутки |
| Tracker | ByteTrack в Python/Ultralytics | DeepStream NvDCF `max_perf`, tracker resolution близко к infer resolution |
| Classifier | до 3 key frames / finalize | **1 лучший кроп на событие**, convnext TRT; 2-й кроп только если confidence/margin плохие |
| ReID | finalize enrichment | DINOv2 lazy/deferred; live ReID выключен; максимум 1 embedding на visit |
| Behavior | Python эвристики | tracker metadata first; **3D-CNN только deferred/event-only**, не live hot path |
| Persist | после full finalize | video+bbox persist first; classifier/ReID могут догонять async |

Правило деградации:

1. Всегда сохраняем событие и bbox metadata.
2. Если GPU/RAM high → classifier skipped/deferred.
3. Если RAM high → ReID off.
4. Если latency high → `interval += 1`, затем `imgsz 704→640`.
5. Если deferred queue растёт → отключить Behavior 3D-CNN первым, потом ReID.
6. Если event quality низкая → не меняем модель сразу; сначала проверяем RTSP, tracker, threshold parity.

### 5.5 Модели: сохранить, но добавить parity gates

`trapper`, `convnext_v2_tiny_eu-common256px`, DINOv2 остаются каноническими моделями продукта. Для Jetson вводим gates:

- **Detector parity:** `.pt` vs `.engine` на 20–50 клипах; IoU bbox ≥0.85, drop in recall ≤5%.
- **Classifier parity:** Top-1/Top-5 и margin на экспортированных кропах; exotic labels regression fail.
- **ReID parity:** cosine distance distribution на тех же crops; если DINOv2 TRT тяжёлый — оставить torch+cuda/deferred, не заменять на OSNet без A/B.
- **Golden clips:** отдельные `feeder_close` и `feeder_far`; night/IR clips обязательны.

### 5.6 Tracker choice: NvDCF сначала, IOU fallback

NvDCF точнее, но может съесть FPS на Nano. План:

1. Start: NvDCF `max_perf`, reduced tracker resolution (`704×576` или меньше, кратно 32), HOG off если bottleneck.
2. Если FPS/thermal плохие — IOU tracker fallback (меньше качество, меньше память).
3. `maxTargetsPerStream=10–15`, past-frame history ограничить.
4. В Hub сохранять `track_provider=deepstream_nvdcf|deepstream_iou|bytetrack`.

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
- [ ] 24h soak: нет OOM/throttle, reconnect сработал хотя бы в dry-run
- [ ] Golden clips: day/night/IR, close/far, empty negatives, rodent/intrusion
- [ ] Сохранены model hashes + config snapshot + JetPack/L4T/DeepStream versions
- [ ] Low-confidence/conflict cases попали в review/dataset export
- [ ] Проверен экспорт: текущий CSV/eBird + планируемый Camtrap DP/Darwin Core mapping

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
- Performance budget / graceful degradation: [#656](https://github.com/Gfermoto/BirdLense-Hub/issues/656) (E10)

## 10. Внешние источники

- NVIDIA DeepStream troubleshooting: RTSP `live-source=1`, sink `sync=0`, latency/jitter trade-offs, decoder buffer starvation — <https://docs.nvidia.com/metropolis/deepstream/6.2/dev-guide/text/DS_troubleshooting.html>
- NVIDIA DeepStream performance: Jetson Nano uses FP16, `interval=5`, NvDCF `max_perf`, reduced tracker resolution — <https://docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Performance.html>
- RidgeRun Jetson GStreamer encoder latency: `nvv4l2h264enc` / `nvv4l2h265enc`, `maxperf-enable` impact — <https://developer.ridgerun.com/wiki/index.php/GStreamer_Encoding_Latency_in_NVIDIA_Jetson_Platforms>
- NVIDIA forum notes: `low-latency-mode` and `num-extra-surfaces=0` reduce latency but can stutter with jitter/B-frames — <https://forums.developer.nvidia.com/t/deepstream-performance-issue-1s-latency-and-periodic-stutter-with-rtsp-streams/342100/17>
