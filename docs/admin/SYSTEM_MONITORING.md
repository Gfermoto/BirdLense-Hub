# Мониторинг BirdLense Hub (страница «Система»)

## Матрица статусов

| Уровень | UI | Когда |
|---------|-----|--------|
| **OK** (зелёный) | `success` | Штатная работа, очередь BirdNET с событиями, readiness green |
| **Info** (синий) | `info` | Намеренно выключено: BirdNET без топика MQTT, пустая очередь при тишине, устаревшие ключи в `user_config` |
| **Warning** (жёлтый) | `warning` | Деградация: устаревший снимок FIFO, MQTT down при включённом BirdNET, предупреждения config-audit, strict-quality gates |
| **Critical** (красный) | `error` | Readiness не ready, падение БД/диска, недоступность очереди при включённом BirdNET и reporting |

Правило для оператора: **красный = действие сейчас**; **синий = так задумано или нет данных для метрики**; жёлтый — разобрать в рабочее время.

## BirdNET FIFO

API: `GET /api/ui/system/diagnostics/birdnet-fifo`

Поля `operational_tier` / `operational_code` / `operational_summary_key`:

| code | tier | Смысл |
|------|------|--------|
| `birdnet_disabled` | info | Нет `mqtt.broker` или `mqtt.birdnet_topic` |
| `birdnet_reporting_off` | info | `birdnet_fifo_snapshot_enabled` и persist выкл. |
| `birdnet_queue_empty` | info | MQTT настроен, очередь пуста после TTL (тишина) |
| `birdnet_active` | ok | Есть события в очереди |
| `birdnet_snapshot_stale` | warning | JSON-снимок старше `birdnet_fifo_snapshot_stale_sec` |
| `birdnet_mqtt_disconnected` | warning | В снимке `mqtt_connected: false` |
| `birdnet_unavailable` | warning/critical | Нет БД и нет файла при включённом reporting |

Пустая таблица видов при `queue_len: 0` — **не ошибка**, если tier = `birdnet_queue_empty`.

## Domain health (качество данных)

`GET /api/ui/system/domain-health` — не liveness.

- Gates по ratio (YOLO primary, bbox frames) **пропускаются**, если за 24 ч не было video-детекций (`video_detections_24h = 0`), чтобы не было ложного «требует проверки».
- Дубликаты клипов зависят от `processor.min_seconds_between_recordings` — короткий cooldown даёт жёлтый gate намеренно.

## Config audit

- **config_warnings** — требуют внимания (жёлтый).
- **deprecated_keys_present** — только info в hero и «Справка» в карточке аудита.
- **parity_alerts.frigate_*** — скрываются, если `triggers.frigate.enabled: false`.

## Логи процессора

`GET /api/ui/system/logs?lines=N` — хвост `data/processor.log`.

На странице «Система» → Advanced: фильтр по уровню (ERROR / WARNING / INFO / DEBUG). В production держите `processor.birdnet_mqtt_observability_level: off` или `info`, debug — только на время диагностики.

## Readiness и деплой

- `GET /api/ui/readiness` — для smoke/deploy (`make verify`).
- Processor heartbeat: `processor.readiness_heartbeat_max_age_seconds` (по умолчанию 180 с).

## Поддержание «чистоты»

1. Раз в неделю: hero без жёлтых блоков при штатной работе.
2. BirdNET выключен → в диагностике синий «не настроен», не жёлтый «недоступен».
3. После смены Frigate/MQTT — config-audit без лишних parity по выключенному триггеру.
4. Не поднимать пороги strict-quality без причины; при Frigate-heavy площадке низкий % YOLO primary может быть нормой.

См. также: `docs/user/runbooks.md`, `.cursor/rules/deploy.mdc`.
