# CV Pipeline Recovery Plan (Jun 2026)

**Дата:** 2026-06-05  
**Статус:** Активный execution track (дополняет [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601), не заменяет storage/infrastructure)  
**GitHub EPIC:** [#606](https://github.com/Gfermoto/BirdLense-Hub/issues/606)

---

## 0. Симптомы в поле (VPS/LAN, после track-first + placeholder Bird/Rodent)

| Симптом | Оператор видит | Метрика / сигнал |
|---------|----------------|------------------|
| **Нет треков** | Overlay пустой, `yolo_frames_with_tracks=0` | ByteTrack `boxes.id is None`, post-filters, detect-first без anchor |
| **Ложные рамки** | Квадраты на фоне/кормушке, «залипание» | `auto_unstick` слишком поздно, `tracker_remember_seconds`, salvage/predict fallback |
| **Промахи по птицам** | Птица в кадре, запись есть, persist пустой | `min_confidence_binary` 0.25+, object_confirm, `min_track_duration` |
| **Классификация = Bird** | Почти всегда «Птица», редко вид | `classifier_defer_to_finalize: true` + weak Birder → linear fallback `"Bird"` |
| **Неверный вид** | Синица → мышь и наоборот | Низкий `birder_eu_min_confidence`, нет species consensus на finalize |

**Корневая ошибка:** накопленный слой legacy-порогов, hardcoded fallback в коде ≠ `default_config.yaml`, и defer-classifier без жёсткого acceptance на species.

---

## 1. Принципы (anti-legacy)

1. **Один контракт конфигурации** — все runtime-пороги из merged config; код не содержит «тайных» default 0.22/0.30/180, только `config_defaults.py` ↔ `default_config.yaml`.
2. **Linear pipeline only** — `pipeline_mode: legacy` удаляется; decision path = `linear_pipeline.py`.
3. **Track-first invariant** — persist только с bbox+track; Frigate/MQTT = hint, не standalone row (уже `frigate_standalone_when_no_yolo: false`).
4. **Honest metrics** — каждый reject с `reject_reason_code`; funnel в readiness (#605).
5. **No silent salvage** — `ultra_weak_box_salvage`, `track_to_predict_fallback`, `iou_id_fallback` только через явный camera_profile + metric.
6. **Species ≠ Bird by default** — placeholder Bird только при `detector_only` evidence; после finalize Birder ≥ threshold → named species или `needs_review`, не sticky Bird.

---

## 2. Целевой пайплайн (упрощённый)

```
Trigger → detect-first (lores confirm) → record main
    → YOLO binary + ByteTrack (conf aligned to YAML)
    → quality gates (geometry IoU reject, static filter, scoring)
    → linear decision (duration, object_confirm, bbox frames)
    → finalize: Birder on best_frame crop(s)
    → species vote / calibration → persist (Bird|Species|review)
```

**Не делаем:** новый fusion arbiter, frigate_standalone rows, classifier veto на live при `binary_track_first`.

---

## 3. Фазы

### Phase A — Tracks exist (P0, 1–2 нед)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| A1 | ByteTrack conf contract: `track(conf)` > `track_high_thresh` в materialized YAML | На favorite mp4: `yolo_frames_with_tracks / yolo_frames_ran ≥ 0.15` |
| A2 | Убрать fallback drift: `auto_unstick_no_track_frames` etc. из кода → config defaults module | Unit test: missing key = default_config value, не 180 |
| A3 | IoU id fallback: метрика + disable по default на prod profile | `bytetrack_rows` correlates with `yolo_frames_with_tracks` |
| A4 | Detect-first ↔ live parity: anchor conf не ниже live floor | `detect_first_confirmed` → first live track ≤ 2s |

**Issues:** #607 (A1–A4)

### Phase B — Bbox quality / false positives (P0, 1–2 нед)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| B1 | `bbox_iou_gate_action: reject` (не warn) на prod profile | phantom full-frame boxes ↓ на golden set |
| B2 | Static/temporal filter: default ON для feeder; audit unstick bird floor 0.03 | FP rate ↓ без recall collapse на golden |
| B3 | `tracker_remember_seconds` ≤ 2.0 default; unstick tracker не держит ghost bbox | sticky overlay ↓ в UI |
| B4 | Salvage/predict fallback: off by default, opt-in per `camera_tuning_by_role` | no boxes at conf < 0.05 unless profile |

**Issues:** #608 (B1–B4)

### Phase C — Species resolution (P0, 2 нед)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| C1 | Finalize Birder: top1_confidence fix (done), multi-crop vote | named species rate ↑ on labeled favorites |
| C2 | Linear: не возвращать `"Bird"` если classifier_events пуст — `detector_only` + review flag | UI shows «Птица (детектор)» not fake species |
| C3 | Species consensus window на finalize (median top-k crops) | wrong-species ↓ vs single-frame |
| C4 | Calibrated thresholds from config only (`birder_eu_min_confidence`, ECE hook) | no hardcoded 0.15 in code paths |

**Issues:** #609 (C1–C4)

### Phase D — Legacy removal (P1, 2–3 нед)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| D1 | Remove `pipeline_mode: legacy` code paths | grep clean, tests green |
| D2 | Deprecate `detection.min_confidence_to_store` veto | only linear + btf |
| D3 | `processor_config_defaults.py` + CI drift test vs default_config.yaml | PR fails on orphan hardcode |
| D4 | Delete unused fusion/hypothesis branches | coverage maintained |

**Issues:** #610 (D1–D4)

### Phase E — Regression gate (P1, 1 нед)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| E1 | Golden favorite mp4 set + `make pipeline-golden` | CI/local: tracks>0, persist>0, species≠Bird on ≥1 clip |
| E2 | Nightly prod funnel export → issue auto-comment if red | ops visibility |

**Issues:** #611 (E1–E2)

---

## 4. Связь с открытыми issues

| Issue | Отношение |
|-------|-----------|
| [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601) EPIC Consortium | Storage/NVR parity — **parallel**, не блокирует Phase A–C |
| [#605](https://github.com/Gfermoto/BirdLense-Hub/issues/605) Honest readiness | Phase A/B funnel metrics — **dependency** |
| [#602–604](https://github.com/Gfermoto/BirdLense-Hub/issues/602) | Finalize/storage — orthogonal |
| Closed [#591](https://github.com/Gfermoto/BirdLense-Hub/issues/591), [#590](https://github.com/Gfermoto/BirdLense-Hub/issues/590) | Code landed; **field acceptance failed** → этот plan |

### Superseded (comment only, не reopen)

- [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517) Frigate superiority → split: #601 (NVR) + CV EPIC (quality)
- [#555](https://github.com/Gfermoto/BirdLense-Hub/issues/555) pipeline TZ → largely done; residual → CV EPIC
- [#557](https://github.com/Gfermoto/BirdLense-Hub/issues/557) domain retrain → **Phase F** after E green

---

## 5. Config checklist (prod audit)

Проверить merge `default_config.yaml` + `user_config.yaml`:

```yaml
processor.pipeline_mode: linear
processor.classifier_defer_to_finalize: true   # OK if finalize C1–C3 green
processor.min_confidence_binary: ≤ 0.18       # prod often 0.25 — too high
processor.min_confidence_binary_bird: ≤ 0.18
processor.openvino_binary_track_ultralytics_conf: < bird floor
processor.auto_unstick_no_track_frames: 10     # NOT 180 in code fallback
processor.tracker_remember_seconds: ≤ 2.0
detection.persist_mode: binary_track_first
detection.bbox_iou_gate_action: reject
detection.frigate_standalone_when_no_yolo: false
```

---

## 6. Definition of Done (CV EPIC)

На VPS/LAN, 7 дней, без skip-gates:

1. `yolo_frames_with_tracks > 0` в ≥ 80% sessions с `yolo_frames_ran > 30`
2. `post_fusion_persisted > 0` когда `bytetrack_rows > 0` в ≥ 70% sessions
3. Named species (не placeholder Bird) в ≥ 25% bird sessions с visible bird in clip
4. FP phantom boxes: operator review queue FP rate ↓ vs baseline (golden set)
5. No hardcoded threshold in processor hot path (CI guard)

---

## 7. Immediate actions (2026-06-05)

1. Create GitHub EPIC + child issues (#606–#611)
2. Comment supersede links on #517, #591, #590, #555
3. Fix `frame_processor` auto_unstick `or 180` bug (same day)
4. Update `docs/contributor/roadmap.md` primary epic → #601 + CV EPIC
5. Prod config audit script → `scripts/audit_processor_config_drift.py` (exists in reports?) 
