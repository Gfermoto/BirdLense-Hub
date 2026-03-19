# Диагностика перезапусков и подвисаний

## Архитектура контейнера

В одном контейнере работают:
1. **nginx** — статика, прокси
2. **gunicorn** (1 worker) — Flask API
3. **processor** (`main.py`) — запускается **в цикле** в entrypoint

Когда processor завершается (по флагу перезапуска из UI, crash или exit) — перезапускается **только процесс процессора**, контейнер не выходит. Контейнер падает только при выходе nginx/gunicorn или самого entrypoint. При старте контейнера gunicorn вызывает `notify_app_startup()` (уведомление «App is UP!» в Telegram).

---

## Что проверить на сервере

### 1. Частота перезапусков

```bash
ssh birdlense "docker ps -a --format '{{.Status}}' && docker inspect birdlense --format '{{.State.StartedAt}}'"
```

Если `Restarting` или `Up X seconds` — контейнер только что перезапустился.

### 2. Причина выхода (exit code)

```bash
ssh birdlense "docker inspect birdlense --format '{{.State.ExitCode}} {{.State.Error}}'"
```

- `137` — OOM Kill (нехватка памяти)
- `139` — segfault
- `0` — нормальный выход (например, restart flag)

### 3. Логи процессора

```bash
ssh birdlense "docker logs birdlense --tail 200 2>&1"
```

Ищите: `Traceback`, `Error`, `Killed`, `Restart flag found`, `exiting for restart`.

### 4. Память

```bash
ssh birdlense "free -h && docker stats birdlense --no-stream"
```

YOLO/Ultralytics + FFmpeg требуют 2–4 GB RAM. При нехватке — OOM Kill.

### 5. Файл restart flag

```bash
ssh birdlense "ls -la /root/BirdLense/app/data/restart_processor.flag 2>/dev/null || echo 'нет'"
```

Если файл есть — processor при следующей итерации цикла выйдет. Удалить: `rm /root/BirdLense/app/data/restart_processor.flag`

### 6. История перезапусков Docker

```bash
ssh birdlense "docker events --since 1h --filter 'container=birdlense' --filter 'event=restart' 2>/dev/null | tail -20"
```

---

## Типичные причины

| Симптом | Возможная причина |
|--------|-------------------|
| Exit 137 | OOM — добавить RAM или ограничить потребление |
| Exit 139 | Segfault (CUDA, библиотеки) |
| «Restart flag found» | Кто-то вызвал «Перезапустить процессор» в UI |
| Подвисания без рестарта | Блокировка: Go2RTC, MQTT, диск |
| Частые рестарты при детекции | Ошибка в обработке видео (best_frame, merge) |
| `[h264] error while decoding MB` в логах | Нестабильный RTSP: потери пакетов, слабая сеть, перегрузка камеры |

### Ошибки H.264 в логах

Сообщения `error while decoding MB`, `SEI truncated`, `cabac decode failed` — FFmpeg не может корректно декодировать часть кадров. Обычно не критично, но при сильной деградации потока возможны подвисания FFmpeg.

**Что проверить:**
- Качество сети до камеры (Wi‑Fi vs Ethernet)
- Нагрузка на камеру (разрешение, битрейт, количество клиентов)
- Настройки Go2RTC (буфер, кодек)

---

## Рекомендации

1. **Лимит памяти** — в `docker-compose` добавить `mem_limit: 4g` (или по возможностям сервера).
2. **Логи в файл** — для разбора после падения:
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "50m"
       max-file: "3"
   ```
3. **Мониторинг** — `docker stats` в фоне или Prometheus/Grafana.
