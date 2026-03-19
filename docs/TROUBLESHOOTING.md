# Диагностика и решение проблем

---

## Intel GPU: запись идёт как CPU

В **Настройки → Видео → Кодирование записи** можно выбрать CPU или Intel GPU. Если в логах «Starting FFmpeg recording ... (CPU)» при выборе Intel — в контейнере нет доступа к `/dev/dri/renderD128`.

**Решение:** скопировать override:
```bash
cp app/docker-compose.intel.example.yml app/docker-compose.override.yml
make stop && make start
```
В настройках выбрать «Intel GPU». На странице System должно появиться «Сейчас: Intel GPU (VA-API)».

---

## Спам «App is UP!» в Telegram

**Причина:** entrypoint ждал API 30 с, но gunicorn не отвечает, пока не завершится `create_app()` → `notify_app_startup()` → Telegram (таймаут до 300 с в РФ). Health check не успевал → перезапуск контейнера → цикл.

**Исправлено:** ожидание 400 с; таймауты Telegram 300 с (до 600 с); маркер `/tmp/.birdlense_startup_notify_sent` — повторные вызовы пропускают отправку.

**Диагностика:** `docker inspect birdlense --format '{{.RestartCount}}'` (растёт = цикл). Логи: `create_app() invoked`, `notify_app_startup: sending` / `skip`.

Тихие сообщения, фото: [CONFIGURATION.md](./CONFIGURATION.md) — Notifications.

---

## Перезапуски и подвисания

В контейнере: nginx, gunicorn, processor (в цикле). Processor перезапускается без выхода контейнера. Контейнер падает при выходе nginx/gunicorn/entrypoint.

**Проверить:**
```bash
docker inspect birdlense --format '{{.State.ExitCode}} {{.State.Error}}'
docker logs birdlense --tail 200 2>&1
```
- `137` — OOM Kill
- `139` — segfault
- `[h264] error while decoding MB` — нестабильный RTSP, сеть

**Рекомендации:** `mem_limit: 4g` в compose; логи в файл; Prometheus/Grafana.

---

## Пропущенные события Frigate/BirdNET

Цепочка: Камера → go2rtc → Frigate → MQTT → BirdLense. Проверять снизу вверх.

**Типичные ошибки:** `non monotonically increasing dts`, `Connection timed out`, `404 Not Found`, `No route to host` — без стабильного потока нет детекций.

**Проверка:** `mosquitto_sub -t 'frigate/#' -v`; `curl -s http://GO2RTC_IP:1984/api/streams | jq .`

**Резерв:** если Frigate падает — включить OpenCV или ESPHome как запасной триггер (Настройки → Детекция движения).

---

## Live: 502 или чёрный экран

**502** — контейнер не достучался до go2rtc. URL должен быть доступен из контейнера:
- `network_mode: host` → `http://localhost:1984`
- bridge → `http://172.17.0.1:1984` или `http://IP_хоста:1984`

go2rtc должен слушать `0.0.0.0:1984`. Проверка: `curl -s -o /dev/null -w "%{http_code}" http://172.17.0.1:1984/api/streams` → 200.

**Обход:** на странице Live нажать **«MJPEG»** — поток через процессор.
