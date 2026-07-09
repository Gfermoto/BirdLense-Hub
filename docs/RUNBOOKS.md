# Runbook оператора (Orin)

## Ежедневные операции

### Проверка здоровья

```bash
cd app && make verify
# или
curl http://<host>:8085/api/health
```

### Логи

```bash
cd app && make logs
# или конкретный сервис
docker compose logs -f birdlense
```

### Перезапуск

```bash
cd app && make stop && make start
```

### Полное обновление

```bash
cd app && git pull && make build && make stop && make start
```

### Деплой на удалённый Orin

1. Настроить `scripts/deploy.local.sh`
2. `make deploy`

## Проблемы

| Симптом | Действие |
|---------|----------|
| 403 на API | Проверить PROCESSOR_SECRET в .env |
| GPU не виден | `docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi` |
| Пустые записи | Проверить RTSP поток, GStreamer pipeline |
| Процессор не стартует | `make logs` — проверить пути к ONNX файлам |

См. [`user/runbooks.md`](user/runbooks.md) · [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).