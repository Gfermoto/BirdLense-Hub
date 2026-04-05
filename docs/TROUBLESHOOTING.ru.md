# Диагностика и решение проблем

[English](./TROUBLESHOOTING.md)

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

Тихие сообщения, фото: [CONFIGURATION](./CONFIGURATION.ru.md) — Notifications.

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

## Медленный ответ веб-интерфейса (API/UI)

**Типичная причина:** в одном контейнере крутятся **processor** (декодирование, детекция, запись) и **gunicorn** (API). Под нагрузкой CPU занят кадрами и моделью — запросы к UI ждут в очереди потоков.

**Что сделать:**

1. **Ресурсы хоста и Docker** — в `app/docker-compose.yml` по умолчанию лимит **4 CPU / 4G RAM**. При необходимости поднимите `cpus` и `mem_limit` через `docker-compose.override.yml` (см. `docker-compose.intel.example.yml` как образец override).
2. **Кэш API** — **Настройки → Производительность**: включите Redis (`performance.cache_redis_enabled`), проверьте `REDIS_URL` в `.env` (в compose обычно `redis://redis:6379/0`). Без Redis кэш только в памяти процесса и менее эффективен при перезапусках.
3. **Параллельные запросы** — один процесс gunicorn, потоки `gthread` (по умолчанию **16**). Увеличить очередь: в `.env` задать `GUNICORN_THREADS=24` (или выше, если RAM и CPU позволяют), затем `make restart`.
4. **Диск и БД** — очень большой `birdlense.db` или медленный диск усиливают задержки; страница **Система** показывает загрузку. При необходимости сделайте бэкап (**Система → Хранилище**), остановите хаб и выполните обслуживание SQLite (например `sqlite3 birdlense.db "VACUUM;"`).
5. **Сеть** — доступ по Wi‑Fi или через удалённый VPS добавляет задержку независимо от сервера.

**Быстрая проверка нагрузки:** `docker stats birdlense` — если CPU у контейнера долго около лимита, UI будет откликаться медленнее; снижайте нагрузку (разрешение/FPS, внешний Frigate) или поднимайте лимиты.

---

## Пропущенные события Frigate/BirdNET

Цепочка: Камера → go2rtc → Frigate → MQTT → BirdLense. Проверять снизу вверх.

**Типичные ошибки:** `non monotonically increasing dts`, `Connection timed out`, `404 Not Found`, `No route to host` — без стабильного потока нет детекций.

**Проверка:** `mosquitto_sub -t 'frigate/#' -v`; `curl -s http://GO2RTC_IP:1984/api/streams | jq .`

**Резерв:** если Frigate падает — включить OpenCV или ESPHome как запасной триггер (Настройки → Детекция движения).

### Чеклист причин (Frigate видит птицу, BirdLense не записывает)

| # | Причина | Как проверить |
|---|---------|---------------|
| 1 | `motion.source: opencv` (дефолт) | `user_config.yaml` → `motion.source` должен быть `frigate` или `mqtt` |
| 2 | Камера Frigate не в `video.cameras` | `id` в cameras должен совпадать с именем камеры во Frigate |
| 3 | `frigate_label_filter` пустой | Дефолт `["bird","Bird"]`; пустой список отбрасывает все события |
| 4 | MQTT долго недоступен (брокер/сеть) | Логи `MQTT aggregator disconnected` / `MQTT aggregator connected`; reconnect идёт с backoff (`mqtt.reconnect_min_delay` → `mqtt.reconnect_max_delay`) |
| 5 | `frigate_topic` не совпадает с Frigate | Frigate `mqtt.topic_prefix` → топик `PREFIX/events` |
| 6 | MQTT QoS 0 — потеря при reconnect | Нестабильная сеть |

**Порядок проверки:** motion.source → video.cameras (id камеры) → логи `Frigate trigger` / `Frigate event skipped` → `GET /api/ui/status` (mqtt: ok).

---

## Восстановление SQLite не сработало

Функция: **System → Storage → Восстановить из файла**.

- Поддерживаются только валидные SQLite-файлы (`.db/.sqlite`).
- При восстановлении текущая БД заменяется, но перед этим автоматически создаётся `*.pre_restore_*.bak` рядом с `birdlense.db`.
- Если получаете ошибку `Invalid SQLite database file` — файл повреждён или не является SQLite.

Проверка файла перед загрузкой:

```bash
sqlite3 "/path/to/backup.db" "PRAGMA integrity_check;"
```

Ожидаемый результат: `ok`.

---

## Live: 502 или чёрный экран

**502** — контейнер не достучался до go2rtc. URL должен быть доступен из контейнера:
- `network_mode: host` → `http://localhost:1984`
- bridge → `http://172.17.0.1:1984` или `http://IP_хоста:1984`

go2rtc должен слушать `0.0.0.0:1984`. Проверка: `curl -s -o /dev/null -w "%{http_code}" http://172.17.0.1:1984/api/streams` → 200.

**Обход:** на странице Live нажать **«MJPEG»** — поток через процессор.

---

## См. также

[INSTALL](./INSTALL.ru.md) · [CONFIGURATION](./CONFIGURATION.ru.md) · [SCENARIOS](./SCENARIOS.ru.md) · [GLOSSARY](./GLOSSARY.ru.md)
