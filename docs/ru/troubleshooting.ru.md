# Диагностика и решение проблем

[English](../user/troubleshooting.md)

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

Тихие сообщения, фото: [CONFIGURATION](./configuration.ru.md) — Notifications.

---

## Старт одного контейнера (entrypoint): куда смотреть, если «зависло» {#single-container-startup-stuck}

Контейнер запускает **`app/scripts/entrypoint.sh`**: nginx → gunicorn → ожидание **`GET /api/ui/health`** (до ~400 с) → опционально MCP → цикл **processor** (`processor/src/main.py`). См. [ARCHITECTURE.ru.md](./architecture.ru.md#runtime-processes-ports-and-health-signals) и [RUNTIME_COUPLING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/RUNTIME_COUPLING.ru.md).

| Симптом | Куда смотреть |
| --------- | ---------------- |
| Пустая страница / 502 от nginx | `docker exec birdlense tail -100 /var/log/nginx/error.log` — upstream на `127.0.0.1:8000` |
| Долгое ожидание health / первый ответ | `docker logs birdlense` — `create_app()`, Telegram, миграции БД; см. раздел **«Спам App is UP!»** выше |
| UI есть, нет детекций / live | Processor отдельно: логи `main.py`, Go2RTC/MQTT; см. раздел **«Пороги processor»** ниже |
| Ошибки Redis | `docker compose ps` — здоров ли `birdlense-redis`; `REDIS_URL` в `app/.env` |

Проверки с хоста (порт по умолчанию):

```bash
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/api/ui/health"
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/api/ui/readiness" | head -c 400
```

Внутри контейнера gunicorn — **`127.0.0.1:8000`** (не публикуется наружу); nginx — **`8080`**.

---

## Перезапуски и подвисания

В контейнере: nginx, gunicorn, processor (в цикле). Processor перезапускается без выхода контейнера. nginx и gunicorn запущены в фоне: если они упадут, контейнер может остаться живым, но стать unhealthy или частично сломанным. Контейнер выходит при завершении foreground entrypoint / processor loop или остановке runtime.

**Проверить:**
```bash
docker inspect birdlense --format '{{.State.ExitCode}} {{.State.Error}}'
docker logs birdlense --tail 200 2>&1
```
- `137` — OOM Kill
- `139` — segfault
- `[h264] error while decoding MB` — нестабильный RTSP, сеть
- **nginx** (прокси до gunicorn): файлы **`/var/log/nginx/error.log`** и **`access.log`** в контейнере, владелец **`birdlense`**. Пример: `docker exec birdlense tail -100 /var/log/nginx/error.log`

**Рекомендации:** `mem_limit: 4g` в compose; логи в файл; Prometheus/Grafana.

---

## Пороги processor: сохранили в UI, поведение не меняется

**Причина:** веб (gunicorn/Flask) и **processor** — разные процессы. Сохранение настроек пишет `user_config.yaml` и обновляет конфиг в памяти веба; **цикл записи и детекции** в processor не опрашивает файл на каждом кадре — действуют значения на момент старта процесса.

**Что сделать:** после правок `processor.*`, `detection.*` и связанных ключей выполните **перезапуск processor** (Настройки → соответствующая кнопка, `POST /api/ui/restart-processor` или перезапуск контейнера `birdlense`). Чтобы отделить шум в Telegram от записи в БД, используйте **`processor.min_confidence_to_notify`** — см. [CONFIGURATION.ru.md](./configuration.ru.md) → Processor.

---

## Контракт весов: `detector_scope` и классы модели {#detector-weight-contract-mismatch}

**Симптом в логах:** `Detector weight contract: ... miss scoped labels` — в `processor.detector_scope` указан класс, которого **нет** в текущих бинарных весах (например в модели только `Bird`, а в scope ещё и `Rodent`).

**Падения нет** при `processor.detector_weight_contract: warn` (дефолт). В режиме **`enforce`** старт не пройдёт, пока веса и scope не согласованы.

**Что сделать:** (1) Сузьте `processor.detector_scope` под реальные `model.names` / манифест обучения. (2) Либо выкатите веса, где есть все scoped-классы, и перезапустите processor. (3) Не добавляйте `Background` в scope — см. [CV_ML_PREP.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CV_ML_PREP.ru.md).

**Связано:** [CV_ML_ROADMAP_PHASES.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.ru.md) (эпик #368). Англ. версия: [TROUBLESHOOTING.md](../user/troubleshooting.md#detector-weight-contract-mismatch).

---

## Запись: JSON-сводка сессии в логах {#recording-session-summary-json}

**Слабые детекции / пустые строки в БД:** после финализации клипа в логах processor одна структурированная строка:

`recording_session_summary {…}` (JSON) — `duration_s`, `triggered_camera`, `frames_seen`, `yolo_frames_ran`, `yolo_frames_with_tracks`, `low_light_blocked_frames`, `session_extended_by_frigate_only`, `bytetrack_rows`, `post_fusion_persisted`, `mqtt_events_in_window`, `video_file_ok`, `runtime_profile` (воронка: кадры → запуски YOLO → треки → fusion).

**Пример:** `docker logs birdlense 2>&1 | grep recording_session_summary | tail`

---

## Processor: шум «Slow frame processing» на большом разрешении {#processor-slow-frame-warnings}

**Симптом:** много строк `Slow frame processing: …ms >= …ms`, низкий эффективный FPS — типично для **2.7K+** и тяжёлого YOLO.

**Важно:** `processor.frame_processing_warn_ms` (по умолчанию **450**) влияет только на **частоту предупреждений в логах**, не на скорость инференса. Снижать **реальную** задержку: `processor.binary_imgsz`, профиль, ресурсы — см. [PROCESSOR_PERFORMANCE.ru.md](./processor-performance.ru.md) и [RUNBOOKS.ru.md](./runbooks.ru.md). Подсказка **config-audit** в UI (`configAuditRuntimeSlowFrames`) об этом же компромиссе.

**Англ. версия:** [TROUBLESHOOTING.md](../user/troubleshooting.md#processor-slow-frame-warnings).

---

## Медленный ответ веб-интерфейса (API/UI)

**Типичная причина:** в одном контейнере крутятся **processor** (декодирование, детекция, запись) и **gunicorn** (API). Под нагрузкой CPU занят кадрами и моделью — запросы к UI ждут в очереди потоков.

**Что сделать:**

1. **Ресурсы хоста и Docker** — в `app/docker-compose.yml` по умолчанию лимит **4 CPU / 4G RAM**. При необходимости поднимите `cpus` и `mem_limit` через `docker-compose.override.yml` (см. `docker-compose.intel.example.yml` как образец override).
2. **Кэш API** — **Настройки → Производительность**: включите Redis (`performance.cache_redis_enabled`), проверьте `REDIS_URL` в `.env` (в compose обычно `redis://redis:6379/0`). Без Redis кэш только в памяти процесса и менее эффективен при перезапусках.
3. **Параллельные запросы** — один процесс gunicorn, потоки `gthread` (по умолчанию **16**). Увеличить очередь: в `app/.env` задать `GUNICORN_THREADS=24` (или выше, если RAM и CPU позволяют), затем перезапуск контейнера: `cd app && docker compose restart birdlense` (или `make stop && make start`).
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
| 1 | Frigate не включаётся автоматически только из broker | **`user_config.yaml`**: включите **`triggers.frigate.enabled: true`** и задайте **`mqtt.broker`**, топик задаётся в **`triggers.frigate.topic`** (или legacy **`mqtt.frigate_topic`**, который мигрирует при сохранении) |
| 2 | Камера Frigate не в `video.cameras` | `id` в cameras должен совпадать с именем камеры во Frigate |
| 3 | `frigate_label_filter` пустой | Дефолт `["bird","Bird"]`; пустой список отбрасывает все события |
| 4 | MQTT долго недоступен (брокер/сеть) | Логи `MQTT aggregator disconnected` / `MQTT aggregator connected`; reconnect идёт с backoff (`mqtt.reconnect_min_delay` → `mqtt.reconnect_max_delay`) |
| 5 | `frigate_topic` не совпадает с Frigate | Frigate `mqtt.topic_prefix` → топик `PREFIX/events` |
| 6 | MQTT QoS 0 — потеря при reconnect | Нестабильная сеть |

**Порядок проверки:** **`triggers.frigate.enabled`**, **`mqtt.broker`**, `video.cameras` (id камеры) → логи `Frigate trigger` / `Frigate event skipped` → `GET /api/ui/status` (mqtt: ok).

### BirdNET: звук есть, FIFO заполняется, но видео «не слышит» / нет audio evidence

Симптом: в **Система → Автоматизация → BirdNET FIFO** события видны, а слияние с YOLO не даёт `support` или авто-пороги по BirdNET не срабатывают.

| # | Причина | Что сделать |
|---|---------|-------------|
| 1 | В MQTT **нет научного имени** (`ScientificName` / аналог), только локализованное имя | Предпочтительно **BirdNET-Go** (обычно шлёт латинское имя). Иначе добавьте **алиас** в реестре видов Hub на эту строку из MQTT → таксон, либо пару в `detection.species_mapping`. |
| 2 | Вид в каталоге Hub **не совпадает** с `species_taxon.scientific_name` | Проверьте строку таксона и латинское имя (опечатки, лишние пробелы). |
| 3 | Hub на **PostgreSQL** без общего `birdlense.db` у процессора | Авто-сопоставление по SQLite-каталогу недоступно — используйте **`detection.species_mapping`** для строк из MQTT. |
| 4 | MQTT-имя вида не совпадает с **именем вида у классификатора** | После сопоставления с каталогом ключ слияния должен совпасть с тем, что даёт `normalize()` для видео-детекций (см. [CONFIGURATION.ru.md](./configuration.ru.md) § MQTT). |

**Проверка на сервере:** `GET /api/ui/health` — `mqtt: ok`; логи процессора — `MQTT aggregator connected`, при отладке BirdNET — уровень `processor.birdnet_mqtt_observability_level: debug`. Снимок FIFO: **Система → Автоматизация → BirdNET FIFO: снимок** (нужен пароль администратора).

---

## Процессор: деградация триггеров / MQTT (метрики) {#processor-trigger-metrics}

Симптом: записи почти не стартуют при включённом **`triggers.frigate`** или MQTT-only motion, без явного traceback.

На сервере откройте **`data/diagnostics/processor_runtime_stats.json`** (снимок процессора):

| Сигнал | Смысл |
|--------|--------|
| `trigger_frigate_degraded_no_mqtt` = **1** | Frigate включён в конфиге, MQTT задан, но сессия **не** жива (`trigger_mqtt_live` = 0). |
| `trigger_degraded_effective_lt_configured` = **1** | При простое MQTT эффективных путей motion меньше, чем включено в `triggers.*`. |
| `trigger_motion_factory_frigate_fallback_opencv_total` | Фабрика motion откатилась на один OpenCV — детектор Frigate не был подключён. |

Вместе с **`mqtt_connected`** и счётчиками очередей — см. [PROCESSOR_PERFORMANCE.ru.md](./processor-performance.ru.md). Ключи YAML: [CONFIGURATION.ru.md](./configuration.ru.md) § MQTT и инвентаризация триггеров.

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

[INSTALL](./install.ru.md) · [CONFIGURATION](./configuration.ru.md) · [SCENARIOS](./scenarios.ru.md) · [GLOSSARY](./glossary.ru.md)
