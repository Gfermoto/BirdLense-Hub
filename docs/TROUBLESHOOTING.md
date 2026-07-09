# Устранение проблем (Orin)

## 403 Forbidden на API

PROCESSOR_SECRET в `.env` не совпадает с тем, что ждёт процессор.

```bash
# Проверить
grep PROCESSOR_SECRET app/.env
# Сгенерировать новый
python3 -c "import secrets; print(secrets.token_hex(16))"
```

## GPU не виден в контейнере

```bash
# Проверить на хосте
nvidia-smi
# Проверить runtime
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi
# Если не работает: переустановить nvidia-container-toolkit
```

## Пустые записи / нет детекций

1. Проверить RTSP поток: `ffplay rtsp://...`
2. Проверить пути к ONNX моделям в user_config
3. Проверить GStreamer pipeline в логах: `make logs | grep gstreamer`

## Процессор падает с FileNotFoundError

Путь к ONNX файлу указан неверно. Путь — **относительно `app/processor/`**.

```bash
ls -la app/processor/models/detection/trapper_ai_v02_2024/
```

## Контейнер не стартует

```bash
docker compose logs --tail=50
# Проверить .env: все ли переменные заданы
```

См. [`user/troubleshooting.md`](user/troubleshooting.md).