# Jetson Nano B01 — аппаратная и программная настройка под BirdLense Hub

**Статус:** Final review plan + external review (2026-06-17)  
**Исполнять:** раздел **2** (шаги 1–21), сверху вниз. Разделы 3–6 — справочник.  
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

## 2. Runbook — выполнять строго по порядку

Один путь. Не перескакивать шаги. Каждый шаг: **где**, **что сделать**, **команды**, **готово когда**.

| Шаг | Где | Суть |
|-----|-----|------|
| 1–2 | стол / ПК | железо, образ на SD |
| 3–8 | Jetson | boot, SSD, extlinux guard |
| 9–12 | Jetson | Docker, MAXN, runtime check |
| 13–16 | Jetson + dev | env, build, TRT, **benchmark** |
| 17–18 | Jetson / UI | камеры, RTSP + buffer tune |
| 19–21 | dev → Jetson | deploy, smoke, **recovery test** |

---

### Шаг 1. Подготовить железо

**Где:** стол, Jetson **выключен**.

**Что сделать:**

1. Подключить БП **5 В / 4 А (20 Вт)** через barrel jack 5.5×2.1 мм (не micro-USB).
2. Установить радиатор и **активный** вентилятор.
3. Подключить **USB 3.0 SSD** (или NVMe через HAT). Диск пока не трогать — только физическое подключение.

**Готово когда:** питание, охлаждение и SSD подключены; Jetson ещё не включали.

---

### Шаг 2. Записать JetPack на microSD

**Где:** ПК, Jetson **выключен**.

**Что сделать:**

1. Скачать [JetPack 4.6.1 SD Card Image](https://developer.nvidia.com/embedded/jetpack-sdk-461) → `jetson-nano-sd-r32.7.1.img.zip`.
2. Записать образ на microSD (≥16 ГБ, A2/V30): `balenaEtcher` или `dd`.
3. Вставить SD в Jetson.

**Готово когда:** SD записана и вставлена.

---

### Шаг 3. Первый boot и SSH

**Где:** Jetson, первый запуск с SD.

**Что сделать:**

1. Включить Jetson, пройти OEM wizard:
   - пользователь: `gfer`
   - hostname: `birdlense-jetson`
2. Включить SSH:

```bash
sudo systemctl enable ssh --now
```

**Готово когда:** вход по SSH с dev-машины работает: `ssh gfer@birdlense-jetson`.

---

### Шаг 4. Обновить JetPack до 4.6.x

**Где:** Jetson по SSH.

**Что сделать:**

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y nvidia-jetpack
cat /etc/nv_tegra_release
```

**Готово когда:** `cat /etc/nv_tegra_release` показывает `R32.7.x`. Зафиксировать точную версию в deployment notes.

---

### Шаг 5. Разметить SSD

**Где:** Jetson по SSH.

**Что сделать:**

```bash
lsblk
# USB SSD обычно /dev/sda, NVMe — /dev/nvme0n1
# Ниже пример для /dev/sda — подставь свой диск!

sudo parted /dev/sda mklabel gpt
sudo parted /dev/sda mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L birdlense-data /dev/sda1
```

**Готово когда:** `lsblk` показывает `/dev/sda1` с типом ext4.

---

### Шаг 6. Перенести rootfs на SSD

**Где:** Jetson по SSH.

**Что сделать:**

```bash
sudo mkdir -p /mnt/ssd
sudo mount /dev/sda1 /mnt/ssd

sudo rsync -aAXv \
  --exclude={"/mnt/*","/proc/*","/sys/*","/dev/*","/run/*","/tmp/*","/lost+found"} \
  / /mnt/ssd/

SSD_UUID=$(blkid -s UUID -o value /dev/sda1)
SSD_PARTUUID=$(blkid -s PARTUUID -o value /dev/sda1)

echo "UUID=${SSD_UUID}  /  ext4  defaults,noatime  0  1" | sudo tee -a /mnt/ssd/etc/fstab

sudo cp /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.bak
sudo sed -i "s|root=[^ ]*|root=PARTUUID=${SSD_PARTUUID}|" /boot/extlinux/extlinux.conf

sudo reboot
```

**Готово когда:** после reboot команда `df -h /` показывает SSD (`/dev/sda1` или `nvme0n1p1`), не `mmcblk0`.

---

### Шаг 7. Проверить загрузку с SSD

**Где:** Jetson после reboot.

**Что сделать:**

```bash
df -h /
lsblk
```

**Готово когда:**

- `/` на SSD
- `mmcblk0` — только `/boot` (загрузчик), не корневая ФС

---

### Шаг 8. Защитить загрузку с SSD после apt upgrade

**Где:** Jetson.

**Проблема:** `sudo apt full-upgrade` может перезаписать `/boot/extlinux/extlinux.conf` и сбросить `root=PARTUUID=...` обратно на SD.

**Что сделать:**

```bash
SSD_PARTUUID=$(blkid -s PARTUUID -o value /dev/sda1)   # или nvme0n1p1

sudo tee /usr/local/sbin/birdlense-fix-extlinux.sh >/dev/null <<SCRIPT
#!/bin/bash
set -euo pipefail
CONF=/boot/extlinux/extlinux.conf
PARTUUID="${SSD_PARTUUID}"
grep -q "root=PARTUUID=\${PARTUUID}" "\$CONF" || \
  sed -i "s|root=[^ ]*|root=PARTUUID=\${PARTUUID}|" "\$CONF"
SCRIPT
sudo chmod +x /usr/local/sbin/birdlense-fix-extlinux.sh

sudo tee /etc/apt/apt.conf.d/99-birdlense-extlinux >/dev/null <<'EOF'
DPkg::Post-Invoke { "/usr/local/sbin/birdlense-fix-extlinux.sh"; };
EOF

sudo /usr/local/sbin/birdlense-fix-extlinux.sh
grep root= /boot/extlinux/extlinux.conf
```

**Готово когда:** `grep root=` показывает `PARTUUID` SSD; скрипт в `DPkg::Post-Invoke` на месте.

---

### Шаг 9. Настроить Docker с NVIDIA runtime

**Где:** Jetson.

**Что сделать:**

```bash
sudo usermod -aG docker "$USER"
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
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

Перелогиниться (или `newgrp docker`), чтобы группа `docker` применилась.

**Готово когда:** `docker ps` работает без `sudo`.

---

### Шаг 10. Включить MAXN

**Где:** Jetson.

**Что сделать:**

```bash
sudo tee /etc/systemd/system/jetson-performance.service >/dev/null <<'EOF'
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
sudo nvpmodel -m 0
sudo jetson_clocks
```

**Готово когда:** `jtop` (после `sudo apt install -y jetson-stats`) показывает GPU ~921 MHz, CPU ~1479 MHz, temp <80°C в idle.

---

### Шаг 11. ZRAM и headless

**Где:** Jetson.

**Что сделать:**

```bash
sudo apt update
sudo apt install -y zram-config
sudo systemctl enable zram-config
sudo systemctl set-default multi-user.target
```

**Готово когда:** `systemctl is-enabled zram-config` → `enabled`; default target → `multi-user`.

---

### Шаг 12. Проверить NVIDIA runtime, GStreamer и путь интеграции

**Где:** Jetson.

**Что сделать:**

```bash
docker run --rm --runtime nvidia nvcr.io/nvidia/l4t-base:r32.7.1 \
  bash -lc 'ls /usr/local/cuda && echo OK'

# На хосте JetPack (или внутри будущего DeepStream-образа — шаг 14):
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc
gst-inspect-1.0 nvinfer      # DeepStream Primary GIE — обязателен для Plan A
gst-inspect-1.0 nvtracker    # NvDCF / IOU tracker
```

**Версия DeepStream:** для JetPack **4.6.x (R32.7.x)** — **DeepStream 6.2** (`nvcr.io/nvidia/deepstream-l4t:6.2-*-r32.7.1`). Элементы `nvinfer` / `nvtracker` **не** входят в `l4t-base` и **не** в текущий `Dockerfile.jetson` (`python:3.11-bookworm`) — только в DeepStream SDK или образ `deepstream-l4t`.

**Готово когда:** Docker выводит `OK`; `nvv4l2*` на хосте; для Plan A — `nvinfer` и `nvtracker` находятся (хост или контейнер из шага 14). Если `nvinfer` нет — до шага 20 поставить DeepStream 6.2 или зафиксировать **Plan B** в deployment notes.

**Путь интеграции (главный риск E1–E3):**

| Путь | Когда | Запас времени |
|------|-------|---------------|
| **A — DeepStream Primary GIE + probe** | целевой MVP | базовая оценка × **2–3** на отладку Python↔DS |
| **B — GStreamer `appsink` + TRT в Python** | если A нестабилен >1 недели | медленнее, проще отладка |

Plan B: `rtspsrc ! nvv4l2decoder ! nvvidconv ! video/x-raw(memory:NVMM) ! appsink` → Ultralytics/TRT в Python. Не блокировать деплой ожиданием идеального DeepStream.

**NVDEC:** при двух камерах мониторить decode load:

```bash
tegrastats --interval 1000 | head -20   # смотреть NVDEC % / GR3D %
```

Если NVDEC >90% sustained — снизить FPS substream или перейти на event-only high-res decode.

---

### Шаг 13. Задать переменные окружения

**Где:** dev-машина (`scripts/deploy.local.sh`) и при необходимости `app/.env` на Jetson.

**Что сделать:**

```bash
# scripts/deploy.local.sh
export BIRDLENSE_PLATFORM=jetson_nano
export DEPLOY_HOST="gfer@192.168.8.199"
export DEPLOY_URL="http://192.168.8.199:8085"
```

В `app/.env` на Jetson (если нужно локально):

```bash
BIRDLENSE_PLATFORM=jetson_nano
BIRDLENSE_INFERENCE_BACKEND=tensorrt
BIRDLENSE_OPENVINO_BINARY_ENABLED=0
BIRDLENSE_INFERENCE_DEVICE=cuda
# GO2RTC_URL=http://<lan-ip-go2rtc>:1984  — LAN площадки, не копировать с VPS
```

Overlay: `deploy/profiles/jetson-nano/config.overlay.yaml`.

**Готово когда:** `echo $BIRDLENSE_PLATFORM` на dev → `jetson_nano`; `DEPLOY_HOST`/`DEPLOY_URL` указывают на Jetson в LAN.

---

### Шаг 14. Базовая сборка контейнера на Jetson

**Где:** Jetson, каталог `app/` репозитория.

**Базовый образ (Plan A — DeepStream):** `docker-compose.jetson.yml` / `Dockerfile.jetson` должны собираться из образа **с DeepStream SDK**, не из «голого» Debian:

| Путь | Базовый образ | Когда |
|------|---------------|-------|
| **Plan A (целевой)** | `nvcr.io/nvidia/deepstream-l4t:6.2-base-r32.7.1` (или `-devel` на этапе сборки TRT) | Primary GIE + `nvinfer` + NvDCF |
| **Plan B (fallback)** | `nvcr.io/nvidia/l4t-base:r32.7.1` + `nvidia-l4t-jetson-multimedia-api` | GStreamer NVDEC/NVENC + TRT в Python, без `nvinfer` |

> **Сейчас в репо:** `Dockerfile.jetson` = `python:3.11-bookworm` (заглушка для smoke UI/API). Перед E2 (#648) — смена базы на `deepstream-l4t:6.2-*` под R32.7.x.

**Что сделать:**

```bash
cd app
BIRDLENSE_PLATFORM=jetson_nano \
  docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d --build
```

Проверить в `docker-compose.jetson.yml` и образе:

- `restart: unless-stopped` — автоподъём после reboot/power glitch.
- `network_mode: host` — UI на **порту хоста** (`BIRDLENSE_PORT`, по умолчанию **8085**); не искать порт в `ports:` bridge.
- Внутри контейнера (после смены базы): `gst-inspect-1.0 nvinfer` → OK для Plan A.

```bash
grep -E 'restart:|network_mode:' docker-compose.jetson.yml
docker compose exec birdlense gst-inspect-1.0 nvinfer 2>/dev/null || echo "Plan B или образ ещё без DeepStream"
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/health"
```

**Готово когда:** `birdlense` `running`; health OK; для Plan A — образ на базе `deepstream-l4t:6.2` и `nvinfer` в контейнере.

---

### Шаг 15. Конвертировать веса в TensorRT на этом Jetson

**Где:** Jetson (engine несовместим, если собран на другом устройстве).

**Что сделать:**

```bash
# После реализации scripts/convert_to_trt.sh:
./scripts/convert_to_trt.sh \
  --detector processor/models/detection/weights/trapper_ai_v02_2024.pt --imgsz 704,576 \
  --classifier processor/models/classification/weights/convnext_v2_tiny_eu-common256px.pt --imgsz 256
```

Скрипт должен:

1. Собрать `.engine` FP16; **кэшировать** по hash весов + JetPack/L4T (не пересобирать при каждом deploy).
2. Прогнать parity на 20–50 golden clips.
3. Упасть, если recall drop >5% или IoU <0.85.
4. Записать hashes в `weights/trt_manifest.json`.

OpenVINO IR на Jetson **не использовать**. Модели: trapper, convnext — обязательны; **DINOv2 ReID — experimental (фаза 2)**.

Проверка DINOv2 до включения в hot path:

```bash
# OOM на Nano 4 ГБ — типичный fail; при ошибке — ReID из ConvNeXt backbone или defer
trtexec --onnx=dinov2_vits14.onnx --fp16 --workspace=512 --saveEngine=/tmp/dino_test.engine
```

**Готово когда:** `.hef` (Hailo) или `.engine` (TensorRT) для **EfficientNetV2-S** (region EU/NA) лежат на Jetson; parity gate (species + welfare + ReID) зелёный.

**Region switch (EU ↔ NA):**  
- При старте `processor` читает координаты (`config.yaml` / env) → определяет регион (`region_by_coords`).  
- Выбирает соответствующий `.hef` (например, `species_classifier_inat.hef` для EU, `species_classifier_nabirds.hef` для NA).  
- **BirdNET** (аудио) остаётся без изменений — подсказки через MQTT.

---

### Шаг 16. Benchmark на Jetson (gate перед камерами/deploy)

**Где:** Jetson, тот же образ и `.engine`, что в шаге 15.

**Что сделать:**

```bash
# Реализация: scripts/benchmark_jetson.py (#650 / #657) — пока заглушка в плане
python scripts/benchmark_jetson.py \
  --detector-engine processor/models/detection/weights/trapper.engine \
  --classifier-engine processor/models/classification/weights/convnext.engine \
  --frames 1000 --lores 704,576 --interval 4
```

**Контракт скрипта (реализация, не блокер плана):**

1. Загрузить `.engine` detector + classifier на **этом** Jetson.
2. Прогнать **N кадров** (предпочтительно кропы/кадры из golden clips, не синтетика).
3. Детектор: FPS sustained с учётом `interval`; **p95 latency** на inference.
4. Классификатор: **p95 <100 ms** на один кроп.
5. Проверить RAM контейнера (`docker stats`) — не выше лимита compose (`mem_limit: 3g`) в idle после прогона.
6. Записать CSV `jetson_bench_YYYYMMDD.csv` (latency, FPS, RAM, interval).

**Пороги (не деплоить, если не выполнены):**

| Метрика | Минимум |
|---------|---------|
| Детектор на lores | **>10 FPS** sustained (с `interval=3–4`) |
| Классификатор (species) на 1 кроп | **<100 ms** p95 |
| **Welfare (Mahalanobis)** | <50 ms p95 на кроп |
| **ReID (ArcFace)** | <50 ms p95 на кроп |
| RAM container idle | зафиксировать baseline (цель <2.5 ГБ до live) |

Лог: CSV `jetson_bench_YYYYMMDD.csv` (latency, FPS, queue depth) — для сравнения после тюнинга.

**Готово когда:** benchmark зелёный; цифры записаны в deployment notes.

---

### Шаг 17. Настроить камеры в Hub

**Где:** `app/app_config/user_config.yaml` (на Jetson или через deploy).

**Что сделать:**

1. Две камеры: `feeder_close`, `feeder_far` в `video.cameras[]`.
2. Для каждой камеры:
   - **lores/detect** — прямой RTSP URL камеры (substream 704×576, H.264, 7–15 FPS).
   - **main/high-res** — через go2rtc (`rtsp://<go2rtc>:8554/...`), 1080p, 15–25 FPS.
3. Включить NTP на камерах; GOP 2–4 с.

**Готово когда:** в конфиге есть реальные URL обоих потоков для обеих камер; роли `tuning_role` заданы.

---

### Шаг 18. Проверить RTSP-потоки (NVMM + buffer tuning)

**Где:** Jetson.

**Что сделать:**

```bash
# lores — zero-copy NVMM (как в боевом pipeline)
gst-launch-1.0 rtspsrc location=rtsp://CAMERA_IP/lores latency=300 drop-on-latency=true ! \
  rtph264depay ! h264parse ! \
  nvv4l2decoder enable-max-performance=1 num-extra-surfaces=2 ! \
  queue leaky=downstream max-size-buffers=2 ! \
  nvvidconv ! video/x-raw(memory:NVMM),format=NV12,width=704,height=576 ! \
  fakesink sync=false

# main через go2rtc
gst-launch-1.0 rtspsrc location=rtsp://GO2RTC_IP:8554/feeder_close latency=300 ! \
  rtph264depay ! h264parse ! nvv4l2decoder num-extra-surfaces=2 ! fakesink sync=false
```

Подставить реальные URL из шага 17.

**Buffer check:** прогнать каждый lores URL **≥5 минут**. Искать артефакты: зелёные блоки, застывание кадра, рост latency. При stutter — `num-extra-surfaces=3`; при избытке latency — `=1` (только после A/B на поле).

**Готово когда:** оба pipeline без «Could not open resource»; нет визуальных артефактов на реальных камерах ≥5 мин.

---

### Шаг 19. Финальный deploy

**Где:** dev-машина.

**Что сделать:**

```bash
cd /path/to/BirdLense
# deploy.local.sh уже с BIRDLENSE_PLATFORM=jetson_nano (шаг 13)
make deploy
```

**Готово когда:** `make deploy` без ошибки; health на `DEPLOY_URL` → OK.

---

### Шаг 20. Smoke после deploy

**Где:** Jetson + браузер/MCP.

**Что сделать:**

1. Открыть `DEPLOY_URL` — UI доступен.
2. Дождаться события или вызвать тестовую запись.
3. Проверить метрики:

```bash
tegrastats --interval 1000 | head -30
# в Hub: yolo_frames_with_tracks > 0
# recording_session_summary: persist OK
```

4. Зафиксировать idle RAM/GPU 5 мин после старта (baseline для E10).

**Готово когда:** health OK; одна запись с persist в UI; `tegrastats` без throttle/OOM; треки появляются.

---

### Шаг 21. Recovery test (обрыв сети)

**Где:** Jetson, live stack после шага 20.

**Что сделать:**

1. Симулировать обрыв RTSP: отключить PoE/порт камеры или `iptables` drop на IP камеры **30–60 с**.
2. Восстановить сеть.
3. Убедиться: реконнект без `docker restart birdlense`; в логах — backoff reconnect; через ≤2 мин снова кадры/треки.
4. В Hub: **`yolo_frames_with_tracks > 0`** в `recording_session_summary` (или эквивалентная метрика live detect) — как в чек-листе §7.

```bash
# пример блокировки (подставить IP камеры)
sudo iptables -A OUTPUT -d CAMERA_IP -j DROP
sleep 45
sudo iptables -D OUTPUT -d CAMERA_IP -j DROP
docker logs birdlense --tail 50 | grep -iE 'rtsp|reconnect|error'
# после восстановления — дождаться события или проверить summary в UI/API
```

Опционально для поля: API **экстренного сброса буферов** GStreamer (`POST /api/.../media/reset-buffers`) — backlog E11.

**Готово когда:** после обрыва поток восстановился автоматически; контейнер не перезапускали; **`yolo_frames_with_tracks > 0`** снова зафиксирован.

---

## 3. Справочник: целевой стек

| Слой | Технология | Статус в репо |
|------|------------|---------------|
| Hub UI/API | Flask + nginx в контейнере | `Dockerfile.jetson` (bookworm → deepstream-l4t:6.2) |
| Live detect/track | **YOLOv11n (Hailo `.hef`)** или DeepStream GIE fallback | #648 / E2 |
| Inference weights | **EfficientNetV2-S (ONNX → Hailo `.hef`)**, region-switch EU/NA | #650 / E4 |
| **Welfare (здоровье)** | Mahalanobis anomaly (EfficientNetV2-S features) | #650 / E4 |
| **ReID (индивид)** | ArcFace 256-d embedding (EfficientNetV2-S backbone) | #650 / E4 |
| Live decode lores | NVDEC / DeepStream или GStreamer NVMM | planned |
| High-res capture | Ring buffer + event trigger | новый модуль |
| Record encode | NVENC (`nvv4l2h264enc`) | planned |
| Classifier / ReID / Welfare | **Shared backbone EfficientNetV2-S** (species + welfare + ReID) | #650 |
| Offline regen | `track_regenerator` на `.pt`/`.engine` | общий код |

---

## 4. Справочник: камеры (детали к шагам 17–18)

| Поток | Назначение | Разрешение | FPS | Маршрут |
|-------|------------|------------|-----|---------|
| Substream / detect | DeepStream сторож | 704×576 | 7–15 | **прямой RTSP камеры** |
| Main | ring buffer + запись | 1080p | 15–25 | **через go2rtc** |

- Оба **H.264**, GOP 2–4 с, NTP на камере.
- `video.cameras[]`: `tuning_role: feeder_close|feeder_far`.

Исполнять: **шаг 17** (конфиг) → **шаг 18** (проверка gst-launch + buffer tune).

---

## 5. RTSP и сеть (замечания ревью, адаптировано под BirdLense)

### 5.1 Источник потоков: go2rtc vs прямой RTSP

На площадке Hub уже использует **go2rtc** (`video.go2rtc_url`). На Jetson — **гибрид**:

| Поток | Маршрут | Зачем |
|-------|---------|-------|
| **main / high-res** | `rtsp://<go2rtc>:8554/...` | одно подключение к камере на main; ring buffer + NVENC |
| **lores / detect** | **прямой RTSP камеры** | минимальная задержка для DeepStream сторожа |

`/dev/video0` в Docker **не нужен** для RTSP.

### 5.2 Docker: `network_mode: host`

Jetson полностью отдан под Hub — **`network_mode: host` по умолчанию** (проще RTSP/RTP, без NAT).

| Режим | Когда |
|-------|-------|
| **`network_mode: host`** | **дефолт Jetson** — UI на порту хоста (`BIRDLENSE_PORT`, обычно 8085 или 8080) |
| **bridge** | только для отладки изоляции |

Профиль: `deploy/profiles/jetson-nano/compose.host-network.yml`.

### 5.3 GStreamer / DeepStream для RTSP

Параметры из ревью — принимаем, но не как жёсткие константы:

- `rtspsrc latency=200–500`; стартовое значение 300 ms
- `drop-on-latency=true` только для live detect; для high-res ring buffer включать после теста (может портить поток при jitter)
- `nvv4l2decoder enable-max-performance=1`
- `low-latency-mode=true` только если камеры не используют B-frames
- `num-extra-surfaces`: не ставить «0 всегда»; 0 снижает latency, но при сетевом jitter даёт stutter. Старт: 1–2.
- после decoder ставить `queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0`
- `appsink sync=false` для ring buffer
- DeepStream `type=4`, `latency=300`, `live-source=1`, sink `sync=0`

Пример lores (704×576) — tuned для Nano (zero-copy, leaky, минимальный jitter):

```bash
gst-launch-1.0 rtspsrc location=rtsp://.../lores latency=300 drop-on-latency=true ! \
  rtph264depay ! h264parse ! \
  nvv4l2decoder enable-max-performance=1 num-extra-surfaces=2 ! \
  queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! \
  nvvidconv ! video/x-raw(memory:NVMM),format=NV12,width=704,height=576 ! \
  appsink name=lores_sink sync=false emit-signals=true
```

Ключевые улучшения:

- `num-extra-surfaces=2` (не 0) — баланс latency vs stutter при jitter.
- `video/x-raw(memory:NVMM)` — zero-copy в nvvidconv / downstream.
- `leaky=downstream` + малые буферы — защита от backlog при перегрузе.
- Для high-res ring buffer: `drop-on-latency=false`, больший pre-roll буфер, `sync=false`.

Эти параметры интегрировать в `go2rtc_stream_source.py` / DeepStream pipeline builder.

### 5.4 Синхронизация lores ↔ high-res

Не frame-index, а **timestamp/PTS**: ring buffer `get_frame_at(lores_timestamp)` с допуском ≤200–500 ms (см. ревью `RingBufferSync`).

### 5.5 RTSP reconnect и мониторинг (этап E9)

- Exponential backoff реконнект при обрыве (`max_retries`, base delay 1s).
- Health: `gst-discoverer-1.0` или probe «кадр за N сек» каждые 60s.
- 3 fail подряд → алерт (Telegram / Hub activity log).

Задача: GitHub **#655** (E9), связана с E1/E7.

---

## 6. Архитектура пайплайна (рекомендуемая)

Консультанты предлагали чистый DeepStream на 4 потока — **для Nano 4 ГБ это рискованно**. Согласовано с BirdLense:

### 6.1 «Сторож + охотник» (гибрид)

1. **Сторож (DeepStream):** только **2 потока lores** (по одному на камеру).  
   YOLO TensorRT FP16, `interval=3–4` (~7 FPS effective), NvDCF каждый кадр.  
   Probe → событие `TRIGGER_RECORD(camera_id, track_id, bbox, ts)`.

2. **Кольцевой буфер high-res:** лёгкий GStreamer `uridecodebin ! nvvidconv ! appsink` на main stream;  
   `deque` последних 60–90 кадров (~2–3 с). **Не** пишем на диск до триггера.

3. **Охотник (Python):** по триггеру — pre-roll из deque + post-roll 8–10 с → **NVENC** → mp4 на SSD.  
   Один репрезентативный кроп → **тот же** Birder convnext + DINOv2 ReID (TRT/torch), не замена моделей.

4. **Hub persist:** существующий API/SQLite — ingest метаданных и путь к файлу (адаптер, не переписывать UI с нуля).

### 6.2 Топология потоков, триггеры и подсказки

**Сеть:** `network_mode: host` — основной профиль Jetson (устройство целиком под Hub; проще RTSP/RTP, меньше NAT).

**Потоки (как на Intel, с уточнением):**

| Поток | Источник | Назначение |
|-------|----------|------------|
| **lores / detect** | **прямой RTSP камеры** | DeepStream сторож, YOLO, трекер |
| **main / high-res** | **через Go2RTC** | ring buffer, запись клипа, NVENC |

Go2RTC разгружает камеру от множества подключений к main; lores идёт напрямую — меньше задержка и проще сторож.

**Две камеры на одной локации:** `feeder_close` / `feeder_far` в `video.cameras[]` + `camera_tuning_by_role`; `multi_camera_groups` — только для подсказок fusion, не для блокировки записи.

#### 6.2.1 Триггеры (старт записи)

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

#### 6.2.2 Подсказки (hints)

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

### 6.3 Альтернатива (фаза 2): один high-res поток на камеру в DeepStream

Primary GIE `network-width/height=704×576` на **main** stream — без рассинхрона lores/main.  
Требует больше GPU на decode; оценить на полевом тесте после MVP сторожа.

### 6.4 Что сохраняем из текущего Hub

- `feeder_close` / `feeder_far`, `camera_tuning_by_role`, geometry contract (`frame_shape.py`)
- Linear stages: trigger → detect_track → classify → persist (реализация стадий разная)
- **Контракт триггеров vs подсказок** (ADR #634): Frigate/BirdNET/eBird/multicam — **только hints** для classifier/fusion; Frigate **может** быть триггером записи (`triggers.frigate`), но label/species Frigate — не замена YOLO при `motion_immediate`
- **Модели:** trapper детектор, Birder convnext классификатор, DINOv2 ReID — те же веса, TRT-обёртка
- OpenAPI, UI, Telegram, visit model

### 6.5 Jetson execution contract — не повторять Intel hot path

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

### 6.6 Модели: сохранить, но добавить parity gates

`trapper`, `convnext_v2_tiny_eu-common256px`, DINOv2 остаются каноническими моделями продукта. Для Jetson вводим gates:

- **Detector parity:** `.pt` vs `.engine` на 20–50 клипах; IoU bbox ≥0.85, drop in recall ≤5%.
- **Classifier parity:** Top-1/Top-5 и margin на экспортированных кропах; exotic labels regression fail.
- **ReID parity:** cosine distance distribution на тех же crops; если DINOv2 TRT тяжёлый — оставить torch+cuda/deferred, не заменять на OSNet без A/B.
- **Golden clips:** отдельные `feeder_close` и `feeder_far`; night/IR clips обязательны.

### 6.7 Tracker choice: NvDCF сначала, IOU fallback

NvDCF (DeepStream) даёт лучшее качество треков на Nano при правильной настройке, но требует explicit tuning:

1. **NvDCF primary (max quality):** `tracker-width/height` = infer resolution (704×576 или 640×640), `useColorSimilarity=0`, `featureImgSizeLevel=1` (минимальный HOG/цвет), `maxTargetsPerStream=12`, `past-frame=0` (экономия памяти).
2. **Fallback:** при sustained GPU>80% или temp>75°C → `deepstream_iou` (простой, низкое потребление).
3. Конфиг хранится в `nvtracker` element properties или отдельном `config_tracker.yml` (подключается через DeepStream pipeline builder).
4. В Hub: `track_provider` + метрики `track_fragmentation`, `track_lifetime` для A/B.

Tracker — вторая по важности точка после детектора; его деградация сразу бьёт по visit quality.

### 6.8 Лучшие практики из экосистемы (adopted)

- **Motion gate first** (BirdWatcher, HUMBIRDY): до 90% экономии CPU. RTSP motion уже в DeepStream, но для сторожа lores добавить `gstreamer:motioncells` или простую метрику.
- **YOLO interval + tracker fill** (NVIDIA bench): `interval=3–5`, NvDCF/NvSORT заполняет промежутки.
- **Shared backbone для classifier/ReID** (Ornimetrics): один кроп → DINOv2 → species+welfare+ReID. На Nano: ConvNeXt достаточно; DINOv2 ReID оставить deferred/lazy.
- **Fine-tune на yard data** (BirdClass-NA, Backyard watcher): 20–30 кропов/вид обязательны до деплоя. Dataset: `gfermoto/birdlense-annotations`.
- **Pre-roll buffer** (Orpheus): гарантированный pre-roll 1–2 c до события. Ring buffer реализует эту практику.
- **MegaDetector/Wildlife Insights pattern:** animal/empty filtering, uncertainty routing, HITL review. В BirdLense это не runtime-модель, а benchmark/reference gate: наши detector+trigger графы должны давать сопоставимый FN/FP профиль на golden clips.
- **Active learning:** неизвестные, low-margin и конфликтные случаи не прячем; отправляем в review queue/dataset export. Цель — уменьшать ручную разметку, не «доверять AI вслепую».
- **FAIR / Camtrap DP:** внутренний формат Hub сохраняется, но внешний экспорт должен быть совместим с Camtrap DP/Darwin Core/Audubon Core.

### 6.9 Много-modal и power-aware распространение

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

### 6.10 Publication / reserve-ready gates

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

### 6.11 Runtime monitoring, budget enforcement и auto-throttle (E10+)

Nano 4 ГБ нельзя вести как «маленький сервер». Для него нужен runtime budget, который enforced кодом.

| Ресурс | Бюджет MVP | Если вышли за бюджет |
|--------|------------|----------------------|
| RAM container | ≤3.0 ГБ sustained, без OOM | уменьшить ring buffer, отключить ReID live, classifier keyframes=1 |
| GPU | ≤80–85% sustained | поднять `interval`, снизить detector input до 640, отключить secondary live |
| CPU | ≤250% sustained (из 4 cores) | убрать OpenCV hot path, только GStreamer/DS metadata |
| Температура | <75–80°C | fan/jetson_clocks policy, снизить FPS/interval |
| Latency event | pre-roll 2–3 c + post-roll 8–10 c | сохранять клип даже без classifier/ReID, enrich позже |

**Правило:** если ML-обогащение не укладывается, сохраняем видео + bbox metadata, а classification/ReID переносим в deferred job. Потеря вида лучше, чем потеря события.

- `tegrastats --interval 1000 --format json` → парсить GPU util, RAM, temp, power, **NVDEC load** (две камеры).
- Простой Python-probe в DeepStream appsink / `processor` watchdog: если sustained GPU >85% или RAM container >2.8 ГБ → поднять `interval`, снизить `imgsz`, отключить secondary GIE (classifier).
- **Адаптивный `interval`:** при GPU >80% sustained автоматически `interval += 1` (до max 6); при GPU <50% — `interval -= 1`. Backlog E10.
- **CSV-лог** latency/FPS/очередей (`jetson_perf_YYYYMMDD.csv`) — для полевого сравнения и регрессий.
- Alert при throttle (temp >78°C) или OOM risk → Telegram + log; graceful: classifier off → ReID off → Behavior deferred.
- Интеграция: `scripts/jetson_monitor.py` (или в `media_runtime`) + systemd timer; экспорт метрик в Hub `/metrics` или MQTT.

Это усиливает E10 graceful degradation — не только «если вышли», а «предотвращать выход».

### 6.12 Критический review предложенных оптимизаций (итог)

Предыдущие предложения (Yocto, single-engine bundle, hybrid split containers, self-update) оценены заново:

- **Yocto** — мощный, но избыточен для MVP; отложен (см. 6.13).
- **Single .engine bundle + INT8** — риск качества (калибровка) и сложности (разные input sizes); оставляем separate FP16 engines + parity gate.
- **Split containers (DeepStream + Python trim)** — лишний IPC overhead; сохраняем single-container hybrid.
- **Self-update engines** — nice-to-have, но security surface; defer.
- **Усилено:** GStreamer pipeline tuning (zero-copy NVMM, leaky, num-extra-surfaces), NvDCF explicit config, runtime tegrastats enforcement, model conversion parity gate, **benchmark gate (шаг 16)**, **recovery test (шаг 21)**.
- **INT8** — только с калибровкой на полевых кропах; до parity FP16 не включать.

Итог: план заточен под 4 ГБ Nano — максимум hardware acceleration при жёстком контроле ресурсов и качества. Нет «магии», только проверенные практики + enforced degradation.

### 6.13 Yocto / custom minimal image — optional advanced (отложено)

Yocto даёт минимальный rootfs и контроль над kernel/device-tree, но:

- Высокая сложность поддержки (meta-jetson, L4T layers).
- JetPack 4.6.x + headless + ZRAM + Docker data-root на SSD уже даёт достаточный запас RAM/износ для MVP.
- **Решение:** Yocto рассматривать в E15+ только если после 24h soak на JetPack останутся проблемы с памятью/стабильностью или потребуется production-grade tamper-proof image.

Приоритет: сначала довести JetPack baseline до production quality, потом минимализм.

### 6.14 Внешняя рецензия (2026-06) — принятые риски и митигации

| Риск | Вероятность | Митигация в плане |
|------|-------------|-------------------|
| DeepStream ↔ Python интеграция | **высокая** | Plan B (appsink + TRT); ×2–3 время E1–E3; шаг 12 |
| DINOv2 OOM на 4 ГБ | **высокая** | `trtexec` probe; defer / ConvNeXt ReID; шаг 15 |
| NVDEC bottleneck (2× RTSP) | средняя | `tegrastats` NVDEC; снизить substream FPS; шаг 12 |
| `extlinux.conf` сброс после apt | средняя | `birdlense-fix-extlinux.sh` + apt hook; шаг 8 |
| Buffer starvation / jitter | средняя | `num-extra-surfaces=2`, leaky queue; шаг 18 |
| Нет benchmark перед боем | — | шаг 16: >10 FPS detect, <100 ms classify |
| Нет recovery test | — | шаг 21: RTSP reconnect без restart контейнера |

**Не в MVP (backlog):** кэш TRT engine по hash (шаг 15), адаптивный interval (6.11), API сброса буферов (шаг 21), CSV perf log (6.11).

---

## 7. Чек-лист перед боем на площадке

Соответствие runbook:

- [ ] **Шаги 1–2:** БП 5V/4A, вентилятор, SSD, SD с JetPack записана
- [ ] **Шаги 3–8:** SSH, apt upgrade, rootfs на SSD, `df -h /` → SSD, extlinux guard
- [ ] **Шаги 9–12:** Docker nvidia runtime, MAXN, ZRAM/headless, `gst-inspect` OK, путь DS vs Plan B зафиксирован
- [ ] **Шаги 13–15:** env, build (`restart: unless-stopped`, host network), `.engine` + parity + DINOv2 probe
- [ ] **Шаг 16:** benchmark зелёный (>10 FPS detect, <100 ms classify), CSV сохранён
- [ ] **Шаги 17–18:** камеры в конфиге, RTSP NVMM без артефактов ≥5 мин
- [ ] **Шаги 19–20:** `make deploy`, health OK, запись с persist, `yolo_frames_with_tracks > 0`, idle RAM baseline
- [ ] **Шаг 21:** recovery test — reconnect без restart контейнера; **`yolo_frames_with_tracks > 0`** после восстановления
- [ ] **24h soak** (ручной): нет OOM/throttle, reconnect сработал; *backlog:* `scripts/jetson_soak_24h.sh` (tegrastats + docker logs → OOM/restart)
- [ ] Golden clips: day/night/IR, close/far, empty negatives
- [ ] Model hashes + JetPack/L4T/DeepStream versions сохранены
- [ ] Low-confidence cases → review/dataset export

---

## 8. Риски и эскалация железа

| Симптом | Действие |
|---------|----------|
| OOM / swap | уменьшить ring buffer, `interval`, отключить ReID live |
| GPU throttle | охлаждение, снизить `binary_imgsz` до 640 |
| NVDEC saturated | снизить substream FPS; event-only high-res decode |
| DeepStream↔Python зависание | Plan B (appsink + TRT); не блокировать MVP |
| DINOv2 OOM | defer ReID; ConvNeXt embedding fallback |
| Загрузка с SD после apt | шаг 8: `birdlense-fix-extlinux.sh` |
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
