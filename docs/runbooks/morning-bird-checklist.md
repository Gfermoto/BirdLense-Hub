# Утренний чеклист BirdLense (~5 минут)

Короткая проверка **до или вместе с первыми птицами** на prod-хабе. Не требует правок конфигов и секретов.

Связано: [hub-incident-protocol](../contributor/hub-incident-protocol.md), [troubleshooting.ru](../ru/troubleshooting.ru.md), [yolo-blind-runbook.ru](../ru/yolo-blind-runbook.ru.md).

---

## 1. Живость хаба (30 с)

На VPS (пример):

```bash
curl -sf http://185.218.111.196:8085/api/ui/health
curl -sf http://185.218.111.196:8085/api/ui/readiness
```

Ожидание:

| URL | Что смотреть |
|-----|----------------|
| `http://185.218.111.196:8085/api/ui/health` | `"status":"ok"` |
| `http://185.218.111.196:8085/api/ui/readiness` | `checks.database`, `checks.cache_backend`, `checks.processor_heartbeat` — без критичных `status:"error"` |

Публичные пути **`/health`** и **`/readiness`** на том же порту могут отдавать SPA; для автоматики и деплоя используйте **`/api/ui/*`** (контракт: [health-readiness-contract](./health-readiness-contract.md)).

Docker на хосте:

```bash
docker ps --filter name=birdlense --format '{{.Names}} {{.Status}}'
```

Ожидание: `birdlense` и `birdlense-redis` — **Up (healthy)**.

---

## 2. Логи процессора (2 мин)

Окно: последние 1–3 завершённые сессии.

```bash
docker logs birdlense 2>&1 | grep recording_session_summary | tail -5
docker logs birdlense 2>&1 | grep -E 'yolo_blind_confirmed|yolo_blind_suspected' | tail -10
docker logs birdlense 2>&1 | grep detection_acceptance_gap | tail -5
docker logs birdlense 2>&1 | grep post_fusion_persisted | tail -5
```

Или одной строкой JSON в `recording_session_summary` (поля воронки):

- `yolo_frames_with_raw_boxes`, `yolo_accepted_boxes_total`
- `yolo_frames_with_tracks`, `bytetrack_rows`
- `post_fusion_persisted`, `db_persist_success`
- `detection_acceptance_gap` (boolean)
- `yolo_blind_suspected` / `yolo_blind_confirmed`

---

## 3. Воронка в UI — что означает «ноль»

Откройте **Система → Detection Quality / воронка** (или аналог в текущем UI) после первой утренней записи.

| Метрика | Если 0 | Действие |
|---------|--------|----------|
| **Raw** (сырые боксы YOLO) | Нет детекций на кадрах | Проверить YOLO blind ([yolo-blind-runbook.ru](../ru/yolo-blind-runbook.ru.md)), IR/веса, `inference_backend` / device в **ml-runtime** (без правки секретов) |
| **Accepted** | Raw > 0, accepted = 0 | Пороги `min_confidence_*`, geometry gate; смотреть `quality_reject_counts` в summary |
| **Tracks** | Accepted > 0, tracks = 0 | Трекер / FPS; см. [tracking-low-fps.ru](../ru/tracking-low-fps.ru.md) |
| **Persist** (`post_fusion_persisted`) | Tracks > 0, persist = 0 | Fusion / decision engine; `detection_acceptance_gap: true` → incident-код `FUSION_NO_ACCEPTED` |
| **TG** (уведомления) | Persist > 0, TG нет | Если в конфиге **`notifications.disable_notification: true`** — Telegram намеренно тихий; иначе проверить канал уведомлений в UI (токены не логировать) |

---

## 4. Telegram и offline regen

- **`notifications.disable_notification`** — сообщения без звука/алерта; не путать с «сломанным ботом».
- **`processor.track_regen_match_live_pipeline: false`** — офлайн **regen ≠ live**: другие пороги/geometry; бенчмарк `benchmark-track-regen.py` **не доказывает** паритет с утренним потоком. Для паритета см. [tracking-parity.ru](../ru/tracking-parity.ru.md) (`track_regen_match_live_pipeline: true`).

---

## 5. Быстрый offline smoke (опционально)

Только если нужно сравнить regen на golden-клипе, **не** во время пиковой нагрузки:

```bash
cd /root/BirdLense
python3 scripts/benchmark-track-regen.py \
  --video app/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4 \
  --frame-step 2 \
  --write-report /tmp/benchmark_track_regen.json
```

Смотреть JSON: `raw_track_count`, `fused_track_count`, `inference_backend` / `inference_device`.

---

## 6. Когда эскалировать

- `yolo_blind_confirmed` или серия `yolo_blind_suspected` + `yolo_frames_with_tracks=0` при живых Frigate-триггерах.
- `post_fusion_persisted=0` при `bytetrack_rows>0` или `detection_acceptance_gap: true`.
- Readiness не ready / контейнер не healthy.

Дальше — [hub-incident-protocol](../contributor/hub-incident-protocol.md), без трогания Frigate и чужих контейнеров без явного OK.

---

## Запреты (prod)

- Не коммитить и не вставлять в тикеты: `.env`, MCP/API токены, пароли.
- Не выполнять `docker image prune -a`, `volume prune`, не рестартить Frigate без согласования.
