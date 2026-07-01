# Orin NX / NANO — runbook BirdLense Hub

**Статус:** ветка `orin`, ONNX GPU (CUDA EP), без OpenVINO/Intel  
**Платформы:** Orin NX 16GB (песочница) → Orin NANO 8GB (production)  
**Хранилище:** один загрузочный диск **M.2 NVMe** — отдельного SSD для данных **нет** (записи и Docker на том же NVMe)

**Модельный стек (ветка `orin`):**

| Компонент | Модель | Формат | Бэкенд |
|-----------|--------|--------|--------|
| Детектор | Trapper AI v02 2024 | ONNX | ONNX Runtime CUDA EP |
| Классификатор | Birder ConvNeXt EU-707 (birder_eu) | PyTorch → ONNX | ONNX Runtime CUDA EP |
| ReID | Ornimetrics `reid_embedder` | ONNX | ONNX Runtime CUDA EP |
| Welfare | Ornimetrics embedder + `welfare_scorer.npz` | ONNX + NPZ | ONNX Runtime CUDA EP |
| Трекер | ByteTrack / BotSORT | YAML | CPU |

**Исполнять:** §2 сверху вниз. §3–7 — справочник и тюнинг.

---

## 1. Что в ветке `orin`

Ключевые артефакты (остальное — как в Hub: `web/`, `ui/`, `app_config/`):

```
app/
├── Dockerfile.orin              # aarch64, Python 3.12, onnxruntime-gpu
├── docker-compose.orin.yml      # nvidia runtime, host network, NVENC capture
├── Makefile                     # BIRDLENSE_PLATFORM=orin по умолчанию
├── app_config/
│   └── user_config.orin.example.yaml
└── processor/models/            # веса в .gitignore — копируются вручную
    ├── detection/trapper_ai_v02_2024/
    │   └── trapper_ai_v02_2024.onnx
    ├── reid/ornimetrics/reid_embedder.onnx
    ├── welfare/ornimetrics/
    │   ├── embedder.onnx
    │   └── welfare_scorer.npz
    ├── classification/convnext_v2_tiny_eu-common256px/
    │   ├── convnext_v2_tiny_eu-common256px.onnx
    │   └── class_labels.txt
    └── tracker/                   # bytetrack_birdlense.yaml, botsort_birdlense.yaml
```

Классификатор — ONNX Birder EU-707: `scripts/download_birder_classifier.py --export-onnx`.  
Деплой с dev-машины: `make deploy` (rsync + `make build` + `make start` на Orin).  
Сборка на самом Orin: `make local-build && make start` (нужен Node 22 для UI).

---

## 2. Runbook — развёртывание на Orin (M.2 boot)

| Шаг | Где | Суть |
|-----|-----|------|
| 1 | Host PC (x86, Ubuntu) | Прошить **JetPack 6** сразу на **M.2 NVMe** (SDK Manager) |
| 2 | Orin | Первый boot, пользователь, hostname, SSH |
| 3 | Orin | `apt` + `nvidia-jetpack`, проверка `R36.x` |
| 4 | Orin | Проверить, что **root на NVMe** (`lsblk`, `df`) |
| 5 | Orin | Docker + `nvidia-container-runtime` |
| 6 | Orin | Тюнинг: MAXN, `jetson_clocks`, ZRAM, headless (§4) |
| 7 | Orin / dev | Клон `orin`, веса ONNX, `.env`, `user_config.yaml` |
| 8 | Orin | `make local-build` или `make deploy` с dev |
| 9 | Orin | Smoke: health, CUDA providers, камера |
| 10 | Orin | Полный пайплайн: треки в `recording_session_summary` |

### Шаг 1. Прошивка JetPack 6 на M.2 NVMe

На **host PC** (Ubuntu 20.04/22.04 x86_64):

1. Установить [NVIDIA SDK Manager](https://developer.nvidia.com/sdk-manager).
2. Подключить Orin по USB (recovery) или по сети — по [Flashing Guide JP6](https://docs.nvidia.com/jetson/archives/r36.4/DeveloperGuide/SD/FlashingSupport.html).
3. В SDK Manager выбрать **JetPack 6.x**, целевую плату (**Orin NX** или **Orin NANO**).
4. В разделе storage указать **NVMe (M.2)** как целевой носитель — **не** SD + перенос на «второй SSD».
5. Дождаться окончания flash, отключить recovery, загрузиться с NVMe.

> Отдельного SATA/USB SSD в этой схеме нет: один M.2 — и ОС, и Docker, и `app/data/recordings/`. Следите за `df -h /`.

### Шаг 2. Первый boot

OEM wizard (или headless через serial):

- пользователь: `gfer` (или свой)
- hostname: `birdlense-orin`
- SSH: `sudo systemctl enable ssh --now`

### Шаг 3. Базовая система

```bash
ssh gfer@birdlense-orin
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y nvidia-jetpack git curl
sudo reboot
```

**Готово когда:** `cat /etc/nv_tegra_release` → `R36.x` (JetPack 6), `nvidia-smi` без ошибок.

### Шаг 4. Проверка диска (только M.2)

```bash
lsblk -f
df -h /
```

Ожидается: `nvme0n1` (или аналог) смонтирован как `/`.  
Нет второго диска под root — **шаги «разметить SSD / rsync rootfs» не нужны**.

Рекомендация для одного NVMe (опционально, в `/etc/fstab` для `/`):

```text
defaults,noatime
```

Оставить запас ≥30 GB под Docker-слои и записи (`app/data/recordings/`).

### Шаг 5. Docker + NVIDIA runtime

```bash
# JetPack 6 обычно уже ставит nvidia-container-toolkit; если нет — пакет из репозитория NVIDIA.
sudo usermod -aG docker "$USER"
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
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
newgrp docker
docker run --rm --runtime=nvidia nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### Шаг 6. Тюнинг Orin (см. §4)

```bash
sudo nvpmodel -m 0          # MAXN (для NANO 8GB см. §4.2)
sudo jetson_clocks
sudo apt install -y zram-config && sudo systemctl enable zram-config
sudo systemctl set-default multi-user.target   # без GUI
```

### Шаг 7. Репозиторий, веса, конфиг

```bash
cd /home/gfer
git clone --branch dev git@github.com:Gfermoto/BirdLense-Hub.git BirdLense
cd BirdLense/app

cp app_config/user_config.orin.example.yaml app_config/user_config.yaml
bash scripts/setup-orin.sh
```

**Веса** (не в git) — положить на Orin в те же пути, что в `docker-compose.orin.yml` volumes:

| Файл | Путь на хосте |
|------|----------------|
| Trapper ONNX | `processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx` |
| Birder classifier ONNX | `processor/models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx` |
| Birder labels | `processor/models/classification/convnext_v2_tiny_eu-common256px/class_labels.txt` |
| ReID | `processor/models/reid/ornimetrics/reid_embedder.onnx` |
| Welfare | `processor/models/welfare/ornimetrics/embedder.onnx`, `welfare_scorer.npz` |

Скачать классификатор (на dev-машине или Orin):

```bash
python3 scripts/download_birder_classifier.py --export-onnx
# или всё сразу:
bash scripts/fetch-processor-models-orin.sh
```

С dev-машины можно `rsync` каталоги `processor/models/` (как при `make deploy`, без перезаписи `app/data/`).

### Шаг 8. Сборка и запуск

**На Orin** (нужен Node 22: `nvm use` в `ui/`):

```bash
cd /home/gfer/BirdLense/app
export BIRDLENSE_PLATFORM=orin
make local-build    # ui build + docker build
make start
```

**С dev-машины** (UI уже собран локально):

```bash
# scripts/deploy.local.sh: DEPLOY_HOST=birdlense-orin, BIRDLENSE_PLATFORM=orin
cd /path/to/BirdLense && make deploy
```

**Готово когда:** `docker ps` → `birdlense` и `birdlense-redis` в статусе `Up`.

### Шаг 9. Smoke-тест

```bash
curl -sf http://localhost:8085/api/ui/health

docker exec birdlense python3 -c "
import onnxruntime as ort
print(ort.get_available_providers())
"
# Ожидается: CUDAExecutionProvider, CPUExecutionProvider
```

### Шаг 10. Камеры и пайплайн

1. UI → Settings → Cameras: RTSP URL, логин/пароль.
2. System → «Сканировать и импортировать» (если записи с Frigate/NVR).
3. Метрика: в сводке сессии `yolo_frames_with_tracks > 0`.

---

## 3. Модели и инференс

### 3.1 Пути и бэкенды

- Детектор: `processor.models.binary` → ONNX Trapper.
- Классификатор: `classifier_engine: birder_eu`, ONNX `weights/{variant}.onnx` + bundle `{variant}/class_labels.txt`.
- ReID: `processor.models.reid_embedder`, `processor.reid.*` (см. `user_config.orin.example.yaml`).
- Welfare: `welfare_runtime.py` в finalize после ReID; модели в `processor/models/welfare/ornimetrics/` (volume в compose). Порог: `processor.welfare.distance_review_threshold`.

OpenVINO, Intel GPU, TensorRT и Jetson Nano legacy в ветке `orin` **не используются**.

### 3.2 Проверка CUDA внутри контейнера

```bash
docker exec birdlense python3 <<'PY'
import onnxruntime as ort
s = ort.InferenceSession(
    "/app/processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx",
    providers=["CUDAExecutionProvider"],
)
print("providers:", s.get_providers())
PY
```

---

## 4. Оптимизация под Orin

### 4.1 Orin NX 16GB (песочница)

| Параметр | Рекомендация |
|----------|----------------|
| Power | `sudo nvpmodel -m 0` + `sudo jetson_clocks` |
| Docker | `docker-compose.orin.yml`: `shm_size: 1gb`, `memory: 14G` — ок для 16GB |
| Детектор | `binary_imgsz: 640` (баланс); 704 если Trapper экспортирован под 704 |
| Захват RTSP | `BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi` (NVDEC, уже в compose) |
| Инференс | `BIRDLENSE_INFERENCE_BACKEND=onnxruntime`, `BIRDLENSE_INFERENCE_DEVICE=cuda:0` |
| Записи | тот же NVMe — периодически чистить старые `app/data/recordings/` |

### 4.2 Orin NANO 8GB (production)

| Параметр | Рекомендация |
|----------|----------------|
| Power | `nvpmodel` — режим с меньшим TDP, если греется; иначе MAXN краткими сессиями |
| RAM | **обязательно** ZRAM; в `docker-compose.orin.yml` снизить `deploy.resources.limits.memory` до **~6G** |
| Детектор | `binary_imgsz: 640`, один поток камеры до стабилизации |
| Классификатор | `max_classifications_per_frame: 2` в `user_config` |
| Диск | один M.2 — жёсткий лимит retention записей (System / политика хранения) |

### 4.3 Захват и кодирование (в compose уже задано)

```bash
BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi   # аппаратный decode RTSP
BIRDLENSE_ENCODING=orin                  # профиль медиа-пайплайна под Jetson
```

### 4.4 Процессор (`user_config.yaml`)

Стартовая точка — `user_config.orin.example.yaml`:

```yaml
processor:
  models:
    binary: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
    classifier: models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx
    reid_embedder: models/reid/ornimetrics/reid_embedder.onnx
  classifier_engine: birder_eu
  inference_backend: onnxruntime
  classifier_inference_backend: onnxruntime
  inference_device: cuda:0
  binary_imgsz: 704
  min_confidence_binary: 0.12
  merge_window_seconds: 12
  reid:
    device: cuda:0
    inference_backend: onnxruntime
```

После правки `user_config.yaml`: `docker compose -f docker-compose.yml -f docker-compose.orin.yml up -d --force-recreate birdlense`.

### 4.5 Мониторинг

```bash
sudo apt install -y python3-pip && sudo pip3 install jetson-stats
sudo jtop    # CPU/GPU/RAM/NVMe temp
```

---

## 5. Переменные окружения (`app/.env`)

Минимум для Orin (дополняет `docker-compose.orin.yml`):

```bash
BIRDLENSE_PORT=8085
BIRDLENSE_PLATFORM=orin
BIRDLENSE_INFERENCE_BACKEND=onnxruntime
BIRDLENSE_INFERENCE_DEVICE=cuda:0
BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi
BIRDLENSE_ENCODING=orin

FLASK_SECRET_KEY=<32-char-hex>
PROCESSOR_SECRET=<32-char-hex>
MCP_TOKEN=<token>
```

Production: `BIRDLENSE_ENV=production`.  
При задании пароля в `user_config.yaml:general.settings_password` — система запросит авторизацию.  
Пока пароль не задан — свободный вход (даже в production).

---

## 6. Ориентиры по производительности

| Метрика | Orin NX 16GB | Orin NANO 8GB |
|---------|--------------|---------------|
| GPU | 1024-core Ampere | 1024-core Ampere |
| RAM | 16 GB | 8 GB |
| Детектор 640² | >25 FPS (ORT CUDA) | >15 FPS |
| Классификатор / кроп | <50 ms | <80 ms |
| NVENC/NVDEC | да | да |
| Диск | один NVMe | один NVMe |

Цифры зависят от числа камер, `binary_imgsz`.

---

## 7. Чек-лист перед production

- [ ] JetPack 6 (`R36.x`), `nvidia-smi` на хосте и в контейнере
- [ ] Root на **M.2 NVMe**, запас места на диске ≥30 GB
- [ ] Docker `default-runtime: nvidia`
- [ ] `nvpmodel` + `jetson_clocks`; на NANO — ZRAM и лимит памяти контейнера ~6G
- [ ] Веса ONNX на месте (§2 шаг 7)
- [ ] `user_config.yaml` из `user_config.orin.example.yaml`, без ключей `openvino_*`
- [ ] `.env` с секретами
- [ ] `BIRDLENSE_PLATFORM=orin make build && make start` (или `make deploy`)
- [ ] `curl -sf http://localhost:8085/api/ui/health`
- [ ] `onnxruntime.get_available_providers()` содержит `CUDAExecutionProvider`
- [ ] Камера(ы) в UI, `yolo_frames_with_tracks > 0`

---

## 8. Миграция с Intel / Jetson Nano

Ветка `orin` **не** совместима с `user_config` от OpenVINO/Intel NUC или Jetson Nano (torch worker, `binary_openvino`, `jetson_nano` platform).  
Перенос: новый `user_config.yaml` из example, веса ONNX, деплой ветки `orin` — без rsync старых IR/OpenVINO каталогов.