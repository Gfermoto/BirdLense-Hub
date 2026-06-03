# Консилиум: архитектурный план BirdLense Hub (не «набор фиксов»)

**Дата:** 2026-06-03  
**Статус:** Утверждён консилиумом (issue-источник правды — GitHub EPIC)  
**Цель:** Hub **не хуже Frigate** по надёжности записи/хранения/диагностики на тех же камерах; **лучше Frigate** — по виду, поведению, ReID (только после базового контракта).

---

## 0. Почему предыдущие планы провалились (5-я попытка — с другой premiss)

| Попытка | Что делали | Почему не сработало |
|---------|------------|---------------------|
| #435 Hub reliability | Workstreams W1–W4, KPI | Закрыт без field acceptance; метрики «parity» не стали blocking |
| #517 Frigate superiority | EPIC качества | **CLOSED** при `acceptance_blocked: True` в reality-check |
| SOTA Waves #528–#580 | 32+ deploy gates, DORA, OWASP | Control plane без **инвариантов продукта**; deploy со skip-gates |
| Track-first #591–#600 | Fusion, persist tail | Закрыты по чеклисту; prod: 14 favorite, orphan 79 GB, funnel 170/282 drop |
| Точечные фиксы (retention, JPG) | Патчи симптомов | Не меняют модель: disk≠DB, health врёт, config drift |

**Корневая ошибка:** путали *«закрыть issue / пройти gate»* с *«система ведёт себя предсказуемо для оператора»*.  
**Этот план:** сначала **инварианты и контракты**, потом ML/SOTA; каждая фаза — working software + blocking acceptance на prod.

---

## 1. Консилиум: роли и мандат

| Роль | Вопрос | Veto |
|------|--------|------|
| **NVR-архитектор** (реф. Frigate) | Файл, БД, retention — один контур? | Любой auto-job без порога |
| **Pipeline-инженер** | Trigger→clip→detect→persist — атомарно? | Новые fusion-gate без funnel metric |
| **SRE/Ops** | Deploy меняет только то, что задумано? | Skip-gates на prod deploy |
| **Оператор продукта** | Почему пропало — видно за 2 мин? | Health=ok при blind persist |
| **ML-лид** (фаза 5+) | Улучшаем вид после integrity | ML до зелёного ingest |

**Мандат:** не добавлять фичи и governance-artifacts, пока не зелёны **Phase 0–2 acceptance** на VPS/LAN.

---

## 2. Бенчмарк конкурентов (критический разбор)

### 2.1 Frigate — эталон NVR-слоя

| Принцип | Frigate | BirdLense сейчас | Вывод |
|---------|---------|------------------|-------|
| **Запись** | Remux с камеры, сегменты ~60s, cache→disk по policy | Re-encode через Go2RTC/ffmpeg, session dir | Latency, артефакты, CPU ↑ |
| **Метаданные** | SQLite: `Recordings` row **на файл** | Video row после HTTP POST finalize | Orphan disk / orphan DB |
| **Retention** | `RecordingCleanup` / `EventCleanup` / `StorageMaintainer`; trim **до порога**; `retain_indefinitely` | Scheduler + cascade; недавно — gate (fix) | Семантика «квота», не «cron-бомба» |
| **Disk↔DB** | `sync_recordings` опционально | Manual Scan + orphan purge UI | Должен быть **startup reconcile** |
| **Событие** | Event = object track + clip ref | SpeciesVisit через fusion gates | 170/282 sessions: tracks>0, persist=0 |
| **Диагностика** | Review, metrics, logs per camera | Readiness ok, yolo unknown | Health не отражает funnel |

Источники: [Frigate record config](https://docs.frigate.video/configuration/record/), storage/cleanup threads (RecordingCleanup, StorageMaintainer).

**Перенимаем:** row-per-artifact, quota-trim, retain flag (= favorite), disk sync job, emergency space maintainer **отдельно** от age policy.

**Не копируем слепо:** Frigate не делает species/ReID — это **Hub differentiation** (фаза 5).

### 2.2 Другие референсы

| Продукт | Берём | Не берём |
|---------|-------|----------|
| **BirdNET-Go** | Спектrogram pipeline, MQTT события | Замена YOLO bbox |
| **Home Assistant + Frigate** | Frigate как trigger **hint** | «Frigate видит = OK» |
| **Scrypted NVR** | Локальный first, один config | Перегруз plugin-моделью |

---

## 3. Архитектурные инварианты (конституция Hub)

1. **I1 — Storage quota:** политика = *ограничить рост*; удаление только **старейшего/просроченного** до порога; cap за прогон; **никогда** full sweep по расписанию.
2. **I2 — Artifact integrity:** каждый `video.mp4` → `{state: pending|ready|failed}` + row или явная очередь; finalize **atomic** (commit или rollback dir).
3. **I3 — Honest health:** `/readiness` degraded если persist funnel < SLO или detector blind (не `yolo: unknown` при ok).
4. **I4 — Effective config:** один merged config + versioned migration; prod drift = **blocking** deploy gate.
5. **I5 — Deploy artifact:** bundled static assets + weights contract; **не** «exclude data + entrypoint hack».
6. **I6 — Frigate parity baseline:** Frigate event в окне ⇒ Hub **clip exists + playable** OR classified miss reason (не молчание).

Нарушение инварианта = P0 bug, не «известное ограничение».

---

## 4. Целевая архитектура (упрощённо)

```
Trigger (opencv|frigate|…) 
    → SessionController (one clip, one session_id)
        → RecordWriter (mp4 + sidecar manifest.json)
        → DetectTrack (YOLO+ByteTrack, live overlay)
        → FinalizeTransaction
              BEGIN
                validate mp4
                POST ingest OR local DB write same txn boundary
                write session_runtime_metrics
              COMMIT | ROLLBACK (remove dir on hard fail)
    → QuotaMaintainer (on threshold only, oldest first)
    → ReconcileJob (startup + daily: disk ↔ DB)
```

**Ключ:** SessionController владеет жизненным циклом; web/processor не расходятся через fire-and-forget HTTP без idempotency.

---

## 5. Фазы (порядок обязателен)

### Phase 0 — Stop misleading green (1–2 нед)

**Проблема:** система «зелёная», оператор видит пустоту.

| # | Deliverable | Acceptance (prod/LAN) |
|---|-------------|------------------------|
| 0.1 | Readiness: yolo/persist funnel в components | degraded если blind или drop rate > X |
| 0.2 | API retention GET: defaults = default_config | auto_run не «true by default» в API |
| 0.3 | Prod user_config audit | documented effective retention + drift diff |
| 0.4 | Заморозка новых auto-* flags без ADR | PR checklist |

**Не делаем:** новые gates без привязки к I1–I6.

---

### Phase 1 — Recording & Storage Contract (4–6 нед) — **Frigate parity core**

| # | Deliverable | Frigate analog | Acceptance |
|---|-------------|----------------|------------|
| 1.1 | **FinalizeTransaction** wrapper | atomic write | 0 orphan sessions за 7d после rollout |
| 1.2 | **Session manifest** (`manifest.json`: session_id, paths, state) | segment metadata | replay/import без synthetic 30s |
| 1.3 | **QuotaMaintainer** single module | RecordingCleanup + StorageMaintainer | один code path: scheduler, API, max_gb |
| 1.4 | **ReconcileJob** startup+daily | sync_recordings | orphan count → 0 без manual purge |
| 1.5 | **retain_indefinitely** = favorite + session dir | Event.retain_indefinitely | retention skip proven in tests |

**Anti-patterns:** orphan purge UI как primary path; отдельный rsync images; entrypoint cp overwrite.

**KPI:** artifact integrity rate ≥ 99.5%; orphan_bytes / total_recordings → < 1%.

---

### Phase 2 — Persist Funnel (4–6 нед)

**Проблема:** 170/282 `decision_fusion_drop_tracks_gt_0_persisted_0`; 646 static_pinned.

| # | Deliverable | Acceptance |
|---|-------------|------------|
| 2.1 | **Persist funnel dashboard** (API+UI) | top reject reasons per camera, 24h |
| 2.2 | Per-**camera_profile** gates (not global 646 reject) | Forest static_pinned ↓ 50% без FP↑ |
| 2.3 | **Miss reason codes** (Frigate seen, Hub not) | 100% classified in parity window |
| 2.4 | Empty clip policy explicit | fp_empty_recording opencv < 20% (#I9) |
| 2.5 | Trigger moratorium visible in UI | operator sees «запись paused» |

**North star:** `healthy_persisted_gt_0` / sessions ≥ 70% (сейчас ~22%).

**Anti-patterns:** новый fusion layer; «Frigate fallback» без track persist.

---

### Phase 3 — Operator Truth (3 нед)

| # | Deliverable | Acceptance |
|---|-------------|------------|
| 3.1 | Daily **Frigate↔Hub parity report** (automated) | mismatch rate trend |
| 3.2 | System card: disk, quota, orphan, funnel | one screen, no log spelunking |
| 3.3 | Incident template wired to API | MTTR classify < 15 min |

Ref: `docs/contributor/hub-reliability-and-quality-plan.md` W1+W3 — **реализовать**, не переписать.

---

### Phase 4 — Deploy & Config Contract (3 нед)

| # | Deliverable | Acceptance |
|---|-------------|------------|
| 4.1 | **Artifact manifest** (images, default seeds) checksum in CI | 0-byte JPG impossible |
| 4.2 | Config schema + migration on startup | verify-prod-config-drift blocking |
| 4.3 | Prod deploy: **≤3 skip-gates**, audit log | no skip without reason file |
| 4.4 | Post-deploy smoke: ingest+health+funnel | deploy fails if red |

---

### Phase 5 — Hub > Frigate (ML/UX, после зелёного 1–4)

Только когда `acceptance_blocked: False` **4 недели подряд**:

- Domain detector/classifier (#557 scope) с champion/challenger
- Behavior/ReID без регресса I2
- Active learning — opt-in, not default mine

---

## 6. Метрики программы (weekly, blocking)

| Metric | Сейчас (2026-06-02) | Target Phase 2 | Target Phase 4 |
|--------|---------------------|----------------|----------------|
| fusion_drop / sessions | 170/282 (60%) | < 20% | < 10% |
| fp_empty opencv | 43.6% | < 20% | < 15% |
| orphan disk GB | ~79 | < 1 | 0 |
| acceptance_blocked | True | False 2w | False 4w |
| unexplained miss | ad-hoc | 0/week | 0/week |
| finalize_p95 | 63s | < 30s | < 20s |

---

## 7. Что явно НЕ делаем (anti-roadmap)

- ❌ Новые deploy gates без product KPI
- ❌ Закрытие EPIC по чеклисту при red reality-check
- ❌ UI purge/orphan как «решение» без Phase 1
- ❌ Ещё один scheduler «что-то чистит каждые N часов»
- ❌ SOTA documentation waves вместо FinalizeTransaction

---

## 8. Дочерние issues (создать из EPIC)

| ID | Title | Phase |
|----|-------|-------|
| #605 | [P0] Honest readiness: funnel + yolo status | 0.1 |
| #602 | [P0] FinalizeTransaction: atomic clip + DB | 1.1 |
| #603 | [P0] QuotaMaintainer: unified trim module | 1.3 |
| #604 | [P0] ReconcileJob: disk↔DB startup sync | 1.4 |
| #606 | [P1] Persist funnel dashboard per camera | 2.1 |
| TBD | [P1] camera_profile static gate calibration | 2.2 |
| TBD | [P1] Frigate↔Hub daily parity report | 3.1 |
| TBD | [P1] Deploy artifact manifest + config migration | 4.1–4.2 |

---

## 9. Definition of Done (вся программа)

- [ ] Оператор на prod: новая запись ⇒ timeline ≤ 5 min без manual scan
- [ ] Retention: disk stable под max_gb/days; favorites never auto-deleted
- [ ] Frigate parity: mismatch classified; rate ↓ 4 weeks
- [ ] Deploy без skip-gates проходит на VPS; post-deploy smoke green
- [ ] `sota_reality_check`: decision=go **4 consecutive weeks**
- [ ] Документ **устаревшие** closed EPIC (#517) помечены «superseded by Consortium EPIC #XXX»

---

## 10. Связанные документы

- `docs/contributor/hub-reliability-and-quality-plan.md` — W1–W4 входят в Phase 2–3
- `app/processor/src/README.md` — north star сценарии (сохраняем)
- `docs/reports/quality_outcome/failure_mode_funnel_latest.md` — baseline metrics
- `docs/strategy/SOTA_ALL_WAVES_MASTER_PLAN_2026.md` — Phase 5+ только после integrity
