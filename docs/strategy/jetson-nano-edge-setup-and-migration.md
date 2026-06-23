# Jetson Nano B01 — runbook и архитектура BirdLense Hub

**Статус:** Jetson production stack **2026-06-22** (ветка `jetson-nano`; TRT detector + chriamue ONNX + Ornimetrics reid/welfare)
**Исполнять:** §**2** (шаги 1–20) сверху вниз. §**3–6** — справочник, контракты, научные gates.
**Visual stack:** TrapperAI v02.2024 → ONNX 704² → **TensorRT FP16 `.engine`**; species **chriamue** ONNX; ReID/welfare **Ornimetrics ONNX**.  
**Не на Jetson:** OpenVINO IR, Birder EU-707, Intel VA-API encode/decode, Hailo `.hef`.  
**Связано:** [ADR platform profiles](adr-platform-profiles-intel-jetson.md), [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645)

| § | Содержание |
|---|------------|
| 0–1 | Сводка платформ, **стек нейросетей Jetson (2026-06)** |
| 2 | **Runbook 1–20** (единственный порядок работ) |
| 3 | Perf-budget, веса, behavior, issues |
| 4–5 | Камеры, RTSP |
| 6 | Архитектура, деградация, научный контур |
| 7–8 | Чек-лист, риски |

## 0. Сводка платформ

| Платформа | Детектор | Классификатор | ReID / welfare | Behavior |
|-----------|----------|---------------|----------------|----------|
| **Intel NUC** | Trapper + OpenVINO GPU | Birder ConvNeXt EU-707 | DINOv2 deferred | meta + video (OpenVINO) |
| **Jetson Nano** | **TrapperAI TRT** `.engine` @704 | **chriamue** EfficientNet 525 spp (ONNX CUDA) | **Ornimetrics** ArcFace ONNX + welfare NPZ | **meta** heuristics (logistic JSON) |

Переключатель species-пакета Ornimetrics на Intel — **`ebird.country`**. На Jetson species — **chriamue** (глобальный 525-class pack, не Ornimetrics NA/CC).

### 0.1 Стек нейросетей Jetson (production, 2026-06-22)

Все артефакты — **на устройстве** (`app/processor/models/`, bind на SSD). Сборка конфига: `python3 scripts/build_jetson_user_config.py`.

| Этап | Модель | Backend | Путь (flat layout) | Примечание |
|------|--------|---------|-------------------|------------|
| **Детектор** | [TrapperAI v02.2024](https://huggingface.co/OSCF/TrapperAI-v02.2024) | **TensorRT** FP16 | `detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine` | lores 704×576; классы Bird + Eurasian Red Squirrel; fallback `.pt`+torch если `.engine` нет |
| **Классификатор** | [chriamue/bird-species-classifier](https://huggingface.co/chriamue/bird-species-classifier) | **ONNX Runtime** (CPU, TRT — roadmap) | `classification/chriamue_bird_species_classifier/model.onnx` | 525 видов; preprocess из `preprocessor_config.json` (260×260), без OpenVINO |
| **ReID** | Ornimetrics edge | **ONNX Runtime** (CPU, TRT — roadmap) | `reid/ornimetrics/reid_embedder.onnx` | `scripts/fetch_ornimetrics_jetson.sh` |
| **Welfare** | Ornimetrics edge | ONNX + NPZ | `welfare/ornimetrics/embedder.onnx`, `welfare_scorer.npz` | Mahalanobis scorer |
| **Behavior** | meta baseline | **logistic_json** | `models/behavior/meta/behavior_logistic_export@v1.json` | без OpenVINO fallback на Jetson |

**Видео (Jetson, HW acceleration):**

| Функция | Значение | Железо |
|---------|----------|--------|
| Захват lores (motion/YOLO) | `capture_backend: ffmpeg_nvmpi`, GStreamer NVDEC | **HW NVDEC** через `nvv4l2decoder` |
| Запись main | `encoding: jetson`, `h264_v4l2m2m` → fallback `h264_omx` → `libx264` | **HW V4L2 mem2mem / OpenMAX IL** |
| VA-API / Intel iGPU | **выключено** | `record_with_vaapi: false` |
**Env (`app/.env` + `docker-compose.jetson.yml`):** `BIRDLENSE_PLATFORM=jetson_nano`, `BIRDLENSE_INFERENCE_BACKEND=tensorrt`, `BIRDLENSE_BINARY_TENSORRT_PATH=models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine`, `BIRDLENSE_CLASSIFIER_ENGINE=chriamue`, `BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND=onnxruntime`, `BIRDLENSE_ENCODING=jetson`, `BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=0`, `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1`.

**Bootstrap без `.engine`:** `python3 scripts/build_jetson_user_config.py --bootstrap-torch` → torch/cpu до `export_trapper_detector_trt.sh`.

**После `docker compose --force-recreate`:** `scripts/jetson-post-recreate-bootstrap.sh` (до пересборки образа с обновлённым `Dockerfile.jetson`).

---

## 1. Роль Jetson

Jetson Nano B01 (4 ГБ) — вторая боевая платформа (рядом с Intel NUC).

**Делает Jetson:**
- сторож: детекция + трекинг на **lores** 704×576 (**TrapperAI TensorRT** + ByteTrack);
- охотник: event-triggered запись main/high-res (**HW V4L2 h264_v4l2m2m**, fallback h264_omx → libx264);
- enrichment на кропе: **chriamue** species (525) + **Ornimetrics** welfare + ReID;
- behavior: **meta** heuristics (logistic JSON), без OpenVINO.

**Не делает Jetson:** OpenVINO / Birder EU-707 / Intel VA-API; Ornimetrics NA/CC species packs; Hailo `.hef`.

**Общее с NUC:** визиты, triggers/hints (ADR #634), UI, геометрия, BirdNET MQTT, `BIRDLENSE_PLATFORM=jetson_nano`.

**Хранение (rev.7):** система на **SD**, тяжёлые данные на **SSD** — `app/data`, Docker, веса, journal (§2.0). На Jetson держим **runtime bundle**, не полный dev-репозиторий.

**Конфиг (уже в Hub):** `secrets.latitude/longitude`, `ebird.country/state` — см. таблицу в шапке и §3.0.

---

## 2. Runbook — выполнять строго по порядку

Один путь. Не перескакивать шаги. Каждый шаг: **где**, **что сделать**, **команды**, **готово когда**.

| Шаг | Где | Суть |
|-----|-----|------|
| 1–2 | стол / ПК | железо, образ на SD |
| 3–4 | Jetson | boot, SSH, JetPack |
| 5–7 | Jetson | SSD: разметка, **bind-mounts**, проверка |
| 8–12 | Jetson | Docker на SSD, MAXN, ZRAM, GStreamer |
| 13–16 | Jetson + dev | env, build, TRT, **benchmark** |
| 17–18 | Jetson / UI | камеры, RTSP + buffer tune |
| 19–20 | dev → Jetson | deploy, smoke, **recovery test** |

### 2.0 Стратегия хранения: система на SD, тяжёлое на SSD

**Принцип:** корень `/` и `/boot` остаются на **microSD** (перепрошивка SD не трогает клипы и БД). USB/NVMe SSD — только для **write-heavy** и **крупных** каталогов. Без `rsync` rootfs и без правки `extlinux` — меньше риск «не грузится после reboot».

**Runtime-дерево на SD** (`/home/gfer/BirdLense`) — только то, что нужно для запуска/деплоя. Не копировать `docs/`, `.github/`, `datasets/`, venv, тестовые артефакты, старые UI-каталоги, кэши и Markdown-документацию.

```text
/home/gfer/BirdLense/
├── app/
│   ├── .env                         # локальный runtime env
│   ├── docker-compose.yml
│   ├── docker-compose.jetson.yml
│   ├── Dockerfile.jetson
│   ├── app_config/                  # default/user config
│   ├── data/                        # bind → /mnt/ssd/birdlense/data
│   ├── nginx/
│   ├── processor/                   # runtime code + models bind
│   │   └── models/                  # bind → /mnt/ssd/birdlense/models
│   ├── scripts/
│   ├── shared/
│   ├── ui/dist/                     # уже собранный UI; не node_modules
│   └── web/
├── scripts/                         # только deploy/runtime scripts, не docs tooling
├── AGENTS.md
├── Makefile
└── VERSION
```

**Фактический clean-layout после ручной гигиены (2026-06-18):**

```text
/home/gfer/BirdLense/
├── AGENTS.md
├── app/
│   ├── .env
│   ├── data/                        # SSD bind
│   └── processor/
│       └── models/                  # SSD bind
├── Makefile
├── scripts/
└── VERSION
```

Этот layout малый, но **ещё не полноценный runtime bundle для сборки**: перед `compose build` нужно синхронизировать минимальный allowlist из §2.12, а не весь репозиторий.

**Дерево на SSD** (`/mnt/ssd`):

```text
/mnt/ssd/
├── birdlense/
│   ├── data/              # recordings, SQLite, dataset exports
│   └── models/            # detection/classification weights, .engine
├── docker/                # Docker data-root (слои, volumes, build cache)
├── log/
│   └── journal/           # systemd journal (лимит размера)
└── apt-cache/             # опционально: кэш apt
```

**Фактический clean-layout SSD после гигиены (2026-06-18):**

```text
/mnt/ssd/
├── apt-cache/
├── birdlense/
├── docker/
├── log/
└── lost+found/
```

Если на SSD после неудачной rootfs migration остались `bin/`, `boot/`, `etc/`, `home/`, `lib/`, `usr/`, `var/` и т.п. — это **мусор**, не runtime state. Удалять только после проверки, что `/` смонтирован с SD (`df /` → `/dev/mmcblk0p1`) и `fstab` использует только перечисленные SSD-каталоги.

**Что куда (tiers):**

| Tier | Каталог | Зачем | Износ SD |
|------|---------|-------|----------|
| **A** (обязательно) | `app/data` → SSD | клипы, `birdlense.db`, кропы | снимает **главный** write load |
| **A** | `docker` data-root | образы Hub, Redis volume, build cache | частые слои при deploy |
| **B** (рекомендуется) | `processor/models` | `.pt`, ONNX, TRT `.engine` (сотни MB–GB) | deploy и TRT build |
| **B** | `journal` | логи systemd | постоянные мелкие записи |
| **C** (опционально) | `apt-cache` | `apt install` / upgrade | умеренно |
| **— не переносить** | `/`, `/boot`, `~/BirdLense` (код) | система и git | чтение после setup |
| **— не переносить** | swap-файл на диск | — | только **ZRAM** (шаг 10), не swap на SD/SSD |
| **— не переносить** | весь `/var/log` bind | риск гонок с journal | достаточно journal + лимиты docker logs |

**Поведение при отвале SSD:** в `fstab` — `nofail`, чтобы Jetson **загрузился с SD**; Hub без данных нерабочен — для боя SSD должен быть подключён до power-on.

**Перепрошивка SD:** записать новый образ → шаги 3–4 → шаги 5–8 (SSD уже с данными, bind заново) → deploy. Клипы и БД на SSD сохраняются.

**Запрещено на Jetson:** полный `rsync` корня репозитория без allowlist. Jetson — edge runtime, не dev-машина.

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

### Шаг 5. Разметить SSD и каталоги

**Где:** Jetson по SSH.

> **Повторная установка:** если на SSD уже есть `birdlense-data` и клипы — **не** выполнять `mkfs.ext4`; только `mount` и шаг 6 (bind). `mkfs` уничтожит данные.

**Что сделать:**

```bash
lsblk
# USB SSD обычно /dev/sda, NVMe — /dev/nvme0n1
# Ниже SSD_DEV=/dev/sda1 — подставь свой раздел!

export SSD_DEV=/dev/sda1   # пример

sudo parted "${SSD_DEV%1}" mklabel gpt
sudo parted "${SSD_DEV%1}" mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L birdlense-data "$SSD_DEV"

sudo mkdir -p /mnt/ssd
sudo mount "$SSD_DEV" /mnt/ssd

sudo mkdir -p /mnt/ssd/birdlense/data/{recordings,db,dataset}
sudo mkdir -p /mnt/ssd/birdlense/models/{detection/trapper_ai_v02_2024,classification/chriamue_bird_species_classifier,reid/ornimetrics,welfare/ornimetrics}
sudo mkdir -p /mnt/ssd/docker /mnt/ssd/log/journal /mnt/ssd/apt-cache/{archives,partial}
sudo chown -R "$USER:$USER" /mnt/ssd/birdlense
sudo chown root:root /mnt/ssd/docker /mnt/ssd/log /mnt/ssd/apt-cache
```

**Готово когда:** `lsblk` показывает `$SSD_DEV` ext4; дерево `/mnt/ssd/birdlense/...` существует.

---

### Шаг 6. Смонтировать SSD и bind-mounts (Tier A–C)

**Где:** Jetson по SSH.

**Переменные** (подставь один раз):

```bash
export SSD_DEV=/dev/sda1
export SSD_UUID=$(sudo blkid -s UUID -o value "$SSD_DEV")
export BIRDLENSE_ROOT="$HOME/BirdLense"
```

**6.1 — автомонтирование SSD + bind-mounts одним файлом** (`nofail`: загрузка с SD, если USB отключён).

Не дописывать bind-строки выше SSD-строки. Порядок важен: сначала `/mnt/ssd`, потом bind-mounts.

```bash
sudo cp /etc/fstab /etc/fstab.bak.birdlense-runtime
sudo tee /etc/fstab >/dev/null <<EOF
# /etc/fstab: static file system information.
# <file system> <mount point> <type> <options> <dump> <pass>
/dev/root / ext4 defaults 0 1
UUID=$SSD_UUID /mnt/ssd ext4 defaults,noatime,nofail,x-systemd.device-timeout=10 0 2
/mnt/ssd/birdlense/data /home/gfer/BirdLense/app/data none bind,nofail,x-systemd.requires=/mnt/ssd,x-systemd.after=/mnt/ssd 0 0
/mnt/ssd/birdlense/models /home/gfer/BirdLense/app/processor/models none bind,nofail,x-systemd.requires=/mnt/ssd,x-systemd.after=/mnt/ssd 0 0
/mnt/ssd/docker /var/lib/docker none bind,nofail,x-systemd.requires=/mnt/ssd,x-systemd.after=/mnt/ssd 0 0
/mnt/ssd/log/journal /var/log/journal none bind,nofail,x-systemd.requires=/mnt/ssd,x-systemd.after=/mnt/ssd 0 0
/mnt/ssd/apt-cache/archives /var/cache/apt/archives none bind,nofail,x-systemd.requires=/mnt/ssd,x-systemd.after=/mnt/ssd 0 0
EOF
```

**6.2 — создать точки монтирования** (пустые точки на SD, данные на SSD):

```bash
sudo mkdir -p \
  /mnt/ssd/birdlense/data/{recordings,db,dataset,.ultralytics} \
  /mnt/ssd/birdlense/models \
  /mnt/ssd/docker \
  /mnt/ssd/log/journal \
  /mnt/ssd/apt-cache/archives \
  "$BIRDLENSE_ROOT/app/data" \
  "$BIRDLENSE_ROOT/app/processor/models" \
  /var/log/journal \
  /var/cache/apt/archives
sudo chown -R "$USER:$USER" /mnt/ssd/birdlense "$BIRDLENSE_ROOT/app/data"
```

**6.3 — Tier B: journal на SSD** (лимит 200 МБ):

```bash
if [ -d /var/log/journal ] && [ ! -L /var/log/journal ]; then
  sudo systemctl stop systemd-journald.socket systemd-journald.service 2>/dev/null || true
  sudo rsync -aH /var/log/journal/ /mnt/ssd/log/journal/
  sudo rm -rf /var/log/journal
fi
sudo tee /etc/systemd/journald.conf.d/birdlense-ssd.conf >/dev/null <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=200M
RuntimeMaxUse=50M
EOF
sudo systemctl restart systemd-journald
```

**6.4 — Tier C (опционально): apt cache:**

```bash
grep -q birdlense-ssd-cache /etc/apt/apt.conf.d/* 2>/dev/null || sudo tee /etc/apt/apt.conf.d/99-birdlense-ssd-cache >/dev/null <<'EOF'
Dir::Cache "/mnt/ssd/apt-cache";
Dir::Cache::archives "/mnt/ssd/apt-cache/archives";
EOF
```

**6.5 — применить и проверить:**

```bash
sudo mount -a
touch "$BIRDLENSE_ROOT/app/data/db/.ssd_test" && ls /mnt/ssd/birdlense/data/db/.ssd_test
df -h / /mnt/ssd "$BIRDLENSE_ROOT/app/data" "$BIRDLENSE_ROOT/app/processor/models" /var/lib/docker /var/log/journal /var/cache/apt/archives
```

**Готово когда:** `df` для `app/data` показывает тот же девайс, что `/mnt/ssd`; тестовый файл виден под `/mnt/ssd/birdlense/data/`.

---

### Шаг 7. Проверить хранение после reboot

**Где:** Jetson.

```bash
sudo reboot
```

После входа:

```bash
df -h / /mnt/ssd ~/BirdLense/app/data ~/BirdLense/app/processor/models
mount | grep -E 'ssd|birdlense'
```

**Готово когда:**

| Проверка | Ожидание |
|----------|----------|
| `df /` | **mmcblk0** (SD), не SSD |
| `df ~/BirdLense/app/data` | **sda1** / nvme (SSD) |
| `df ~/BirdLense/app/processor/models` | SSD |
| `ls /mnt/ssd/birdlense/data/db` | каталог есть |

Если bind не поднялся: `sudo mount -a` и смотреть `journalctl -b | tail -50`.

---

### Шаг 8. Docker: NVIDIA runtime и data-root на SSD

**Где:** Jetson.

**Важно:** задать `data-root` **до** первого `docker pull` / `compose build`. Если Docker уже тянул образы на SD:

```bash
sudo systemctl stop docker docker.socket
sudo rsync -aH /var/lib/docker/ /mnt/ssd/docker/ 2>/dev/null || true
```

**Настройка:**

```bash
sudo usermod -aG docker "$USER"
sudo mkdir -p /etc/docker /mnt/ssd/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "data-root": "/mnt/ssd/docker",
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
newgrp docker   # или перелогиниться
```

**Готово когда:** `docker info --format '{{.DockerRootDir}}'` → `/mnt/ssd/docker`; `docker ps` без `sudo`.

---

### Шаг 9. Включить MAXN

**Где:** Jetson.

**Что сделать:**

```bash
# Важно: nvpmodel находится в /usr/sbin/, не в /usr/bin/
sudo tee /etc/systemd/system/jetson-performance.service >/dev/null <<'EOF'
[Unit]
Description=Jetson MAXN Performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nvpmodel -m 0
ExecStart=/usr/bin/jetson_clocks
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now jetson-performance
sudo nvpmodel -m 0  # или /usr/sbin/nvpmodel -m 0
sudo jetson_clocks
```

**Готово когда:** `sudo nvpmodel -q` показывает MODE 0 (MAXN); `jtop` (после `sudo apt install -y jetson-stats`) — GPU ~921 MHz, CPU ~1479 MHz, temp <80°C в idle.

---

### Шаг 10. ZRAM и headless

**Где:** Jetson.

**Что сделать:**

```bash
sudo apt update
sudo apt install -y zram-config

# Настроить размер ZRAM (50% RAM, алгоритм lzo)
sudo tee /etc/default/zram-config >/dev/null <<'EOF'
ZRAM_SIZE="50%"
ZRAM_ALGORITHM="lzo"
EOF

sudo systemctl enable zram-config
sudo systemctl restart zram-config
sudo systemctl set-default multi-user.target

# Отключить GUI (gdm) — освобождает RAM и GPU
sudo systemctl disable --now gdm 2>/dev/null || true
sudo systemctl mask gdm 2>/dev/null || true

# Базовые runtime/dev утилиты на Jetson
sudo apt install -y curl ca-certificates

# Perf tools:
# - tegrastats уже входит в JetPack/L4T
# - jtop + jetson_release даёт пакет jetson-stats
sudo apt install -y python3-pip
sudo -H pip3 install -U jetson-stats
sudo systemctl restart jtop.service 2>/dev/null || true

# Docker Compose v2 plugin для aarch64 (если `docker compose` отсутствует)
if ! docker compose version >/dev/null 2>&1; then
  curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64 \
    -o /tmp/docker-compose-linux-aarch64
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo install -m 0755 /tmp/docker-compose-linux-aarch64 /usr/local/lib/docker/cli-plugins/docker-compose
fi
```

**Готово когда:**
- `systemctl is-enabled zram-config` → `enabled`
- `cat /proc/swaps` показывает zram устройство
- `systemctl get-default` → `multi-user.target`
- `systemctl is-enabled gdm` → `masked` (GUI отключён)
- `command -v tegrastats jtop jetson_release` показывает пути
- `jetson_release` показывает JetPack/L4T, MAXN и `jtop: Service Active`
- `docker compose version` показывает Compose v2
- `command -v curl tree rsync docker` показывает пути

---

### Шаг 11. Проверить NVIDIA runtime, GStreamer и путь интеграции

**Где:** Jetson.

**Что сделать:**

```bash
# Проверить, что Docker видит GPU-устройства Nano.
# На l4t-base нет tegra-smi, поэтому проверяем /dev/nvhost-*.
docker run --rm --runtime nvidia nvcr.io/nvidia/l4t-base:r32.7.1 \
  bash -lc 'ls /dev/nvhost-gpu /dev/nvmap && echo OK'

# На хосте JetPack (или внутри будущего DeepStream-образа — шаг 13):
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc
gst-inspect-1.0 nvinfer      # DeepStream Primary GIE — обязателен для Plan A
gst-inspect-1.0 nvtracker    # NvDCF / IOU tracker
```

**Факт 2026-06-18:** без NGC auth на Jetson доступны `nvcr.io/nvidia/l4t-base:r32.7.1` и NVIDIA runtime devices. `deepstream-l4t:*`, `l4t-ml:*`, `l4t-pytorch:*` через `docker manifest inspect` вернули `Access Denied`. Поэтому текущий проверенный base для `Dockerfile.jetson` — **`nvcr.io/nvidia/l4t-base:r32.7.1`**; DeepStream (`nvinfer` / `nvtracker`) — отдельный gate: NGC login или native DeepStream SDK install.

**Готово когда:** Docker выводит `GPU_RUNTIME_OK`; `nvv4l2*` на хосте; для Plan A — `nvinfer` и `nvtracker` находятся после NGC auth/native DeepStream install. Если `nvinfer` нет — фиксировать **Plan B** в deployment notes.

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

### Шаг 12. Задать переменные окружения и синхронизировать runtime bundle

**Где:** dev-машина (`scripts/deploy.local.sh`) + Jetson.

**12.1 — env на dev:**

```bash
# scripts/deploy.local.sh
export BIRDLENSE_PLATFORM=jetson_nano
export DEPLOY_HOST="gfer@192.168.1.127"
export DEPLOY_URL="http://192.168.1.127:8085"
```

**12.2 — env на Jetson (`/home/gfer/BirdLense/app/.env`):**

```bash
BIRDLENSE_PLATFORM=jetson_nano
BIRDLENSE_INFERENCE_BACKEND=tensorrt
BIRDLENSE_BINARY_TENSORRT_PATH=models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine
BIRDLENSE_OPENVINO_BINARY_ENABLED=0
BIRDLENSE_CLASSIFIER_ENGINE=chriamue
BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND=onnxruntime
BIRDLENSE_PORT=8085
# GO2RTC_URL=http://<lan-ip-go2rtc>:1984  — LAN площадки, не копировать с VPS
```

**12.3 — синхронизировать только runtime allowlist, не весь репозиторий:**

```bash
cd /home/gfer/BirdLense

rsync -az --delete \
  --include='/AGENTS.md' \
  --include='/.dockerignore' \
  --include='/Makefile' \
  --include='/VERSION' \
  --include='/scripts/' \
  --include='/scripts/deploy.sh' \
  --include='/scripts/fetch_ornimetrics.sh' \
  --include='/scripts/export_yolo11n_detector_onnx.sh' \
  --include='/scripts/convert_ornimetrics_trt.sh' \
  --include='/scripts/platform-profile.sh' \
  --include='/scripts/export_fusion_training_data.py' \
  --include='/scripts/train_fusion.py' \
  --include='/scripts/diag_video_detect.py' \
  --include='/scripts/diag_coco_bird_frames.py' \
  --include='/scripts/benchmark-track-regen.py' \
  --include='/scripts/compare_detector_bboxes.py' \
  --include='/scripts/debug_ov_conversion.py' \
  --include='/scripts/validate_ov_parity.py' \
  --include='/scripts/patch_prod_nuclear_user_config.py' \
  --include='/scripts/benchmark_regen_labels.py' \
  --include='/scripts/catalog_deep_polish.py' \
  --include='/scripts/internal/' \
  --include='/scripts/internal/reid/' \
  --include='/scripts/internal/reid/run_daily_ssl_cycle.py' \
  --include='/app/' \
  --include='/app/.env.example' \
  --include='/app/Dockerfile.jetson' \
  --include='/app/docker-compose.yml' \
  --include='/app/docker-compose.jetson.yml' \
  --include='/app/Makefile' \
  --include='/app/app_config/***' \
  --include='/app/data/' \
  --include='/app/data/images/***' \
  --exclude='/app/data/***' \
  --include='/app/ebird_region_core.py' \
  --include='/app/nginx/***' \
  --include='/app/processor/' \
  --exclude='/app/processor/models/***' \
  --include='/app/processor/***' \
  --include='/app/scripts/***' \
  --include='/app/shared/***' \
  --include='/app/ui/dist/***' \
  --include='/app/web/***' \
  --exclude='*' \
  ./ gfer@192.168.1.127:/home/gfer/BirdLense/
```

**Важно по `--delete`:** allowlist должен сохранять mountpoints `app/data` и `app/processor/models`; содержимое этих путей исключено, потому что это SSD‑данные и веса. Перед первым запуском проверить `--dry-run`.

Overlay: `deploy/profiles/jetson-nano/config.overlay.yaml` остаётся на dev-машине; на Jetson попадает только итоговый runtime config.

**Готово когда:** `echo $BIRDLENSE_PLATFORM` на dev → `jetson_nano`; `DEPLOY_HOST`/`DEPLOY_URL` указывают на Jetson в LAN; `tree -L 2 /home/gfer/BirdLense` не показывает `docs`, `.github`, `datasets`, venv, `node_modules`, `site`.

---

### Шаг 13. Базовая сборка контейнера на Jetson

**Где:** Jetson, каталог `app/` репозитория.

**Базовый образ:** `docker-compose.jetson.yml` / `Dockerfile.jetson` должны соответствовать реально доступному JetPack/L4T stack. Не использовать `nvidia/cuda:*ubuntu20.04` на Nano — это не тот aarch64/L4T путь.

| Путь | Базовый образ | Когда |
|------|---------------|-------|
| **Plan B (текущий проверенный)** | `nvcr.io/nvidia/l4t-base:r32.7.1` | GPU devices + L4T userspace; GStreamer/TRT glue дорабатывается |
| **Plan A (целевой)** | `nvcr.io/nvidia/deepstream-l4t:6.2-base` / `6.2-samples` после NGC auth или native DeepStream SDK | Primary GIE + `nvinfer` + NvDCF |

> **Сейчас в репо:** `Dockerfile.jetson` = `nvcr.io/nvidia/l4t-base:r32.7.1` + micromamba `python=3.11` env (`numpy`, `opencv`, `onnxruntime`). Это честный L4T base без Debian/Bookworm smoke-слоя, без `docker commit` и без GLIBC mismatch с `/usr/lib/aarch64-linux-gnu/tegra`. Full runtime gate всё ещё зависит от detector TensorRT adapter в processor (#648/#651), не от torch/cpu fallback.

**Что сделать:**

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.jetson.yml config >/tmp/birdlense-compose-config.yml
```

Проверить в `docker-compose.jetson.yml` и образе:

- `restart: unless-stopped` — автоподъём после reboot/power glitch.
- `network_mode: host`; nginx слушает `BIRDLENSE_PORT` (обычно 8085). Не использовать bridge `8085:8080` для целевого Jetson profile.
- `docker compose ... config` проходит — compose plugin, env и YAML валидны.
- Внутри DeepStream-контейнера (после NGC auth/native DS): `gst-inspect-1.0 nvinfer` → OK для Plan A.

```bash
grep -E 'restart:|network_mode:' docker-compose.jetson.yml
docker compose exec birdlense gst-inspect-1.0 nvinfer 2>/dev/null || echo "Plan B или образ ещё без DeepStream"
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/health"
```

**Готово когда:** runtime bundle чистый; `docker compose ... config` OK; Docker root на SSD; GPU runtime OK; `docker compose ... up -d --build` поднимает web+processor без import crash loop; `cv2`, `numpy`, `onnxruntime` импортируются внутри контейнера; логи не содержат Intel/OpenVINO runtime noise. До реализации detector TRT adapter не считать production-ready и не заменять это torch/cpu fallback.

**Факт desk preflight (2026-06-18):**

- `docker compose -f docker-compose.yml -f docker-compose.jetson.yml config` проходит на Jetson.
- `DockerRootDir=/mnt/ssd/docker`, `DefaultRuntime=nvidia`.
- `docker run --rm --runtime nvidia nvcr.io/nvidia/l4t-base:r32.7.1 ...` видит `/dev/nvhost-gpu` и `/dev/nvmap`.
- `docker build -f app/Dockerfile.jetson ...` дошёл до Python layer и упал на `/bin/sh: 1: pip: not found`.
- Исторический desk smoke overlay поднял web/nginx, но удалён из target bundle; он не заменяет ML/RTSP gates.
- NUC `user_config.yaml` перенесён на Jetson без моков: `video.source=go2rtc`, `video.go2rtc_url=rtsp://192.168.1.11:554/stream`, Frigate triggers enabled. С рабочего стола Jetson `192.168.1.11:{1984,1883,554}` timeout — это site-pending до переноса в LAN площадки.

**Вывод:** железо и L4T/Docker runtime были готовы к переносу на площадку в preflight 2026-06-18. Source profile 2026-06-19 очищен от Debian smoke base, Intel env noise и torch/cpu final fallback. Полный app image не считать готовым до отдельного решения detector TensorRT adapter (#651/#648). Не чинить это установкой Ubuntu 18 `python3-pip` как финальным решением: это даст Python 3.6 и не соответствует текущим зависимостям Flask/Pydantic.

---

### Статус миграции (2026-06-22, ветка `jetson-nano`, хост `185.218.111.196:8080` NAT→8085)

**Конфиг:** `scripts/build_jetson_user_config.py` — VPS operational settings + `deploy/profiles/jetson-nano/config.overlay.yaml`, **strip Intel/OpenVINO**.

**Фактическое дерево весов на Jetson:**

```text
app/processor/models/
├── classification/chriamue_bird_species_classifier/
│   ├── config.json, model.onnx, model.safetensors, preprocessor_config.json
├── detection/trapper_ai_v02_2024/
│   ├── trapper_ai_v02_2024.pt, .onnx, .yaml [, .engine после trtexec]
├── reid/ornimetrics/reid_embedder.onnx
└── welfare/ornimetrics/embedder.onnx, welfare_scorer.npz
```

| Компонент | Backend | Статус |
|-----------|---------|--------|
| Trapper `.pt` / ONNX 704² | torch / TRT | **На устройстве** |
| Trapper `.engine` | TensorRT | **Собрать** `export_trapper_detector_trt.sh` на Jetson |
| chriamue classifier | ONNX CUDA | **Работает** (preprocess без HF на ORT) |
| Ornimetrics reid/welfare | ONNX CUDA | **На устройстве** |
| MQTT / Go2RTC / 2 cam | — | **Работает** (BirdBox, Forest) |
| UI settings password | — | **Работает** |

**Удалено с Jetson:** `detection/weights/` (Intel OV IR), `yolo11n.*`, Ornimetrics species packs, `.hef` — `jetson_models_prune.sh`.

### Статус миграции (архив 2026-06-20, flat layout `192.168.1.127`)

**Фактическое дерево на устройстве** (без подкаталога `weights/`):

```text
app/processor/models/
├── classification/chriamue_bird_species_classifier/
│   ├── config.json, model.onnx, model.safetensors, preprocessor_config.json
├── detection/trapper_ai_v02_2024/
│   ├── trapper_ai_v02_2024.pt, .onnx, .yaml
├── reid/ornimetrics/reid_embedder.onnx
└── welfare/ornimetrics/embedder.onnx, welfare_scorer.npz
```

Конфиги Hub (`user_config.yaml`, `.env`) и overlay в репозитории приведены к этому layout (2026-06-20).

| Компонент | Путь (flat layout) | Jetson `192.168.1.127` | Статус |
|-----------|----------------------|------------------------|--------|
| Trapper `.pt` / ONNX 704² | `detection/trapper_ai_v02_2024/` | synced | **Готово** |
| Trapper `.engine` | `detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine` | `trtexec` FP16 704² | **В процессе** (старый trtexec на `weights/` — после завершения пересобрать с flat paths) |
| Species classifier | `classification/chriamue_bird_species_classifier/` | `model.onnx` + safetensors | **Готово** ([chriamue/bird-species-classifier](https://huggingface.co/chriamue/bird-species-classifier), 525 видов) |
| Ornimetrics reid | `reid/ornimetrics/reid_embedder.onnx` | synced | **Готово** |
| Ornimetrics welfare | `welfare/ornimetrics/` | synced | **Готово** |
| Legacy `yolo11n.*`, ornimetrics species | — | удалено `jetson_models_prune.sh` | **Готово** |

Детектор: [OSCF/TrapperAI-v02.2024](https://huggingface.co/OSCF/TrapperAI-v02.2024) → ONNX **704²** (desk export) → FP16 `.engine` на Jetson. Классификатор: `classifier_engine: chriamue`, backend `onnxruntime`. Ornimetrics species packs **сняты** с Jetson.

Скрипты: `fetch_chriamue_classifier.sh`, `fetch_ornimetrics_jetson.sh` (только reid+welfare), `jetson_models_prune.sh`, `export_trapper_detector_trt.sh`.

---

### Шаг 14. Скачать Ornimetrics ONNX и собрать TensorRT на Jetson

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

**Факт 2026-06-19:** в публичном HF repo `Ornimetrics/ornimetrics-edge` на revision
`bd792c12d3bcf30f77be20d84a332e72193c67ba` файла `models/model_feeder4.onnx`
нет; доступен только `models/model_feeder4.hef` + `models/detector.names`. Для Jetson Nano
это reference-only Hailo artifact, не TensorRT input. До появления detector ONNX или
собственного export detector TRT остаётся blocker #650/#648; текущий recovery image
держит legacy/intermediate detector `models/detection/weights/best.pt`.

```bash
scripts/fetch_ornimetrics.sh /mnt/ssd/birdlense/models/classification/ornimetrics
```

Ожидаемый layout после скачивания: `species_classifier_*.onnx`, `embedder.onnx`, `reid_embedder.onnx`, `welfare_scorer.npz`, `species_classifier_nabirds.json`, `detector.names`. `.hef` намеренно не скачиваем как runtime artifact.

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
| `US` / `CA` | `species_classifier_nabirds` | 555 |
| иначе | `species_classifier_inat` | 302 |

Переключатель — **`ebird.country`** (тот же ключ, что `ebird_region_core._build_region_code`). Координаты lat/lon **не вычисляют** пакет сами — пользователь их уже задаёт для eBird; страна задаётся явно рядом. Override: `processor.ornimetrics_species_pack: auto|nabirds|inat`.

**Ограничение:** оба классификатора Ornimetrics — североамериканская таксономия. EU-площадка с `country: RU` получает CC-пакет (302) как компромисс «из коробки»; Birder EU-707 на Intel остаётся эталоном для Европы.

**BirdNET:** без изменений (MQTT hint).

**Готово когда:** `.engine` detector + classifier (pack по `ebird.country`) + welfare + reid на Jetson; parity зелёный.

**Detector 2026-06-19 (Jetson):** production path — **TrapperAI v02.2024** TensorRT @1024 (`scripts/export_trapper_detector_trt.sh`, `trtexec --fp16`). Ultralytics загружает `.engine` при `inference_backend: tensorrt`. Ornimetrics `model_feeder4.onnx` на HF нет (только Hailo `.hef`); species/welfare — Ornimetrics ONNX packs.

---

### Шаг 15. Benchmark на Jetson (gate перед камерами/deploy)

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

### Шаг 16. Настроить камеры в Hub

**Где:** `app/app_config/user_config.yaml` (на Jetson или через deploy).

**Что сделать:**

1. Две камеры: `feeder_close`, `feeder_far` в `video.cameras[]`.
2. Для каждой камеры:
   - **lores/detect** — прямой RTSP (substream 704×576, H.264, **~5–9 FPS**, типично **~7**).
   - **main/high-res** — через go2rtc (`rtsp://<go2rtc>:8554/...`), 1080p, 15–25 FPS.
3. Включить NTP на камерах; GOP 2–4 с.

**Готово когда:** в конфиге есть реальные URL обоих потоков для обеих камер; роли `tuning_role` заданы.

---

### Шаг 17. Проверить RTSP-потоки (NVMM + buffer tuning)

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

### Шаг 18. Финальный deploy

**Где:** dev-машина.

**Что сделать:**

```bash
cd /path/to/BirdLense
# deploy.local.sh уже с BIRDLENSE_PLATFORM=jetson_nano (шаг 12)
make deploy
```

**Готово когда:** `make deploy` без ошибки; health на `DEPLOY_URL` → OK.

---

### Шаг 19. Smoke после deploy

**Где:** Jetson + браузер/MCP.

**Desk preflight без камер (исторически выполнено 2026-06-18):**

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.jetson.yml config
```

Старый `docker-compose.jetson-smoke.yml` удалён. Web-only/processor-disabled запуск больше не считается целевым способом проверки; без detector `.engine` и native adapter Jetson ML gate остаётся красным, а не замещается smoke.

**Live smoke на площадке:**

1. Открыть `DEPLOY_URL` — UI доступен.
1. Дождаться события или вызвать тестовую запись.
1. Проверить метрики:

```bash
tegrastats --interval 1000 | head -30
# в Hub: yolo_frames_with_tracks > 0
# recording_session_summary: persist OK
```

1. Зафиксировать idle RAM/GPU 5 мин после старта (baseline для E10).

**Готово когда:** health OK; одна запись с persist в UI; `tegrastats` без throttle/OOM; треки появляются.

---

### Шаг 20. Recovery test (обрыв сети)

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

Источник: [Ornimetrics/ornimetrics-edge](https://huggingface.co/Ornimetrics/ornimetrics-edge). Jetson target: **ONNX → TensorRT**; `.hef` — для RPi5+Hailo-8, на Nano **reference-only**.

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
| `US` / `CA` | `species_classifier_nabirds` | 555 |
| иначе | `species_classifier_inat` | 302 |

Override: `processor.ornimetrics_species_pack: auto|nabirds|inat`. NA-таксономия; EU-707 Birder — на Intel. Welfare — перекалибровка healthy baseline на своих кропах ([caveats Ornimetrics](https://huggingface.co/Ornimetrics/ornimetrics-edge)).

### 3.1 Бюджет производительности (Nano 4 ГБ)

Ornimetrics на Hailo ~28 fps — **с NPU**. Nano без NPU; detect substream у нас **~5–9 FPS** (типично **~7**, см. `default_config` / Frigate lores), **строго <10 FPS** — не закладывать 10–15 FPS на lores.

Enrichment **только event-triggered** (охотник), не в live loop.

| Ресурс | MVP | При перегрузе |
|--------|-----|---------------|
| RAM | ≤3.0 ГБ | ring buffer ↓, ReID off |
| GPU | ≤85% | `interval+1` (до 5–6), detector 416→384 |
| CPU | ≤250% sustained (4 cores) | Plan B проще; меньше буферов |
| **Детектор** | см. шаг 15 | IOU tracker, interval+1 |
| Species | **цель** <100 ms p95 / кроп | **обязательно** defer async; 100–200 ms допустимо |
| Welfare + ReID | **цель** <50 ms p95 | welfare off → ReID off |
| Behavior E14 | **цель** <500 ms p95 / клип | off; X3D: 4→2 frames, 182→128 |

**Детектор — не «>10 FPS».** На 7 FPS lores + `interval=3` реально **~2.3 infer/s**. Gate: latency + не отставать от потока (шаг 15).

Video + bbox persist **не ждут** ML.

### 3.2 Скачивание весов (без Hailo)

Исполняется в **шаге 15**. Список файлов:

| Файл | Jetson |
|------|--------|
| `model_feeder4.onnx` | target, но отсутствует в HF repo на 2026-06-19 |
| `model_feeder4.hef` | скачан как reference-only; Nano без Hailo не использует |
| `species_classifier_{nabirds,inat}.onnx` + `.json` | один pack |
| `embedder.onnx`, `welfare_scorer.npz`, `reid_embedder.onnx` | да |
| прочие `*.hef` | **нет** |

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
| E0 | [#646](https://github.com/Gfermoto/BirdLense-Hub/issues/646) | 1–10 | SD+SSD storage, Docker, MAXN, ZRAM |
| E1 | [#647](https://github.com/Gfermoto/BirdLense-Hub/issues/647) | 11 | NVDEC/NVENC, GStreamer |
| E2 | [#648](https://github.com/Gfermoto/BirdLense-Hub/issues/648) | 11 | DeepStream сторож + NvDCF |
| E3 | [#649](https://github.com/Gfermoto/BirdLense-Hub/issues/649) | 11, 6.1 | Ring buffer + охотник |
| E4 | [#650](https://github.com/Gfermoto/BirdLense-Hub/issues/650) | 14 | Ornimetrics ONNX→TRT |
| E5 | [#651](https://github.com/Gfermoto/BirdLense-Hub/issues/651) | 12–13, 18 | Platform, deploy, CI |
| E6 | [#652](https://github.com/Gfermoto/BirdLense-Hub/issues/652) | 6.1 | Hub ingest adapter |
| E7 | [#653](https://github.com/Gfermoto/BirdLense-Hub/issues/653) | 16–20 | Field test 2 cam |
| E8 | [#654](https://github.com/Gfermoto/BirdLense-Hub/issues/654) | весь doc | Docs / ADR sync |
| E9 | [#655](https://github.com/Gfermoto/BirdLense-Hub/issues/655) | 17, 20 | RTSP reconnect |
| E10 | [#656](https://github.com/Gfermoto/BirdLense-Hub/issues/656) | 15, 6.11 | Perf budget, throttle |
| E11 | [#657](https://github.com/Gfermoto/BirdLense-Hub/issues/657) | 15, 6.10, 7 | Scientific benchmark |
| E12 | [#658](https://github.com/Gfermoto/BirdLense-Hub/issues/658) | 6.10 | FAIR / Camtrap DP |
| E13 | [#659](https://github.com/Gfermoto/BirdLense-Hub/issues/659) | 6.10, 7 | HITL review queue |
| E14 | [#660](https://github.com/Gfermoto/BirdLense-Hub/issues/660) | 3.3, 15 | Behavior X3D-XS deferred |

---

## 4. Справочник: камеры (детали к шагам 17–18)

| Поток | Назначение | Разрешение | FPS | Маршрут |
|-------|------------|------------|-----|---------|
| Substream / detect | DeepStream сторож | 704×576 | **5–9** (~7) | **прямой RTSP камеры** |
| Main | ring buffer + запись | 1080p | 15–25 | **через go2rtc** |

- Оба **H.264**, GOP 2–4 с, NTP на камере.
- `video.cameras[]`: `tuning_role: feeder_close|feeder_far`.

Исполнять: **шаг 16** (конфиг) → **шаг 17** (проверка gst-launch + buffer tune).

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
| Детектор | Trapper 1024² TRT (Jetson) | Trapper 704² OpenVINO (NUC) |
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
- **Усилено:** GStreamer pipeline tuning (zero-copy NVMM, leaky, num-extra-surfaces), NvDCF explicit config, runtime tegrastats enforcement, model conversion parity gate, **benchmark gate (шаг 15)**, **recovery test (шаг 20)**.
- **INT8** — только с калибровкой на полевых кропах; до parity FP16 не включать.

Итог: план заточен под 4 ГБ Nano — максимум hardware acceleration при жёстком контроле ресурсов и качества. Нет «магии», только проверенные практики + enforced degradation.

### 6.13 Yocto / custom minimal image — optional advanced (отложено)

Yocto даёт минимальный rootfs и контроль над kernel/device-tree, но:

- Высокая сложность поддержки (meta-jetson, L4T layers).
- JetPack 4.6.x + headless + ZRAM + **Tier A–B на SSD** (data, docker, models, journal) даёт достаточный запас RAM/износ для MVP без rootfs migration.
- **Решение:** Yocto рассматривать в E15+ только если после 24h soak на JetPack останутся проблемы с памятью/стабильностью или потребуется production-grade tamper-proof image.

Приоритет: сначала довести JetPack baseline до production quality, потом минимализм.

### 6.14 Внешняя рецензия (2026-06) — принятые риски и митигации

| Риск | Вероятность | Митигация в плане |
|------|-------------|-------------------|
| DeepStream ↔ Python интеграция | **высокая** | Plan B (appsink + TRT); ×2–3 время E1–E3; шаг 11 |
| Ornimetrics TRT RAM на 4 ГБ | средняя | отдельные `.engine`, welfare/ReID defer при overload; шаг 14–15 |
| NVDEC bottleneck (2× RTSP) | средняя | `tegrastats` NVDEC; снизить substream FPS; шаг 11 |
| SSD/bind не поднялся после reboot | средняя | `nofail` + `mount -a`; шаг 7; SSD подключать до power-on |
| Buffer starvation / jitter | средняя | `num-extra-surfaces=2`, leaky queue; шаг 17 |
| Нет benchmark перед боем | — | шаг 15: cadence + p95, не «>10 FPS» |
| Нет recovery test | — | шаг 20: RTSP reconnect без restart контейнера |

**Не в MVP (backlog):** адаптивный interval в коде (6.11, #656), API сброса буферов (шаг 20, #655), fused TRT backbone (#650).

### 6.15 Научный контур продукта (E11–E13)

Jetson-план совместим с полевым протоколом для заповедников и citizen science — не отдельный «research fork», а gates в том же runbook:

| Принцип | Где в плане | Issue |
|---------|-------------|-------|
| Воспроизводимость (версии, hashes, config snapshot) | §6.10, шаг 15 CSV | #657 |
| Golden clips + parity ONNX↔TRT | §6.6, шаг 15 | #657, #650 |
| Uncertainty (confidence, margin, hints ≠ истина) | §6.2.2, §6.10 | #659 |
| HITL / review queue | §6.10, чек-лист §7 | #659 |
| FAIR export (Camtrap DP, DwC) | §6.10 | #658 |
| Ethics (person/dog ≠ biodiversity record) | §6.10, детектор Ornimetrics | — |
| 24h soak + recovery | шаги 19–20, §7 | #653, #655 |

**Порядок:** operational gates (шаг 15) **до** полевого деплоя; полный scientific bundle (#657) — после 2-cam soak, перед публикацией/обменом данными.

### 6.16 Внешнее ревью (2026-06, rev.4) — принято

| Рекомендация | Решение в плане |
|--------------|----------------|
| Lores **<10 FPS** на площадке | Gate **cadence + p95**, не >10 FPS infer (шаг 15, §3.1) |
| Species <100 ms может быть жёстко | **Цель**; defer async обязателен; hard <200 ms |
| Plan B раньше Plan A | Шаг 12: **B = прототип**, A = production |
| X3D-XS — `trtexec` до поля | Шаг 16 п.7; fallback 2 frames / 128² |
| CPU ≤250% в мониторинг | §6.11, шаг 15 CSV |
| `nvinfer` только в DeepStream 6.2 | Шаги 11, 13 |
| go2rtc — где крутится | §5.1, шаг 12 `GO2RTC_URL` |
| Первые действия на железе | TRT convert → benchmark 16 → решение Orin |

---

## 7. Чек-лист перед боем на площадке

### 7.0 Desk preflight — можно выполнить дома, без камер

Фактически выполнено 2026-06-18 на Jetson Nano B01 (`192.168.1.127`):

- [x] Reboot resilience: SSH вернулся после reboot примерно за 1 минуту.
- [x] Headless: `gdm` inactive/masked, default target `multi-user`.
- [x] MAXN: `jetson_release` показывает `NV Power Mode [0]: MAXN`.
- [x] ZRAM: 4× zram по ~506 MB, disk swap отсутствует.
- [x] SSD binds после reboot: `/mnt/ssd`, `app/data`, `processor/models`, `/var/lib/docker`, `/var/log/journal`, `/var/cache/apt/archives` на `/dev/sda1`.
- [x] SSD hygiene: старый rootfs-мусор удалён; top-level только `apt-cache`, `birdlense`, `docker`, `log`, `lost+found`.
- [x] Runtime bundle hygiene: `/home/gfer/BirdLense` около 30 MB; нет `docs/`, `.github/`, `datasets/`, venv, `node_modules`, `site`.
- [x] Tools: `docker`, `docker compose`, `curl`, `tree`, `rsync`, `tegrastats`, `jtop`, `jetson_release`, `nvpmodel`, `jetson_clocks`.
- [x] Compose syntax: `docker compose -f docker-compose.yml -f docker-compose.jetson.yml config` OK.
- [x] GPU runtime: `l4t-base:r32.7.1` видит `/dev/nvhost-gpu` и `/dev/nvmap`.
- [x] Исторический desk smoke подтвердил web/nginx shell, но smoke overlay удалён из target source bundle.
- [x] NUC settings transfer: `user_config.yaml` перенесён без моков; `.env` содержит production secrets; target Jetson profile задаёт `BIRDLENSE_PORT=8085` для host network.
- [x] Site deps classified: `192.168.1.11:{1984,1883,554}` timeout на столе, значит go2rtc/MQTT/RTSP остаются site-pending до переноса в LAN площадки.
- [x] Idle baseline: RAM ~334–479/3956 MB, swap 0, temp CPU/GPU ~30–31°C на столе.

Статус source-clean pass (2026-06-19):

- [x] `Dockerfile.jetson` возвращён на L4T base `nvcr.io/nvidia/l4t-base:r32.7.1`; Python/runtime deps идут через micromamba env, а не через Debian Bookworm image, `docker commit` или Ubuntu 18 `python3-pip`.
- [x] Jetson profile очищен от Intel/OpenVINO runtime path: `BIRDLENSE_INFERENCE_BACKEND=tensorrt`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=0`, `BIRDLENSE_CLASSIFIER_ENGINE=ornimetrics`, `BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND=onnxruntime`.
- [x] Compose target — `network_mode: host`, `BIRDLENSE_PORT=8085`, NVIDIA runtime, no `BIRDLENSE_INTEL_*` env.
- [x] Добавлен resolver contract для `processor.models.binary_tensorrt` / `BIRDLENSE_BINARY_TENSORRT_PATH`; `.engine` считается валидным detector artifact. TensorRT detector loader пока fail-fast, без Hailo `.hef` и без torch/cpu fallback.
- [x] Ornimetrics species selector: `processor.ornimetrics_species_pack: auto|nabirds|inat`; `auto` выбирает `nabirds` для `ebird.country` `US`/`CA`, иначе `inat`.
- [x] Добавлены scripts: `fetch_ornimetrics.sh` (без `.hef`, flatten ONNX sidecars), `export_yolo11n_detector_onnx.sh`, `convert_ornimetrics_trt.sh` (`trtexec`, FP16, hash manifest).
- [x] Добавлен root `.dockerignore`: `app/data`, `app/processor/models`, UI `node_modules`/old dirs, docs/dev artifacts не попадают в Docker build context.
- [ ] Build validation 2026-06-19: первая попытка упала на 404 micromamba pinned URL; Dockerfile исправлен на `latest`. Вторая попытка не дошла до Dockerfile из-за раздутого context (>330 MB, до добавления `.dockerignore`) и после stop Jetson временно пропал из сети (`No route to host`). Повторить `docker compose ... build birdlense` после восстановления SSH и синхронизации `.dockerignore`.
- [x] Jetson MVP detector: **TrapperAI v02.2024** (`trapper_ai_v02_2024.pt` → ONNX `imgsz=704` → FP16 `trapper_ai_v02_2024.engine`); классы — `detection/trapper_ai_v02_2024/trapper_ai_v02_2024.yaml`. Ornimetrics `model_feeder4.onnx` на HF по-прежнему нет (только `.hef`).
- [ ] Validation blocker: на момент source-clean pass Jetson `192.168.1.127:22` снова не отвечал (`No route to host`), поэтому fresh remote build/health/log validation не завершены в этом проходе.

### 7.1 Site transfer checklist — делать при переносе на площадку

- [ ] Подключить тот же SSD до power-on; после boot: `df -h / /mnt/ssd /var/lib/docker ~/BirdLense/app/data`.
- [ ] Проверить питание barrel jack 5V/4A и активный вентилятор; `tegrastats` idle 5 мин.
- [ ] Подтвердить LAN IP/SSH: либо сохранить `192.168.1.127`, либо обновить `DEPLOY_HOST` / `DEPLOY_URL`.
- [ ] Подтвердить, что NUC LAN адреса `192.168.1.11` доступны с Jetson на площадке: `1984` (go2rtc), `1883` (MQTT), `554` (RTSP). Сейчас на столе они перенесены, но недоступны.
- [ ] Проверить `gst-inspect-1.0 nvv4l2decoder` и `nvv4l2h264enc` на устройстве после финальной сети.
- [ ] Прогнать каждый lores RTSP через `gst-launch-1.0` ≥5 минут: stutter, зелёные блоки, latency.
- [ ] Проверить main/high-res через go2rtc, если go2rtc будет отдельным хостом.
- [ ] Только после RTSP gates — запускать live Hub/deploy smoke.

Соответствие runbook:

- [ ] **Шаги 1–2:** БП 5V/4A, вентилятор, SSD, SD с JetPack записана
- [ ] **Шаги 3–7:** SSH, JetPack, SSD layout + bind-mounts, `df /` → **SD**, `df app/data` → **SSD**
- [ ] **Шаги 8–11:** Docker data-root на SSD, MAXN, ZRAM/headless, `gst-inspect` OK, путь DS vs Plan B зафиксирован
- [ ] **Шаги 12–14:** env, build (`restart: unless-stopped`, host network), Ornimetrics `.engine` + parity
- [ ] **Шаг 15:** benchmark (#656): lores FPS записан, YOLO p95 <100 ms, cadence ≥ stream/interval×0.9
- [ ] **Шаги 16–17:** камеры, RTSP NVMM ≥5 мин
- [ ] **Шаги 18–19:** deploy, smoke, `yolo_frames_with_tracks > 0`, idle RAM
- [ ] **Шаг 20:** recovery без restart контейнера
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
| Bind-mount / SSD отвалился | `sudo mount -a`; проверить USB; шаг 7 |
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
