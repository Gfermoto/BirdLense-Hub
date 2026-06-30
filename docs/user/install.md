# Установка на Jetson Orin

## Требования

- Jetson Orin NX 16GB или Orin NANO 8GB
- JetPack 6+ (L4T r36+), NVIDIA drivers
- Docker + NVIDIA Container Toolkit
- ~20GB свободного места (образ + модели)

## Шаг 1: Системные зависимости

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

## Шаг 2: Репозиторий

```bash
git clone <url> /home/birdlense/hub
cd /home/birdlense/hub
git checkout orin
```

## Шаг 3: Модели

Создать структуру директорий и разместить ONNX файлы:

```bash
mkdir -p app/processor/models/detection/trapper_ai_v02_2024
mkdir -p app/processor/models/detection/trapper_ai_v02_2024
  mkdir -p app/processor/models/reid/ornimetrics
  mkdir -p app/processor/models/welfare/ornimetrics
mkdir -p app/processor/models/reid/ornimetrics
mkdir -p app/processor/models/welfare/ornimetrics
```

## Шаг 4: Сборка и запуск

```bash
cp app/.env.example app/.env
# отредактировать .env

cp app/app_config/user_config.orin.example.yaml app/app_config/user_config.yaml
# отредактировать под свою камеру

cd app && make build && make start
```

См. [`strategy/orin-setup-and-migration.md`](../strategy/orin-setup-and-migration.md) для полного runbook.