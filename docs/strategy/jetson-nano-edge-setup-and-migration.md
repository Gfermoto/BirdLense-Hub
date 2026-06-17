# Jetson Nano B01 — runbook и архитектура BirdLense Hub

**Статус:** Ornimetrics + TensorRT plan (2026-06-17, **rev.4**)  
**Исполнять:** §**2** (шаги 1–21) сверху вниз. §**3–6** — справочник, контракты, научные gates.  
**Visual stack:** [Ornimetrics/ornimetrics-edge](https://huggingface.co/Ornimetrics/ornimetrics-edge) → ONNX → **TensorRT `.engine`**.  
**Не на Jetson:** Hailo `.hef`, Intel-пайплайн «как есть».  
**Связано:** [ADR platform profiles](adr-platform-profiles-intel-jetson.md), [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645)

| § | Содержание |
|---|------------|
| 0–1 | Сводка платформ, роль Jetson |
| 2 | **Runbook 1–21** (единственный порядок работ) |
| 3 | Стек, perf-budget, веса, behavior, issues |
| 4–5 | Камеры, RTSP |
| 6 | Архитектура, деградация, научный контур |
| 7–8 | Чек-лист, риски |

## 0. Сводка платформ

| Платформа | Детектор | Классификатор | ReID / welfare | Behavior |
|-----------|----------|---------------|----------------|----------|
| **Intel NUC** | Trapper + OpenVINO | Birder ConvNeXt EU-707 | DINOv2 deferred | meta + video (OpenVINO) |
| **Jetson Nano** | YOLOv11n TRT | EfficientNetV2-S (Ornimetrics) | ArcFace + Mahalanobis | tracklet heuristics + **X3D-XS** deferred (#660) |

Переключатель species-пакета Ornimetrics — **`ebird.country`** (уже в Settings). Lat/lon — для eBird export и погоды.

---

## 1. Роль Jetson

Jetson Nano B01 (4 ГБ) — вторая боевая платформа (рядом с Intel NUC).

**Делает Jetson:**
- сторож: детекция + трекинг на **lores** 704×576 (YOLOv11n TRT + NvDCF);
- охотник: event-triggered запись main/high-res (NVENC);
- enrichment на кропе: Ornimetrics species + welfare + ReID;
- опционально behavior: meta heuristics (tier 0) + X3D-XS deferred (tier 1, #660).

**Не делает Jetson:** Intel-пайплайн torch/cpu; Hailo `.hef`; EU-707 classifier.

**Общее с NUC:** визиты, triggers/hints (ADR #634), UI, геометрия, BirdNET MQTT, `BIRDLENSE_PLATFORM=jetson_nano`.

**Конфиг (уже в Hub):** `secrets.latitude/longitude`, `ebird.country/state` — см. таблицу в шапке и §3.0.

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
| **B — GStreamer `appsink` + TRT в Python** | **первый рабочий прототип** (ревью 2026-06) | проще отладка; NVDEC + TRT в Python |
| **A — DeepStream Primary GIE + probe** | после стабильного B или запаса GPU | × **2–3** на DS↔Python |

Plan B: `rtspsrc ! nvv4l2decoder ! nvvidconv ! video/x-raw(memory:NVMM) ! appsink` → YOLO TRT + трекер в Python. Не блокировать MVP ожиданием идеального DeepStream.

Plan A: целевой production-path при зелёном benchmark и запасе по GPU.

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

### Шаг 15. Скачать Ornimetrics ONNX и собрать TensorRT на Jetson

**Где:** dev (скачать) + Jetson (сборка `.engine` только на целевом устройстве).

**Источник:** [Ornimetrics/ornimetrics-edge](https://huggingface.co/Ornimetrics/ornimetrics-edge)

**Что скачать:**

| Артефакт | Назначение |
|----------|------------|
| `models/model_feeder4.onnx` | детектор YOLOv11n: `bird`, `squirrel`, `person`, `dog` |
| `models/species_classifier_nabirds.onnx` + `.json` | species **US** (`ebird.country: US`), 555 видов |
| `models/species_classifier_inat.onnx` | species **non-US** (CC), 302 вида |
| `models/embedder.onnx` + `welfare_scorer.npz` | welfare (Mahalanobis) |
| `models/reid_embedder.onnx` | ReID (ArcFace 256-d) |

```bash
pip install huggingface_hub
# Только ONNX и sidecar-файлы; .hef не качаем (RPi+Hailo)
huggingface-cli download Ornimetrics/ornimetrics-edge \
  --local-dir ./ornimetrics-edge \
  --exclude "*.hef"
```

Ожидаемый layout после скачивания: `ornimetrics-edge/models/*.onnx`, `welfare_scorer.npz`, `species_classifier_nabirds.json`, `detector.names`.

**Сборка TensorRT** (только на целевом Jetson):

```bash
./scripts/convert_ornimetrics_trt.sh \
  --detector ornimetrics-edge/models/model_feeder4.onnx \
  --classifier-pack nabirds \
  --output processor/models/ornimetrics/jetson/
```

Скрипт (#650): FP16 `.engine`, кэш по hash, parity gate, manifest.

**Оптимизация после MVP (#650 backlog):** fused TRT — один forward EfficientNetV2-S → species + embed 1280-d + ReID head (сейчас в HF четыре отдельных ONNX).

**Пакет классификатора — из существующего конфига Hub:**

```yaml
secrets:
  latitude: "55.934"      # уже есть: погода, eBird CSV export
  longitude: "36.61"
ebird:
  country: "RU"           # уже есть: регион eBird + выбор пакета Ornimetrics
  state: "MOS"
```

| `ebird.country` | ONNX / `.engine` pack | Классов |
|-----------------|----------------------|---------|
| `US` | `species_classifier_nabirds` | 555 |
| иначе | `species_classifier_inat` | 302 |

Переключатель — **`ebird.country`** (тот же ключ, что `ebird_region_core._build_region_code`). Координаты lat/lon **не вычисляют** пакет сами — пользователь их уже задаёт для eBird; страна задаётся явно рядом.

**Ограничение:** оба классификатора Ornimetrics — североамериканская таксономия. EU-площадка с `country: RU` получает CC-пакет (302) как компромисс «из коробки»; Birder EU-707 на Intel остаётся эталоном для Европы.

**BirdNET:** без изменений (MQTT hint).

**Готово когда:** `.engine` detector + classifier (pack по `ebird.country`) + welfare + reid на Jetson; parity зелёный.

---

### Шаг 16. Benchmark на Jetson (gate перед камерами/deploy)

**Где:** Jetson, тот же образ и `.engine`, что в шаге 15.

**Что сделать:**

```bash
# Реализация: scripts/benchmark_jetson.py (#656 E10; полный отчёт — #657 E11)
python scripts/benchmark_jetson.py \
  --detector-engine processor/models/ornimetrics/jetson/feeder4.engine \
  --classifier-engine processor/models/ornimetrics/jetson/species_nabirds.engine \
  --embedder-engine processor/models/ornimetrics/jetson/embedder.engine \
  --reid-engine processor/models/ornimetrics/jetson/reid.engine \
  --frames 1000 --crop 256,256 --interval 4
```

**Контракт скрипта (реализация, не блокер плана):**

1. Зафиксировать **реальный FPS lores** (ожидаемо **5–9**, обычно ~7 — не 10–15).
2. Загрузить `.engine` на **этом** Jetson.
3. **YOLO infer:** p95 latency на один forward (416² FP16).
4. **Cadence:** sustained infer rate ≥ `stream_fps / interval × 0.9` без роста очереди 5 мин (пример: 7 FPS, interval=3 → ≥2.0 infer/s).
5. **Classifier** (event-only): p95 на один кроп; при miss <100 ms — defer OK, если persist не ждёт.
6. RAM (`docker stats`), CPU (`tegrastats`) — baseline в CSV.
7. Опционально X3D-XS (#660): `trtexec` probe до поля; gate <500 ms или снизить frames/resolution.

**Пороги (не деплоить на 2 cam live, если не выполнены):**

| Метрика | Минимум |
|---------|---------|
| Lores FPS (зафиксировать) | **5–9** типично; документировать факт |
| YOLO infer p95 | **<100 ms** на forward |
| Infer cadence | ≥ `stream_fps/interval × 0.9` sustained 5 min, очередь не растёт |
| Классификатор (1 кроп, event) | **цель** <100 ms p95; **hard** <200 ms или только async |
| Welfare + ReID | **цель** <50 ms p95 (после defer path) |
| Behavior X3D-XS (опц.) | **цель** <500 ms p95; fallback 2 frames / 128² |
| GPU sustained | ≤85%; CPU ≤250% |
| RAM container idle | baseline <2.5 ГБ до live |

Лог: CSV `jetson_bench_YYYYMMDD.csv` (latency, FPS, queue depth) — для сравнения после тюнинга.

**Готово когда:** benchmark зелёный; цифры записаны в deployment notes.

---

### Шаг 17. Настроить камеры в Hub

**Где:** `app/app_config/user_config.yaml` (на Jetson или через deploy).

**Что сделать:**

1. Две камеры: `feeder_close`, `feeder_far` в `video.cameras[]`.
2. Для каждой камеры:
   - **lores/detect** — прямой RTSP (substream 704×576, H.264, **~5–9 FPS**, типично **~7**).
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

### 3.0 Ornimetrics visual pack

Источник: [Ornimetrics/ornimetrics-edge](https://huggingface.co/Ornimetrics/ornimetrics-edge). Jetson: **ONNX → TensorRT**; `.hef` — для RPi5+Hailo-8, на Nano **игнорируем**.

| Компонент | Архитектура | Выход | Когда |
|-----------|-------------|-------|-------|
| **Детектор** | YOLOv11n, 416×416 | bird / squirrel / person / dog | live lores (сторож) |
| **Species** | EfficientNetV2-S, 256×256 | 555 (US) или 302 (CC) | 1 кроп / событие (охотник) |
| **Welfare** | backbone → Mahalanobis | anomaly score | 1 кроп / событие |
| **ReID** | ArcFace | 256-d | 1 кроп / visit |
| **BirdNET** | DS-CNN (вне Hub) | species hint | MQTT, ADR #634 |

**Species pack** — `ebird.country`. Lat/lon — погода и eBird CSV, не выбор `.engine`.

| `ebird.country` | Pack | Классов |
|-----------------|------|---------|
| `US` | `species_classifier_nabirds` | 555 |
| иначе | `species_classifier_inat` | 302 |

NA-таксономия; EU-707 Birder — на Intel. Welfare — перекалибровка healthy baseline на своих кропах ([caveats Ornimetrics](https://huggingface.co/Ornimetrics/ornimetrics-edge)).

### 3.1 Бюджет производительности (Nano 4 ГБ)

Ornimetrics на Hailo ~28 fps — **с NPU**. Nano без NPU; detect substream у нас **~5–9 FPS** (типично **~7**, см. `default_config` / Frigate lores), **строго <10 FPS** — не закладывать 10–15 FPS на lores.

Enrichment **только event-triggered** (охотник), не в live loop.

| Ресурс | MVP | При перегрузе |
|--------|-----|---------------|
| RAM | ≤3.0 ГБ | ring buffer ↓, ReID off |
| GPU | ≤85% | `interval+1` (до 5–6), detector 416→384 |
| CPU | ≤250% sustained (4 cores) | Plan B проще; меньше буферов |
| **Детектор** | см. шаг 16 | IOU tracker, interval+1 |
| Species | **цель** <100 ms p95 / кроп | **обязательно** defer async; 100–200 ms допустимо |
| Welfare + ReID | **цель** <50 ms p95 | welfare off → ReID off |
| Behavior E14 | **цель** <500 ms p95 / клип | off; X3D: 4→2 frames, 182→128 |

**Детектор — не «>10 FPS».** На 7 FPS lores + `interval=3` реально **~2.3 infer/s**. Gate: latency + не отставать от потока (шаг 16).

Video + bbox persist **не ждут** ML.

### 3.2 Скачивание весов (без Hailo)

Исполняется в **шаге 15**. Список файлов:

| Файл | Jetson |
|------|--------|
| `model_feeder4.onnx` | да |
| `species_classifier_{nabirds,inat}.onnx` + `.json` | один pack |
| `embedder.onnx`, `welfare_scorer.npz`, `reid_embedder.onnx` | да |
| `*.hef` | **нет** |

Скрипт (#650): `scripts/fetch_ornimetrics.sh --exclude-hef`. Fused TRT backbone — backlog #650.

### 3.3 Behavior (#660 E14)

Ornimetrics behavior не даёт. Три уровня:

**Уровень 0 — tracklet heuristics (MVP, 0 GPU):** `behavior_baseline_runtime`, NvDCF metadata — `perching`, `flying_away`, `intrusion` (person/dog/squirrel), `unknown`. `engine: meta`.

**Уровень 1 — X3D-XS (рекомендованный 3D-CNN):**

| | |
|--|--|
| Архитектура | [X3D-XS](https://arxiv.org/abs/2004.04730), [PyTorchVideo zoo](https://pytorchvideo.readthedocs.io/en/latest/model_zoo.html) |
| Params / FLOPs | ~3.8 M / **0.91 G** per clip |
| Вход | 4 frames, stride 12, **182×182** bbox-crop |
| Деплой | PyTorch → ONNX → TRT FP16 |
| Gate | <500 ms p95 на клипе 2–4 с |

SlowFast на Nano [не взлетает](https://www.ridgerun.ai/post/optimization-of-an-action-recognition-dl-model-for-the-nvidia-jetson-platform). Запасной по accuracy: X3D-S (2.96 G). Запасной по стеку: [MoViNet-A0-Stream](https://github.com/tensorflow/models/tree/master/official/projects/movinet) (2.7 G, TF/TFLite) — только если X3D-XS провалит benchmark.

**Контракт:** deferred на mp4 охотника; метки `feeding`, `perching`, `flying_away`, `courtship`, `intrusion`, `unknown` — fine-tune на yard data; Kinetics pretrained не маппится. Jetson default: `behavior_recognition.enabled: false` до soak 2 cam.

### 3.4 Issues → runbook

| E | Issue | Runbook | Слой |
|---|-------|---------|------|
| E0 | [#646](https://github.com/Gfermoto/BirdLense-Hub/issues/646) | 1–11 | SSD, Docker, MAXN, ZRAM |
| E1 | [#647](https://github.com/Gfermoto/BirdLense-Hub/issues/647) | 12 | NVDEC/NVENC, GStreamer |
| E2 | [#648](https://github.com/Gfermoto/BirdLense-Hub/issues/648) | 12 | DeepStream сторож + NvDCF |
| E3 | [#649](https://github.com/Gfermoto/BirdLense-Hub/issues/649) | 12, 6.1 | Ring buffer + охотник |
| E4 | [#650](https://github.com/Gfermoto/BirdLense-Hub/issues/650) | 15 | Ornimetrics ONNX→TRT |
| E5 | [#651](https://github.com/Gfermoto/BirdLense-Hub/issues/651) | 13–14, 19 | Platform, deploy, CI |
| E6 | [#652](https://github.com/Gfermoto/BirdLense-Hub/issues/652) | 6.1 | Hub ingest adapter |
| E7 | [#653](https://github.com/Gfermoto/BirdLense-Hub/issues/653) | 17–21 | Field test 2 cam |
| E8 | [#654](https://github.com/Gfermoto/BirdLense-Hub/issues/654) | весь doc | Docs / ADR sync |
| E9 | [#655](https://github.com/Gfermoto/BirdLense-Hub/issues/655) | 18, 21 | RTSP reconnect |
| E10 | [#656](https://github.com/Gfermoto/BirdLense-Hub/issues/656) | 16, 6.11 | Perf budget, throttle |
| E11 | [#657](https://github.com/Gfermoto/BirdLense-Hub/issues/657) | 16, 6.10, 7 | Scientific benchmark |
| E12 | [#658](https://github.com/Gfermoto/BirdLense-Hub/issues/658) | 6.10 | FAIR / Camtrap DP |
| E13 | [#659](https://github.com/Gfermoto/BirdLense-Hub/issues/659) | 6.10, 7 | HITL review queue |
| E14 | [#660](https://github.com/Gfermoto/BirdLense-Hub/issues/660) | 3.3, 16 | Behavior X3D-XS deferred |

---

## 4. Справочник: камеры (детали к шагам 17–18)

| Поток | Назначение | Разрешение | FPS | Маршрут |
|-------|------------|------------|-----|---------|
| Substream / detect | DeepStream сторож | 704×576 | **5–9** (~7) | **прямой RTSP камеры** |
| Main | ring buffer + запись | 1080p | 15–25 | **через go2rtc** |

- Оба **H.264**, GOP 2–4 с, NTP на камере.
- `video.cameras[]`: `tuning_role: feeder_close|feeder_far`.

Исполнять: **шаг 17** (конфиг) → **шаг 18** (проверка gst-launch + buffer tune).

---

## 5. RTSP и сеть (Jetson)

### 5.1 Источник потоков: go2rtc vs прямой RTSP

На площадке Hub уже использует **go2rtc** (`video.go2rtc_url`). На Jetson — **гибрид**:

| Поток | Маршрут | Зачем |
|-------|---------|-------|
| **main / high-res** | `rtsp://<go2rtc>:8554/...` | ring buffer + NVENC |
| **lores / detect** | **прямой RTSP камеры** | сторож; **не** через go2rtc (latency) |

**go2rtc:** обычно на **том же LAN-хосте**, что и камеры (Intel NUC, VPS, отдельный SBC) — `GO2RTC_URL` / `video.go2rtc_url` в Hub. Jetson — **клиент** main-потока. Если go2rtc на единственном хосте — единая точка отказа; зафиксировать в deployment notes.

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

1. **Сторож (DeepStream или Plan B):** 2× lores **~7 FPS**.  
   YOLO TRT FP16, `interval=3–5` → **~1.4–2.3 infer/s** при 7 FPS; NvDCF **каждый** кадр заполняет промежутки.  
   Probe → событие `TRIGGER_RECORD(camera_id, track_id, bbox, ts)`.

2. **Кольцевой буфер high-res:** лёгкий GStreamer `uridecodebin ! nvvidconv ! appsink` на main stream;  
   `deque` последних 60–90 кадров (~2–3 с). **Не** пишем на диск до триггера.

3. **Охотник (Python):** по триггеру — pre-roll + post-roll → **NVENC** → mp4.  
   Один кроп → **EfficientNetV2-S** (Ornimetrics): species + welfare + ReID за один проход backbone.

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
| **BirdNET MQTT** | аудио на площадке (отдельный сервис) | FIFO 24h, prior/confidence bias | **не multimodal**; не заменяет visual classifier; hint only (ADR #634) |
| **eBird regional** | API key + регион | снижает пороги для типичных видов региона | не фильтрует детектор жёстко |
| **Frigate label/sub_label** | MQTT в окне сессии | species prior, fusion bonus | не substitute за отсутствие YOLO anchor (кроме legacy `detect_first`) |
| **multicam group** | `multi_camera_groups` | boost confidence, hint scope между close/far | не блокирует параллельную запись второй камеры |
| **adaptive_profiles** (night/day) | по освещению | пороги, трекер, preprocess | не триггер |
| **camera_tuning_by_role** | feeder_close/far | geometry, thresholds | не триггер |
| **weather** | интеграция | enrichment, аналитика | не триггер |
| **photogrammetry / geometry** | `frame_geometry` | sanity bbox, px/m | не триггер |

Сборка: `collect_hints()` → scorer → fusion/classifier. Веса (`birdnet_prior`, `regional_prior`, …) — **взвешивание при наличии**, не ранжирование «кто главный».

**Behavior** — см. §3.3: tier 0 tracklet heuristics (MVP); tier 1 **X3D-XS** deferred на клипе (#660). При overload behavior отключается **первым** в deferred queue.

### 6.3 Intel vs Jetson — разделение ответственности

| | Intel NUC | Jetson Nano |
|--|-----------|-------------|
| Профиль | `intel_nuc` (default) | `jetson_nano` |
| Детектор | Trapper 704² | YOLOv11n 416² TRT |
| Classifier | Birder EU-707 | Ornimetrics EfficientNetV2-S |
| ReID | DINOv2 deferred | ArcFace Ornimetrics |
| Welfare | — | Mahalanobis |
| Behavior video | OpenVINO (существующий путь) | meta heuristics + X3D-XS TRT (E14) |
| Deploy | `make deploy` без изменений | `BIRDLENSE_PLATFORM=jetson_nano` |

Общий код: visits, triggers/hints (ADR #634), UI, `track_regenerator`, BirdNET MQTT.

### 6.4 Что сохраняем из текущего Hub

- `feeder_close` / `feeder_far`, `camera_tuning_by_role`, geometry contract (`frame_shape.py`)
- Linear stages: trigger → detect_track → classify → persist
- **Контракт триггеров vs подсказок** (ADR #634)
- **Конфиг eBird:** `secrets.latitude`, `secrets.longitude`, `ebird.country`, `ebird.state` — уже в UI; Jetson читает те же ключи для пакета Ornimetrics и regional hints
- **Intel NUC** — без изменений (Trapper + Birder EU-707)
- OpenAPI, UI, Telegram, visit model

### 6.5 Jetson execution contract (Ornimetrics)

| Стадия | Intel (NUC) | Jetson (Ornimetrics) |
|--------|-------------|----------------------|
| Detector | Trapper YOLO + OpenVINO/torch | YOLOv11n TRT, lores, `interval=3–5` |
| Tracker | ByteTrack | NvDCF или IOU fallback |
| Classifier | Birder ConvNeXt EU-707 | EfficientNetV2-S TRT; pack по `ebird.country` |
| Welfare | — | Mahalanobis (embedder TRT) |
| ReID | DINOv2 deferred (Intel) | ArcFace 256-d (Ornimetrics TRT) |
| Behavior | meta + OpenVINO video (Intel) | tier 0 meta + X3D-XS deferred (E14) |
| Audio hint | BirdNET MQTT | **то же** — без изменений |
| Persist | finalize | video+bbox first; enrich async |

Правило деградации:

1. Всегда сохраняем событие и bbox metadata.
2. Если GPU/RAM high → classifier skipped/deferred.
3. Если RAM high → ReID off.
4. Если latency high → `interval += 1`, затем detector input **416→384** (letterbox).
5. Если deferred queue растёт → behavior off → ReID off (species/welfare уже defer по п.2).
6. Если event quality низкая → не меняем модель сразу; сначала проверяем RTSP, tracker, threshold parity.

### 6.6 Parity gates (по платформе)

**Intel NUC (без изменений):** Trapper detector, Birder ConvNeXt EU-707, DINOv2 ReID deferred.

**Jetson (Ornimetrics):**

- **Detector:** `model_feeder4.onnx` vs `.engine`; IoU ≥0.85, recall drop ≤5% на golden clips.
- **Classifier:** top-1/top-5, margin; pack `nabirds` vs `inat` по `ebird.country`.
- **Welfare:** Mahalanobis score distribution vs Ornimetrics baseline.
- **ReID:** ArcFace cosine distance vs ONNX reference.
- **Golden clips:** `feeder_close` + `feeder_far`; day/night/IR обязательны.

Переключатель пакета — **`ebird.country`** (уже в Settings); lat/lon — для eBird export и погоды, не для выбора `.engine`.

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
- **Shared backbone** (Ornimetrics): один кроп EfficientNetV2-S → species + welfare + ReID (ArcFace) за один проход.
- **Fine-tune на yard data** (BirdClass-NA, Backyard watcher): 20–30 кропов/вид обязательны до деплоя. Dataset: `gfermoto/birdlense-annotations`.
- **Pre-roll buffer** (Orpheus): гарантированный pre-roll 1–2 c до события. Ring buffer реализует эту практику.
- **MegaDetector/Wildlife Insights pattern:** animal/empty filtering, uncertainty routing, HITL review. В BirdLense это не runtime-модель, а benchmark/reference gate: наши detector+trigger графы должны давать сопоставимый FN/FP профиль на golden clips.
- **Active learning:** неизвестные, low-margin и конфликтные случаи не прячем; отправляем в review queue/dataset export. Цель — уменьшать ручную разметку, не «доверять AI вслепую».
- **FAIR / Camtrap DP:** внутренний формат Hub сохраняется, но внешний экспорт должен быть совместим с Camtrap DP/Darwin Core/Audubon Core.

### 6.9 Мультимодальность и edge-развёртывание

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
| GPU | ≤80–85% sustained | `interval+1`, detector **416→384**, defer enrichment |
| CPU | ≤250% sustained (из 4 cores) | убрать OpenCV hot path, только GStreamer/DS metadata |
| Температура | <75–80°C | fan/jetson_clocks policy, снизить FPS/interval |
| Latency event | pre-roll 2–3 c + post-roll 8–10 c | сохранять клип даже без classifier/ReID, enrich позже |

**Правило:** если ML-обогащение не укладывается, сохраняем видео + bbox metadata, а classification/ReID переносим в deferred job. Потеря вида лучше, чем потеря события.

- `tegrastats --interval 1000 --format json` → парсить GPU util, RAM, temp, power, **NVDEC load** (две камеры).
- Watchdog: GPU >85% или RAM >2.8 ГБ → `interval+1`, detector input ↓, **defer** species/welfare/ReID (не live GIE на Jetson).
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
| Ornimetrics TRT RAM на 4 ГБ | средняя | отдельные `.engine`, welfare/ReID defer при overload; шаг 15–16 |
| NVDEC bottleneck (2× RTSP) | средняя | `tegrastats` NVDEC; снизить substream FPS; шаг 12 |
| `extlinux.conf` сброс после apt | средняя | `birdlense-fix-extlinux.sh` + apt hook; шаг 8 |
| Buffer starvation / jitter | средняя | `num-extra-surfaces=2`, leaky queue; шаг 18 |
| Нет benchmark перед боем | — | шаг 16: cadence + p95, не «>10 FPS» |
| Нет recovery test | — | шаг 21: RTSP reconnect без restart контейнера |

**Не в MVP (backlog):** адаптивный interval в коде (6.11, #656), API сброса буферов (шаг 21, #655), fused TRT backbone (#650).

### 6.15 Научный контур продукта (E11–E13)

Jetson-план совместим с полевым протоколом для заповедников и citizen science — не отдельный «research fork», а gates в том же runbook:

| Принцип | Где в плане | Issue |
|---------|-------------|-------|
| Воспроизводимость (версии, hashes, config snapshot) | §6.10, шаг 16 CSV | #657 |
| Golden clips + parity ONNX↔TRT | §6.6, шаг 16 | #657, #650 |
| Uncertainty (confidence, margin, hints ≠ истина) | §6.2.2, §6.10 | #659 |
| HITL / review queue | §6.10, чек-лист §7 | #659 |
| FAIR export (Camtrap DP, DwC) | §6.10 | #658 |
| Ethics (person/dog ≠ biodiversity record) | §6.10, детектор Ornimetrics | — |
| 24h soak + recovery | шаги 20–21, §7 | #653, #655 |

**Порядок:** operational gates (шаг 16) **до** полевого деплоя; полный scientific bundle (#657) — после 2-cam soak, перед публикацией/обменом данными.

### 6.16 Внешнее ревью (2026-06, rev.4) — принято

| Рекомендация | Решение в плане |
|--------------|----------------|
| Lores **<10 FPS** на площадке | Gate **cadence + p95**, не >10 FPS infer (шаг 16, §3.1) |
| Species <100 ms может быть жёстко | **Цель**; defer async обязателен; hard <200 ms |
| Plan B раньше Plan A | Шаг 12: **B = прототип**, A = production |
| X3D-XS — `trtexec` до поля | Шаг 16 п.7; fallback 2 frames / 128² |
| CPU ≤250% в мониторинг | §6.11, шаг 16 CSV |
| `nvinfer` только в DeepStream 6.2 | Шаги 12, 14 |
| go2rtc — где крутится | §5.1, шаг 13 `GO2RTC_URL` |
| Первые действия на железе | TRT convert → benchmark 16 → решение Orin |

---

## 7. Чек-лист перед боем на площадке

Соответствие runbook:

- [ ] **Шаги 1–2:** БП 5V/4A, вентилятор, SSD, SD с JetPack записана
- [ ] **Шаги 3–8:** SSH, apt upgrade, rootfs на SSD, `df -h /` → SSD, extlinux guard
- [ ] **Шаги 9–12:** Docker nvidia runtime, MAXN, ZRAM/headless, `gst-inspect` OK, путь DS vs Plan B зафиксирован
- [ ] **Шаги 13–15:** env, build (`restart: unless-stopped`, host network), Ornimetrics `.engine` + parity
- [ ] **Шаг 16:** benchmark (#656): lores FPS записан, YOLO p95 <100 ms, cadence ≥ stream/interval×0.9
- [ ] **Шаги 17–18:** камеры, RTSP NVMM ≥5 мин
- [ ] **Шаги 19–20:** deploy, smoke, `yolo_frames_with_tracks > 0`, idle RAM
- [ ] **Шаг 21:** recovery без restart контейнера
- [ ] **24h soak** (#653): OOM/throttle/reconnect
- [ ] **Scientific bundle** (#657–#659): golden clips, parity report, HITL export path
- [ ] Model hashes + JetPack/L4T/DeepStream в deployment notes

---

## 8. Риски и эскалация железа

| Симптом | Действие |
|---------|----------|
| OOM / swap | уменьшить ring buffer, `interval`, отключить ReID live |
| GPU throttle | охлаждение, `interval+1`, detector 416→384 |
| NVDEC saturated | снизить substream FPS; event-only high-res decode |
| DeepStream↔Python зависание | Plan B (appsink + TRT); не блокировать MVP |
| ReID/welfare overload | defer welfare → ReID off; interval+1 |
| Загрузка с SD после apt | шаг 8: `birdlense-fix-extlinux.sh` |
| 2 камеры не тянут | event-only high-res обязателен; иначе **Orin Nano 8GB** |
| Engine mismatch | пересобрать TRT на устройстве |

---

## 9. Ссылки

- `deploy/profiles/jetson-nano/`
- `app/Dockerfile.jetson`, `app/docker-compose.jetson.yml`
- `scripts/platform-profile.sh`
- Epic: [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645)
- Scientific gates: [#657](https://github.com/Gfermoto/BirdLense-Hub/issues/657) (E11), [#658](https://github.com/Gfermoto/BirdLense-Hub/issues/658) (E12), [#659](https://github.com/Gfermoto/BirdLense-Hub/issues/659) (E13)
- Behavior: [#660](https://github.com/Gfermoto/BirdLense-Hub/issues/660) (E14)
- RTSP: [#655](https://github.com/Gfermoto/BirdLense-Hub/issues/655) (E9)
- Perf budget: [#656](https://github.com/Gfermoto/BirdLense-Hub/issues/656) (E10)

---

## 10. Внешние источники

- Ornimetrics model card + limitations: <https://huggingface.co/Ornimetrics/ornimetrics-edge>
- X3D (efficient video nets): <https://arxiv.org/abs/2004.04730>, PyTorchVideo zoo — <https://pytorchvideo.readthedocs.io/en/latest/model_zoo.html>
- MoViNet (mobile video, fallback): <https://github.com/tensorflow/models/tree/master/official/projects/movinet>
- RidgeRun action recognition on Jetson (SlowFast ≠ Nano): <https://www.ridgerun.ai/post/optimization-of-an-action-recognition-dl-model-for-the-nvidia-jetson-platform>
- NVIDIA DeepStream troubleshooting: <https://docs.nvidia.com/metropolis/deepstream/6.2/dev-guide/text/DS_troubleshooting.html>
- NVIDIA DeepStream performance (Nano FP16, interval, NvDCF): <https://docs.nvidia.com/metropolis/deepstream/6.0.1/dev-guide/text/DS_Performance.html>
- RidgeRun GStreamer encoder latency: <https://developer.ridgerun.com/wiki/index.php/GStreamer_Encoding_Latency_in_NVIDIA_Jetson_Platforms>
