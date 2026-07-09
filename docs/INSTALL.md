# Установка на Jetson Orin

## Требования

- Jetson Orin NX 16GB или Orin NANO 8GB
- JetPack 6+ (L4T r36+)
- Docker с NVIDIA Container Toolkit
- Модели ONNX в `app/processor/models/`

## Шаги

### 1. Установить Docker и NVIDIA runtime

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 2. Скопировать модели

```bash
# Создать структуру
mkdir -p app/processor/models/detection/trapper_ai_v02_2024
mkdir -p app/processor/models/reid/ornimetrics
mkdir -p app/processor/models/welfare/ornimetrics

# Разместить ONNX файлы (см. strategy/orin-setup-and-migration.md §4)
```

### 3. Собрать образ

```bash
cd app
docker build -f Dockerfile.orin -t birdlense-hub:orin .
```

### 4. Настроить и запустить

```bash
cp .env.example .env
# отредактировать
make start
```

См. [`user/install.md`](user/install.md) для полного гайда.