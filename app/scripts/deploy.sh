#!/bin/bash
set -e
# Очистка старых образов и контейнеров
sudo docker-compose down
sudo docker rmi $(sudo docker images -q birdlense:latest) 2>/dev/null || true

# После очистки пробуем удалить остаточные папки (опционально)
sudo rm -rf /var/lib/docker/containers/* || true

# Сборка и запуск
make build
make up