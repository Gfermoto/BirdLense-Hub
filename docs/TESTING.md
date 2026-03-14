# Тестирование BirdLense Hub

> **Безопасность:** если пароль настроек попал в лог или чат — смените его в Settings → General.

---

## Часть 1: Тесты (разработка, CI)

### Unit-тесты (processor)

```bash
cd app && make test
```

Запускает `unittest` для processor в Docker (detection strategy, decision maker). Нужны ultralytics, ncnn — тесты выполняются в контейнере.

### API-тесты (web)

```bash
cd app && make test-web
```

Запускает pytest для web API в Docker (health, status, settings, feed, cameras).

Перед первым запуском: `make build`. Тесты выполняются в контейнере.

### Покрытие (coverage)

```bash
cd app && make test-coverage
```

Запускает processor + web тесты с измерением покрытия, выводит отчёт в консоль.

```bash
cd app && make test-report
```

То же + генерирует HTML-отчёт в `app/htmlcov/index.html`.

Конфигурация: `app/.coveragerc` (исключены tests, app_config, scripts).

Приоритет для расширения покрытия: `ui_system_routes`, `retention_service`, `visit_processor`, `processor_routes`.

### E2E-тесты (Playwright)

E2E проверяют UI и API на работающем экземпляре.

**Запуск:**

1. Запустите приложение:
   ```bash
   cd app && make start
   ```

2. Запустите E2E:
   ```bash
   cd app && make test-e2e
   ```

3. Против сервера (192.168.1.11:8085):
   ```bash
   cd app && BASE_URL=http://192.168.1.11:8085 make test-e2e
   ```

4. **Пароль** — если включена защита настроек (`general.settings_password`), задайте `E2E_SETTINGS_PASSWORD=xxx` для полного прогона. Без него тесты Settings и `GET /api/ui/settings` пропускаются (skip).

**Что проверяют E2E:**

- **smoke.spec.ts**: загрузка главной, навигация, Settings, Live
- **api.spec.ts**: `/api/ui/health`, `/api/ui/status`, `/api/ui/settings`, `/api/ui/cameras`, `/api/ui/weather`, `/api/ui/feed/dispense`
- **settings.spec.ts**: форма настроек, секции Video/MQTT, Feed

**Только API-тесты (без браузера):**

```bash
cd app/e2e && npm test -- --grep @api
```

### Статус MQTT и ESPHome

Эндпоинт `/api/ui/status` возвращает:

- `mqtt`: `ok` | `error` | `not_configured` | `not_used`
- `esphome`: `ok` | `error` | `not_configured` | `not_used`

Когда `feed.source` = `mqtt`, проверяется подключение к MQTT-брокеру.  
Когда `feed.source` = `esphome`, проверяется доступность URL кормушки.

Индикаторы отображаются в навигации (StatusIndicator).

---

## Часть 2: Проверка после деплоя

Проверка работоспособности распознавания **без птиц** (например, после ночного деплоя).

> **Важно:** распознавание могло ломаться из‑за `PROCESSOR_SECRET` (токен не подставлялся в `.env`). Исправление в deploy.sh — проверка обязательна после деплоя (см. раздел «403 (PROCESSOR_SECRET)»).

### 1. Сразу после деплоя (перед сном)

**API и статус:**

```bash
curl -s http://192.168.1.11:8085/api/ui/health
curl -s http://192.168.1.11:8085/api/ui/status
```

Ожидаемо: `processor: ok`, `web: ok`, `motion_source: opencv` или `frigate`. При `motion_source: frigate` и `feed.source` ≠ mqtt поле `mqtt` показывает статус aggregator (ok при processor ok).

**Логи процессора:**

- **UI:** System → Логи процессора (последние 100–200 строк)
- **SSH:**
  ```bash
  ssh birdlense "tail -100 /root/BirdLense/app/data/processor.log"
  ```

Проверить:
- модели загружены (NCNN, YOLO);
- `Motion: Frigate` или `Motion: OpenCV`;
- нет `API request failed`, `403`, `Connection refused`;
- нет `Traceback`, `Error`, `Exception`.

**403 (PROCESSOR_SECRET)**

Если в логах есть `API request failed ... 403` — процессор не проходит проверку API.

**Проверка:** на сервере `cat app/.env | grep PROCESSOR_SECRET` — должно быть `PROCESSOR_SECRET=hex...` (32 символа), а не `PROCESSOR_SECRET=${PROCESSOR_SECRET}`. Если буквально — баг в deploy.sh (исправлено: двойные кавычки при записи).

**Серые иконки (Video, MQTT, YOLO)**

Если статус серый при работающем подключении — heartbeat не доходит до API.

**Диагностика:**
```bash
curl -s http://YOUR_IP:8085/api/ui/status/debug
```

- `last_heartbeat: null` — процессор не шлёт heartbeat (проверить логи: `Heartbeat failed`, `403`)
- `last_heartbeat.updated_at` старый — процессор упал или heartbeat не проходит
- `processor_secret_configured: false` — PROCESSOR_SECRET не задан в контейнере
- `activity_log: 403 Forbidden` в логах — несовпадение PROCESSOR_SECRET

### 2. Провокация события (тест полного пайплайна)

Запуск процессора на **существующей записи** с птицей — симулирует детекцию и создаёт новую запись в UI.

**Автоматический скрипт:**

```bash
./scripts/test-deploy-recognition.sh
```

Скрипт:
1. Находит последнюю запись `video.mp4` в `app/data/recordings/` (или берёт путь по `VIDEO_ID` через API);
2. Запускает процессор с `--fake-motion true` и `MQTT_CLIENT_ID=birdlense_aggregator_test` (избегает конфликта с основным процессором);
3. Обрабатывает видео, запускает YOLO;
4. При обнаружении птицы — создаёт новую запись и сохраняет в API.

**Тест на конкретном видео по ID:**

```bash
VIDEO_ID=37 ./scripts/test-deploy-recognition.sh
```

**Ручной запуск:**

```bash
# Найти запись (на сервере)
ssh birdlense "find /root/BirdLense/app/data/recordings -name 'video.mp4' | tail -1"

# Запустить процессор (подставить путь)
ssh birdlense "docker exec birdlense python /app/processor/src/main.py /app/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4 --fake-motion true"
```

Или локально (если контейнер запущен):

```bash
cd app
VIDEO=$(find data/recordings -name 'video.mp4' 2>/dev/null | tail -1)
docker exec birdlense python /app/processor/src/main.py "/app/$VIDEO" --fake-motion true
```

**Результат:** В UI должна появиться **новая** запись (дата/время = момент запуска). В логах: `Detection ... has N track frames`, `create_video` без ошибок.

**Примечание:** Скрипт запускает процессор в том же контейнере (docker exec). При `args.input` (видеофайл) процессор не создаёт Go2RTC-стримы — конфликта портов нет. Используется отдельный MQTT client_id (`birdlense_aggregator_test`), чтобы не конфликтовать с основным процессором.

**Ограничение:** Скрипт проверяет только **YOLO** и цепочку процессор → API. Не проверяет: Frigate MQTT (триггер записи), BirdNET MQTT (аудио-детекции), Go2RTC (подключение к потоку).

### 3. Тест MQTT (Frigate, BirdNET)

Проверка приёма событий от Frigate и BirdNET. Требует: процессор запущен, MQTT брокер доступен.

**Что смотреть в логах:**

| Событие | Строка в processor.log |
|---------|------------------------|
| MQTT подключён | `MQTT aggregator connected` |
| Frigate триггер | `Frigate trigger: camera=X label=Y sub_label=Z -> recording` |
| Frigate пропущен | `Frigate event skipped (no trigger): camera=... \| camera_filter=... label_filter=...` |
| Frigate не подключён | `Frigate MQTT not connected, falling back to OpenCV` |

**Ручная публикация тестового события:**

**Frigate** (триггер записи — процессор начнёт запись с Go2RTC):

```bash
# Брокер и порт — из mqtt.broker в конфиге или MQTT_BROKER
# Топик по умолчанию: frigate/events
# camera — должен совпадать с video.cameras[].id или frigate_camera_filter (пусто = любая)
# label/sub_label — bird или Bird (frigate_label_filter)

mosquitto_pub -h BROKER -p 1883 -t "frigate/events" -m '{"after":{"camera":"birdbox","label":"bird","sub_label":"Bird","top_score":0.95,"frame_time":'$(date +%s)'}}'
```

Подставьте `BROKER` (IP брокера) и `birdbox` — имя камеры из `video.cameras[].id` или `motion.frigate_camera_filter`. Если фильтр пуст — подойдёт любая камера.

После публикации в логах должно появиться `Frigate trigger: camera=... label=bird sub_label=Bird -> recording`, и начнётся запись.

**BirdNET** (событие для слияния с YOLO; само по себе запись не запускает):

```bash
mosquitto_pub -h BROKER -p 1883 -t "birdnet" -m '{"Common_Name":"Northern Cardinal","Confidence_Score":0.85}'
```

При аутентификации MQTT добавьте `-u USER -P PASS`.

**Проверка статуса MQTT:**

```bash
curl -s http://IP:8085/api/ui/status
```

При `motion.source: frigate` поле `mqtt` должно быть `ok`. Если `not_used` — MQTT не используется для motion.

### 4. Утром (если ночью не было птиц)

Если записей нет — это нормально. Проверить:

- **Status:** `processor: ok` (heartbeat есть);
- **Логи:** нет ошибок, падений, 403;
- **Activity:** в System → Activity есть активность за ночь.

### 5. Диагностика по логам

| Симптом | Что искать |
|--------|------------|
| 403 | `API request failed` + `403` |
| Падение | `Traceback`, `Error`, `Exception` в processor.log |
| Модели не загружаются | `Loading ... ncnn_model` + `Error` |
| Нет Go2RTC | `video.go2rtc_url не задан`, `waiting_cameras` |
| Нет motion | `Frigate MQTT not connected`, `falling back to OpenCV` |
| Frigate не триггерит | `Frigate event skipped` — проверить camera_filter, label_filter |
| MQTT отключён | `MQTT aggregator connect failed`, `disconnected` |

### 6. Минимальный чеклист перед сном

1. `curl http://IP:8085/api/ui/status` → `processor: ok`, `mqtt: ok` (если motion.source: frigate)
2. **PROCESSOR_SECRET:** `ssh birdlense "grep PROCESSOR_SECRET app/.env"` → hex-значение, не `${PROCESSOR_SECRET}`. **DEPLOY_URL** в deploy.local.sh — URL сервера (не localhost), иначе health check FAIL.
3. System → Логи процессора → последние 50 строк без ошибок, нет 403
4. `./scripts/test-deploy-recognition.sh` → новая запись в UI (проверка YOLO)
5. При Frigate: `mosquitto_pub` тестового события → в логах `Frigate trigger: ... -> recording`

Если всё зелёное — можно оставлять на ночь.

---

См. также: [DEPLOYMENT.md](./DEPLOYMENT.md), [CONFIGURATION.md](./CONFIGURATION.md), [MQTT_DISCOVERED_TOPICS.md](./MQTT_DISCOVERED_TOPICS.md).
