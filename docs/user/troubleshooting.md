# Устранение проблем

## Контейнер не запускается

```bash
docker compose logs --tail=50
```

Проверить `.env`:

```bash
diff app/.env.example app/.env
```

## 403 Forbidden на API

PROCESSOR_SECRET не совпадает:

```bash
# Проверить
grep PROCESSOR_SECRET app/.env
# Сгенерировать
python3 -c "import secrets; print(secrets.token_hex(16))"
# Обновить в .env и перезапустить
```

## GPU не виден

```bash
nvidia-smi                           # на хосте
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi   # в контейнере
```

Если не работает:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Пустые записи (нет детекций)

1. RTSP поток работает? `ffplay rtsp://...`
2. Пути к ONNX файлам правильные? `ls -la app/processor/models/detection/trapper_ai_v02_2024/`
3. GStreamer pipeline корректный? (проверить в логах)

## Процессор не стартует (FileNotFoundError)

```bash
# Проверить пути в user_config.yaml
# Путь — относительно app/processor/
# Абсолютные пути должны существовать внутри контейнера
```

## Высокая загрузка CPU/GPU

- Уменьшить число RTSP потоков
- Проверить `binary_imgsz` в конфиге (640 рекомендуется)
- Убедиться, что NVDEC/NVENC используются (проверить логи GStreamer)

## Ошибка сборки Docker

```bash
docker build -f Dockerfile.orin -t birdlense-hub:orin . --no-cache
```

См. [`../TROUBLESHOOTING.md`](../TROUBLESHOOTING.md) · [`runbooks.md`](runbooks.md).