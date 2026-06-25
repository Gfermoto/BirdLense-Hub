# Orin NX / NANO — runbook и архитектура BirdLense Hub

**Статус:** ONNX GPU (CUDA EP / TensorRT EP), Trapper + Birder + Ornimetrics (2026-06-25)  
**Исполнять:** §2 (шаги 1–18) сверху вниз. §3–6 — справочник.  
**Целевые платформы:** Orin NX 16GB (песочница) → Orin NANO 8GB (production).  
**Модельный стек:**

| Компонент | Модель | Формат | Бэкенд |
|-----------|--------|--------|--------|
| Детектор | Trapper AI v02 2024 | ONNX | ONNX Runtime CUDA EP / TensorRT EP |
| Классификатор | Birder ConvNeXt EU-707 (chriamue) | ONNX | ONNX Runtime CUDA EP |
| ReID | Ornimetrics reid_embedder | ONNX | ONNX Runtime CUDA EP |
| Welfare | Ornimetrics embedder + welfare_scorer.npz | ONNX + NPZ | ONNX Runtime CUDA EP |
| Трекер | BotSORT / ByteTrack | YAML-конфиги | CPU (боксы) |
| Behavior | Logistic ONNX + meta/video | ONNX | ONNX Runtime CPU |

---

## 1. Состав ветки `orin`

```
BirdLense/
├── app/
│   ├── Dockerfile.orin          # Сборка под Orin (Python 3.12, onnxruntime-gpu)
│   ├── docker-compose.orin.yml  # Override: nvidia runtime, host network, privileged
│   ├── docker-compose.yml       # Базовый compose (Redis + birdlense)
│   ├── Makefile                 # build / start / stop / logs / test
│   ├── scripts/
│   │   ├── entrypoint.sh        # Orin: без DRM/DRI, без py3.6 worker
│   │   ├── deploy.sh
│   │   ├── deploy.local.sh.example
│   │   ├── verify-stack.sh
│   │   ├── verify-prod-env.sh
│   │   ├── platform-profile.sh
│   │   ├── wait-hub-http.sh
│   │   ├── restore-config.sh
│   │   └── esphome/             # Кормушка (сохранена)
│   ├── processor/
│   │   ├── src/                 # Основной код процессора
│   │   └── models/
│   │       ├── detection/trapper_ai_v02_2024/
│   │       │   ├── trapper_ai_v02_2024.onnx    # Детектор ONNX
│   │       │   ├── trapper_ai_v02_2024.yaml
│   │       │   └── class_maps/
│   │       ├── classification/chriamue_bird_species_classifier/
│   │       │   ├── model.onnx                   # Классификатор ONNX
│   │       │   ├── config.json
│   │       │   ├── preprocessor_config.json
│   │       │   └── class_names.txt
│   │       ├── reid/ornimetrics/
│   │       │   └── reid_embedder.onnx           # ReID ONNX
│   │       ├── welfare/ornimetrics/
│   │       │   ├── embedder.onnx                # Welfare ONNX
│   │       │   └── welfare_scorer.npz
│   │       ├── tracker/                         # YAML-конфиги трекера
│   │       └── behavior/                        # Поведение ONNX
│   ├── web/                     # Flask API
│   ├── app_config/
│   │   ├── default_config.yaml
│   │   └── user_config.orin.example.yaml        # Шаблон под Orin (не трекается)
│   └── ui/                      # React 19 + MUI
├── docs/
│   ├── strategy/orin-setup-and-migration.md     # Данный документ
│   ├── user/troubleshooting.md
│   ├── user/configuration.md
│   ├── user/install.md
│   ├── user/quickstart.md
│   ├── user/overview.md
│   ├── CONFIGURATION.md
│   ├── INSTALL.md
│   ├── OVERVIEW.md
│   ├── QUICKSTART.md
│   └── TROUBLESHOOTING.md
├── esphome/                    # ESPHome кормушка
├── Makefile                    # deploy / build / start / stop / logs / verify
├── .gitignore
├── .nvmrc
├── AGENTS.md
├── install.sh
└── LICENSE
```

---

## 2. Runbook — порядок развёртывания

| Шаг | Где | Суть |
|-----|-----|------|
| 1–2 | dev / хост | Подготовить JetPack 6 SD-образ, записать, загрузиться |
| 3–4 | Orin по SSH | Настроить SSH, apt update/upgrade |
| 5–6 | Orin | Разметить SSD, перенести rootfs |
| 7–8 | Orin | Защитить загрузку с SSD, настроить Docker + NVIDIA runtime |
| 9–10 | Orin | MAXN / jetson_clocks, ZRAM / headless |
| 11–12 | dev → Orin | Склонировать ветку `orin`, создать `.env`, настроить `user_config.yaml` |
| 13–14 | Orin | `make build && make start`, smoke-тест |
| 15–16 | Orin | Развернуть ONNX-модели (подробнее §3), проверить GPU |
| 17–18 | Orin / dev | Настроить камеры, запустить полный пайплайн |

### Шаг 1. Подготовить SD-карту

Скачать JetPack 6 для Orin NX/NANO с [nvidia.com](https://developer.nvidia.com/embedded/jetpack), записать `balenaEtcher` или `dd`.

### Шаг 2. Первый boot

Подключить питание, монитор, клавиатуру. Пройти OEM wizard:
- пользователь: `gfer` (или ваш)
- hostname: `birdlense-orin`

Включить SSH: `sudo systemctl enable ssh --now`

### Шаг 3. SSH и обновление

```bash
ssh gfer@birdlense-orin
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y nvidia-jetpack
sudo reboot
```

**Готово когда:** после reboot `cat /etc/nv_tegra_release` показывает `R36.x` (JP6).

### Шаг 4. Разметить SSD

```bash
lsblk
sudo parted /dev/nvme0n1 mklabel gpt
sudo parted /dev/nvme0n1 mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L birdlense-data /dev/nvme0n1p1
```

### Шаг 5. Перенести rootfs на SSD

```bash
sudo mkdir -p /mnt/ssd && sudo mount /dev/nvme0n1p1 /mnt/ssd
sudo rsync -aAXv --exclude={"/mnt/*","/proc/*","/sys/*","/dev/*","/run/*","/tmp/*","/lost+found"} / /mnt/ssd/
SSD_PARTUUID=$(blkid -s PARTUUID -o value /dev/nvme0n1p1)
echo "PARTUUID=${SSD_PARTUUID}  /  ext4  defaults,noatime  0  1" | sudo tee -a /mnt/ssd/etc/fstab
sudo sed -i "s|root=[^ ]*|root=PARTUUID=${SSD_PARTUUID}|" /boot/extlinux/extlinux.conf
sudo reboot
```

**Готово когда:** `df -h /` показывает NVMe SSD.

### Шаг 6. Docker с NVIDIA runtime

```bash
sudo usermod -aG docker "$USER"
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

### Шаг 7. MAXN и производительность

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks
sudo apt install -y zram-config && sudo systemctl enable zram-config
sudo systemctl set-default multi-user.target
```

### Шаг 8. Клонировать ветку `orin`

```bash
cd /home/gfer
git clone --branch orin git@github.com:Gfermoto/BirdLense-Hub.git BirdLense
cd BirdLense
cp app/app_config/user_config.orin.example.yaml app/app_config/user_config.yaml
cp app/.env.example app/.env  # если есть
```

### Шаг 9. Сборка и запуск

```bash
cd BirdLense
BIRDLENSE_PLATFORM=orin make build
BIRDLENSE_PLATFORM=orin make start
```

**Готово когда:** `docker ps` показывает `birdlense` и `birdlense-redis` оба `Up`.

### Шаг 10. Проверка GPU и детекции

```bash
# Проверить, что ONNX видит CUDA
docker exec birdlense python3 -c "import onnxruntime; print(onnxruntime.get_available_providers())"
# Ожидается: ['CUDAExecutionProvider', 'TensorrtExecutionProvider', 'CPUExecutionProvider']
```

### Шаг 11. Камеры

Настроить потоки в UI: Settings → Cameras → Add stream.
RTSP-адрес камеры, учётные данные.

### Шаг 12. Smoke-тест

```bash
curl -sf http://localhost:8085/api/ui/health
```

---

## 3. Модели и ONNX Runtime GPU

### 3.1 Установка моделей

ONNX-файлы моделей находятся под `.gitignore` и НЕ трекаются в git.  
Их нужно положить вручную или смонтировать через volume.

**Детектор Trapper ONNX:** `app/processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx`  
**Классификатор Birder (chriamue):** `app/processor/models/classification/chriamue_bird_species_classifier/model.onnx`  
**ReID Ornimetrics:** `app/processor/models/reid/ornimetrics/reid_embedder.onnx`  
**Welfare Ornimetrics:** `app/processor/models/welfare/ornimetrics/embedder.onnx` + `welfare_scorer.npz`

### 3.2 ONNX Runtime GPU

```bash
pip install onnxruntime-gpu>=1.20
```

Провайдеры (CUDA EP / TensorRT EP) определяются автоматически.  
Для принудительного выбора: `BIRDLENSE_INFERENCE_DEVICE=cuda:0`

### 3.3 Проверка GPU-инференса

```python
import onnxruntime as ort
sess = ort.InferenceSession("model.onnx", providers=["CUDAExecutionProvider"])
print(sess.get_providers())  # ['CUDAExecutionProvider', ...]
```

---

## 4. Производительность

| Метрика | Orin NX 16GB | Orin NANO 8GB |
|---------|-------------|---------------|
| GPU | 1024-core Ampere | 1024-core Ampere |
| RAM | 16 GB | 8 GB |
| Детектор | >30 FPS (640x640) | >20 FPS (640x640) |
| Классификатор | <50 ms на кроп | <80 ms на кроп |
| ReID | <30 ms на кроп | <50 ms на кроп |
| NVENC/NVDEC | Да (оба) | Да (оба) |

---

## 5. Переменные окружения (app/.env)

```bash
BIRDLENSE_PORT=8085
BIRDLENSE_PLATFORM=orin
BIRDLENSE_INFERENCE_BACKEND=onnxruntime
BIRDLENSE_INFERENCE_DEVICE=cuda:0
BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi
BIRDLENSE_ENCODING=orin
PROCESSOR_SECRET=<32-char-hex>
FLASK_SECRET_KEY=<32-char-hex>
MCP_TOKEN=<token>
```

---

## 6. user_config.yaml (Orin)

Пример: `app/app_config/user_config.orin.example.yaml`

```yaml
processor:
  models:
    detection:
      binary_openvino: models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx
    classification:
      engine: chriamue
    reid:
      model_path: models/reid/ornimetrics/reid_embedder.onnx
    welfare:
      embedder_path: models/welfare/ornimetrics/embedder.onnx
      scorer_path: models/welfare/ornimetrics/welfare_scorer.npz
  inference_backend: onnxruntime
  inference_device: cuda:0
  binary_imgsz: 640
  min_confidence_binary: 0.12
  merge_window_seconds: 12
```

---

## 7. Чек-лист перед деплоем

- [ ] JetPack 6, NVIDIA driver, CUDA 12.x
- [ ] Docker + nvidia-container-runtime
- [ ] `user_config.yaml` настроен
- [ ] `.env` настроен (секреты)
- [ ] ONNX-модели подмонтированы или скопированы
- [ ] `make build && BIRDLENSE_PLATFORM=orin make start`
- [ ] Health-check: `curl -sf http://localhost:8085/api/ui/health`
- [ ] ONNX Runtime видит CUDA: `onnxruntime.get_available_providers()`
- [ ] Камеры добавлены, потоки идут
- [ ] Детекция работает: `recording_session_summary.yolo_frames_with_tracks > 0`