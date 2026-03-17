# Аудит: пропуск событий Frigate (BirdLense не записывает)

**Контекст:** Frigate обнаружил bird на камере Forest в 08:24:01, BirdLense событие не зафиксировал.

---

## Сводная таблица причин

| # | Причина | Вероятность | Как проверить |
|---|---------|-------------|---------------|
| 1 | `motion.source: opencv` (дефолт) | **Высокая** | `user_config.yaml` → `motion.source` |
| 2 | Forest не в `video.cameras` | **Высокая** | cam_f = cameras → Forest отфильтрован |
| 3 | События во время записи терялись | **Средняя** | Исправлено (pending check) |
| 4 | MQTT QoS 0 — потеря при reconnect | **Средняя** | subscribe без qos=1 |
| 5 | MQTT отключён в момент события | **Средняя** | Логи reconnect |
| 6 | Ошибка парсинга payload — тихий пропуск | **Низкая** | Нет логов при parse error |
| 7 | `frigate_label_filter` пустой | **Средняя** | Конфиг |
| 8 | Несколько камер — только последняя | **Средняя** | _last_camera перезаписывается |
| 9 | `frigate_topic` не совпадает с Frigate | **Низкая** | topic_prefix во Frigate |
| 10 | MQTT не подключился за 5 сек → fallback OpenCV | **Средняя** | main.py:216-222 |

---

## 1. motion.source (КРИТИЧНО)

**Код:** `main.py:176-180`, `default_config.yaml:59`

```yaml
motion:
  source: opencv  # дефолт!
```

**Логика:** `use_frigate_from_aggregator = (motion.source in ('frigate','mqtt') and mqtt_broker and not mqtt_topic)`.

При `opencv` Frigate **вообще не используется** для триггера записи. События приходят в aggregator (для merge с YOLO), но `on_frigate_motion` = None — callback не регистрируется.

**Проверка:** `motion.source` должен быть `frigate` или `mqtt` (и `mqtt_topic` пустой).

---

## 2. frigate_camera_filter и video.cameras (КРИТИЧНО)

**Код:** `main.py:165-169`, `mqtt_aggregator.py:280-282`

```python
frigate_camera_filter = (
    app_config.get('motion.frigate_camera_filter')
    or app_config.get('mqtt.frigate_camera_filter')
    or [c['id'] for c in cameras]  # ← дефолт = список камер!
)
cam_ok = not cam_f or (camera.lower() in cam_lower)
```

**Проблема:** Если оба фильтра пусты, используется `video.cameras[].id`. Камера "Forest" из Frigate должна **совпадать** с `id` в `video.cameras`. Если в BirdLense только `BirdBox`, события от Forest **отбрасываются**.

**Проверка:** В `video.cameras` должна быть камера с `id: "Forest"` (или явно `frigate_camera_filter: []` для «любая камера» — но тогда `cam_f=[]` только если cameras пуст).

**Важно:** Явный `frigate_camera_filter: []` в YAML даёт `[]`; `[] or ...` → берётся следующий вариант. Чтобы «любая камера», нужно чтобы в цепочке получился пустой список. Сейчас при `cameras: [{id: BirdBox}]` cam_f = `["BirdBox"]` — Forest не пройдёт.

---

## 3. События во время записи (ИСПРАВЛЕНО)

**Было:** `detect()` вызывал `event.clear()` до проверки → события, пришедшие во время записи, терялись.

**Стало:** Проверка `if self._event.is_set()` до `clear()` — pending-события обрабатываются.

---

## 3b. Pending: MQTT-события вне окна (ИСПРАВЛЕНО)

**Было:** При pending trigger запись начинается с опозданием (после предыдущей). Событие Frigate было 30–60 сек назад. `get_events_in_window(start, end, 8)` ищет в [start-8, end+8]. Событие вне окна → `mqtt_events=[]` → merge пустой → запись удаляется.

**Стало:** При 0 YOLO и Frigate trigger — `lookback_seconds=60` в `get_events_in_window`.

---

## 4. MQTT QoS

**Код:** `mqtt_aggregator.py:322`

```python
self._client.subscribe(self.frigate_topic)  # QoS по умолчанию = 0
```

При QoS 0 сообщения могут теряться при нестабильной сети или reconnect брокера.

**Рекомендация:** `subscribe(self.frigate_topic, qos=1)`.

---

## 5. MQTT reconnect

Во время переподключения (до 300 с) события не доставляются. При частых обрывах возможны пропуски.

---

## 6. Ошибки парсинга Frigate payload

**Код:** `mqtt_aggregator.py:31-34`

```python
try:
    data = json.loads(payload.decode())
except (json.JSONDecodeError, UnicodeDecodeError):
    return None  # без логов!
```

При невалидном JSON событие тихо отбрасывается.

**Рекомендация:** Логировать `logger.warning("Frigate parse error: %s", e)`.

---

## 7. frigate_label_filter пустой

**Код:** `mqtt_aggregator.py:283-285`

```python
lbl_ok = bool(lbl_f_lower & labels_lower)
```

Если `frigate_label_filter` = `[]` → `lbl_f_lower` = `set()` → `lbl_ok` = False → все события отбрасываются.

**Проверка:** `frigate_label_filter` не должен быть пустым (дефолт `["bird","Bird"]`).

---

## 8. Несколько камер — только последняя

При событиях Forest 08:24:01 и BirdBox 08:24:03 в одной «сессии» `_last_camera` перезаписывается. Запись будет для BirdBox; Forest визуально «потерян» (хотя оба события вызвали запись, если они пришли в разное время detect()).

При событиях **во время одной записи** — теперь pending обрабатывается, но `_last_camera` = последняя камера. Если нужно записывать обе — требуется очередь событий.

---

## 9. frigate_topic и topic_prefix Frigate

Frigate по умолчанию публикует в `frigate/events`. Если в Frigate задан `mqtt.topic_prefix: myfrigate`, топик будет `myfrigate/events`. В BirdLense `mqtt.frigate_topic` должен совпадать.

---

## 10. MQTT не подключился за 5 сек

**Код:** `main.py:216-222`

```python
for _ in range(5):
    if mqtt_aggregator.is_connected():
        break
    time.sleep(1)
if not mqtt_aggregator.is_connected():
    logging.warning('Frigate MQTT not connected, falling back to OpenCV')
    motion_detector = OpenCVMotionDetector(...)
```

При старте, если MQTT не успел подключиться за 5 с, используется OpenCV. Frigate не триггерит.

---

## Рекомендуемый порядок проверки

1. **motion.source** — `frigate` или `mqtt`?
2. **video.cameras** — есть ли `id: "Forest"` (или как во Frigate)?
3. **Логи** — `Frigate event skipped (no trigger)` с camera_filter/label_filter?
4. **Логи** — `Frigate trigger` — были ли вообще триггеры в то утро?
5. **Логи** — `MQTT aggregator disconnected`, `Frigate MQTT not connected`?
6. **API** — `GET /api/ui/status` → `mqtt: ok`?
7. **Frigate** — `topic_prefix`, совпадает ли с `mqtt.frigate_topic`?

---

## Рекомендуемые исправления кода

| Изменение | Файл | Описание |
|-----------|------|----------|
| QoS 1 для subscribe | mqtt_aggregator.py | `subscribe(..., qos=1)` |
| Логирование parse error | mqtt_aggregator.py | При `_parse_frigate_event` → None |
| Явная опция «любая камера» | default_config / main | `frigate_camera_filter: []` = any, не fallback на cameras |
| Метрика пропущенных | mqtt_aggregator | Счётчик skipped events для мониторинга |
