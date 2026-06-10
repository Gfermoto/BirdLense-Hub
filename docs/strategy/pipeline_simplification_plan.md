# Pipeline simplification plan — motion→detect→classify spine

**Дата:** 2026-06-10  
**Статус:** active execution track  
**Ветка:** `dev`  
**EPIC:** [#633 — Pipeline simplification](https://github.com/Gfermoto/BirdLense-Hub/issues/633)  
**Инцидент:** [a656199a](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057) — detect-first blind + ByteTrack merge двух зон кормушки  
**Предшественники:** [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601) (закрыт), [#606–#613](https://github.com/Gfermoto/BirdLense-Hub/issues/606) (CV recovery), `DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md`, `simplification_optimization_proposal.md`

---

## 1. Executive summary

Prod funnel показал системную ошибку: **внешние сигналы (Frigate, BirdNET, eBird, multicam) стали gate'ами записи и persist**, а не подсказками классификатору. Параллельно накопились salvage/fusion ветки, detect-first как блокер record, и config-kostyli вместо контрактов.

**Цель программы:** вернуть **оригинальный продуктовый позвоночник**:

```text
motion → detection (YOLO/ByteTrack) → classification → DINOv2 → behavior
```

Frigate / BirdNET / eBird / multicamera — **только weighted hints в scoring классификатора**, никогда primary driver для recording, detection gates или fusion persist.

**Частичные шаги уже в dev** ([`2ff464057`](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057)):

| Fix | Что сделано | Что остаётся |
|-----|-------------|--------------|
| OpenVINO native lores | BirdBox 704×576 без принудительного square 704² | Единый bbox space detect→crop→overlay (Phase 2 EPIC) |
| Detect-first raw hits | Anchor по raw YOLO boxes без снижения conf floor | Убрать detect-first как **recording gate** (Phase 1 EPIC) |
| `track_spatial_split` | Split при center jump >0.18 norm | Default-on + crop from best keyframe (Phase 3 EPIC) |
| Frigate assist | Opt-in hint в detect-first anchor | ADR: hints never gate (Phase 0 EPIC) |

---

## 2. Принципы (non-negotiable)

| # | Прinciple | Implication |
|---|-----------|-------------|
| P1 | **Motion triggers record** | Motion/trigger → немедленный hires record **per camera**; YOLO не блокирует старт MP4 |
| P2 | **Detection owns bbox** | YOLO + ByteTrack — единственный источник bbox для crop, overlay, persist geometry |
| P3 | **Classifier hints only** | Frigate label, BirdNET audio, eBird prior, multicam peer — вход **одного** scoring-модуля; веса, не veto |
| P4 | **No salvage architecture** | `restore_detect_first_persist_rows`, weak/frigate salvage, linear fusion gates — удалить или demote в metrics-only |
| P5 | **One bbox space** | Native lores imgsz → remap в playback/main; detect и crop из **одного** keyframe |
| P6 | **Independent cameras** | Multicam = параллельные sessions; нет implicit single-cam lock, блокирующего вторую камеру |
| P7 | **Layers in order** | DINOv2 и behavior **только после** green SLO bbox/crop (IoU gate, funnel) |
| P8 | **Architecture, not config** | Запрет «починить prod» через `user_config` пороги; изменения — ADR + код + тест |

---

## 3. Что REMOVE vs KEEP

### REMOVE / demote

| Surface | Location (indicative) | Action |
|---------|----------------------|--------|
| Detect-first as recording gate | `detect_first.py`, `recording_session.detect_until_confirmed`, `requires_detect_first_before_record` | Record on motion; detect-first → diagnostic only |
| Fusion/salvage persist paths | `recording_finalize_parts/salvage.py`, `restore_detect_first_persist_rows`, weak/frigate salvage | Demote to classifier hints or delete |
| Frigate/BirdNET as detection gate | `frigate_live_track`, `mqtt_frigate_geometry_trigger`, BirdNET FIFO persist gate | Hint injection only |
| Multicam implicit lock | `recording_concurrency.py`, `_same_multi_camera_group` blocking | Independent sessions per camera |
| Dead fusion config + UI | `linear_skip_*`, `detect_first_*` salvage toggles, Settings fusion gates | Delete keys + UI (Phase 4) |
| Config hotfixes in prod | `user_config` threshold patches documented as workarounds | Replace with code contracts |

### KEEP

| Surface | Rationale |
|---------|-----------|
| Dual-stream detect/main RTSP | Frigate-grade geometry; fix remap, not remove stream |
| `inference_lores_wh` native aspect | Extend `2ff464057`; single canvas contract |
| ByteTrack + spatial split | Core track hygiene; default-on after tests |
| `dual_stream_timeline.py` | Offset detect↔record; golden IoU |
| Linear pipeline skeleton | `linear_pipeline.py`, `frame_processor.py`, `finalize_classification.py` |
| Optional integrations as adapters | Frigate MQTT, BirdNET MQTT, eBird API — thin, behind hint module |
| DINOv2 / behavior stacks | Unchanged order; gated on bbox SLO |
| `compare_detector_bboxes.py` | Frigate-parity CI smoke |

---

## 4. Фазы и GitHub issues

```mermaid
flowchart TB
  EPIC["EPIC: Pipeline simplification"]
  I1["#1 ADR classifier hints"]
  I2["#2 Recording contract"]
  I3["#3 Dual-stream geometry"]
  I4["#4 Track hygiene"]
  I5["#5 Demote fusion salvage"]
  I6["#6 Multicam sessions"]
  I7["#7 Frigate-parity CI"]
  I8["#8 Classifier hints module"]
  I9["#9 DINOv2/behavior gate"]
  I10["#10 Dead config/UI cleanup"]
  I11["#11 Perf Coral/OpenVINO"]

  EPIC --> I1
  I1 --> I2
  I1 --> I3
  I2 --> I4
  I3 --> I4
  I4 --> I5
  I2 --> I6
  I3 --> I7
  I5 --> I8
  I7 --> I8
  I8 --> I9
  I5 --> I10
  I9 --> I11
```

| Phase | Issue | Priority | Deliverable |
|-------|-------|----------|-------------|
| 0 | [#634](https://github.com/Gfermoto/BirdLense-Hub/issues/634) ADR: classifier hints contract | P0 | `docs/strategy/adr-classifier-hints-only.md`; lint in `verify_processor_config_drift` |
| 1 | [#635](https://github.com/Gfermoto/BirdLense-Hub/issues/635) Recording contract | P0 | Motion→hires record; drop detect-first gate |
| 1 | [#636](https://github.com/Gfermoto/BirdLense-Hub/issues/636) Dual-stream geometry | P0 | Native lores + single bbox space *(partial: `2ff464057`)* |
| 2 | [#637](https://github.com/Gfermoto/BirdLense-Hub/issues/637) Track hygiene | P1 | Spatial split default; crop from best keyframe |
| 2 | [#638](https://github.com/Gfermoto/BirdLense-Hub/issues/638) Demote fusion salvage | P1 | Hints feed classifier only |
| 2 | [#639](https://github.com/Gfermoto/BirdLense-Hub/issues/639) Multicam independent sessions | P1 | No single-cam lock |
| 2 | [#640](https://github.com/Gfermoto/BirdLense-Hub/issues/640) Frigate-parity benchmark gate | P1 | `compare_detector_bboxes` CI smoke |
| 3 | [#641](https://github.com/Gfermoto/BirdLense-Hub/issues/641) Classifier hints pipeline | P2 | One module: Frigate + BirdNET + eBird weights |
| 3 | [#642](https://github.com/Gfermoto/BirdLense-Hub/issues/642) DINOv2 + behavior after SLO | P2 | Feature flag tied to IoU/funnel green |
| 4 | [#643](https://github.com/Gfermoto/BirdLense-Hub/issues/643) Dead config/UI cleanup | P2 | Remove deprecated fusion gates |
| 5 | [#644](https://github.com/Gfermoto/BirdLense-Hub/issues/644) Performance audit | P3 | OpenVINO iGPU/CPU + W1 queue hygiene (Intel-only; no Coral/CUDA) |

---

## 5. Regression matrix — «Не регрессировать»

| Capability | Metric / test | Baseline |
|------------|---------------|----------|
| Motion→record latency | Time motion event → MP4 first frame | No increase vs post-`2ff464057` |
| YOLO detection rate | `yolo_frames_with_tracks` / session | ≥ current prod median |
| Persist funnel | `post_fusion_persisted` when tracks>0 | ↑ vs 170/282 (incident baseline) |
| Bbox overlay IoU | Golden clips 3× favorite; `compare_detector_bboxes` | Median IoU ≥ gate in #7 |
| TG notify crop | Visual parity lores vs hires crop | No regression (`record_hires_crop`) |
| Multicam | Two cameras motion within 5s | Both sessions complete |
| Classifier accuracy | Golden species pack | No drop >2pp vs champion |
| Finalize p95 | `finalize_duration_ms` p95 | Trend ↓ toward <8s (parallel #601 KPI) |
| Frigate hint | When MQTT present | Species score nudge only; never blocks persist |
| BirdNET hint | Audio overlap window | Weight in classifier; never sole persist row |
| OpenVINO lores | BirdBox 704×576 | Native aspect preserved (`2ff464057`) |
| Spatial split | Two feeder zones one clip | Two tracks after split |

---

## 6. Incident a656199a — root cause & partial fix

**Symptoms:** YOLO «слепой» на prod; ByteTrack сливал двух птиц в одной зоне; detect-first не давал anchor при square resize.

**Root causes (architectural):**

1. OpenVINO forced square imgsz → birds shrunk on lores  
2. Detect-first treated as persist/recording gate instead of diagnostic  
3. No spatial split before crop/classify  
4. Salvage paths masked funnel drops instead of fixing geometry

**Partial fix [`2ff464057`](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057):**

- Native lores for OpenVINO binary track  
- Raw-hits detect-first anchor (counts boxes, not lowered conf)  
- `track_spatial_split` before classify  
- Frigate assist unchanged (opt-in hint)

**Not done:** recording gate removal, salvage demotion, ADR hints contract, multicam lock, CI parity gate.

---

## 7. Success criteria (program exit)

- [ ] ADR accepted; `verify_processor_config_drift` fails if Frigate/BirdNET configured as gate  
- [ ] 7-day prod window: `tracks>0 → persist=0` rate **<10%** (was ~60% at incident)  
- [ ] No prod `user_config` kostyli documented in runbooks for detection/fusion  
- [ ] Golden IoU CI green on merge to `dev`  
- [ ] Operator can explain pipeline in 5 steps: motion→record→detect→classify→(DINOv2→behavior)

---

## 8. Reference architectures (benchmark, not driver)

Frigate, BirdNET-Go, YA-WAMF и родственные feeder-проекты — **референсы для сравнения**, не источники требований. Полный разбор: [`pipeline_simplification_research.md`](pipeline_simplification_research.md).

### Frigate — dual-stream geometry benchmark

| Frigate pattern | BirdLense mapping | Action |
|-----------------|-------------------|--------|
| `detect` role = low-res substream, 5 fps | go2rtc detect RTSP + `inference_lores_wh` | KEEP; native aspect (#636) |
| `record` role = main stream, 15 fps | go2rtc main / hires MP4 | KEEP |
| Bbox on **record timeline** | `_storage_bbox_norm_for_overlay` → main norm | ADOPT single space (#636) |
| Motion → record segments (no object gate) | `recording_session` motion trigger | ADOPT (#635) |
| Detector crop ~320² in detect canvas | YOLO letterbox on lores | OK; не square-force |
| Frigate MQTT events | Classifier hint weight | HINT ONLY (#634, #641) |

**Не копировать:** generic COCO detector (у нас binary+species), отказ от dual-stream, Frigate как primary NVR для Hub.

### BirdNET-Go — audio hint precedence

- Range/location filter → confidence → repeat-confirmation (Deep Detection) → privacy filters.
- Cross-model merge по species key, async JobQueue для persist/notify.
- **У нас:** BirdNET не создаёт persist без YOLO track; adopt optional `hint_repeat_window_sec` в hints module.

### YA-WAMF — Frigate-adjacent classify

- Frigate snapshot → local classifier; BirdNET audio correlation optional.
- Multi-frame clip analysis для ambiguous species.
- **У нас over-built:** salvage persist из Frigate label; **keep:** in-processor finalize, YOLO owns bbox.

### Intel-only constraint

Deploy target: **Intel CPU + iGPU**. Google Coral и NVIDIA CUDA **вне scope** EPIC и Wave 5 (#644).

---

## 9. Intel OpenVINO + iGPU — constraints & best practices

### Platform

| Item | Value |
|------|-------|
| Binary detect backend | OpenVINO IR (`best_openvino_model/`) |
| Live device | `intel:gpu` (iHD), fallback `intel:cpu` with metric |
| Classifier device | Same or `intel:cpu` if VRAM-bound |
| Docker | `/dev/dri/renderD*`, `group_add`, `LIBVA_DRIVER_NAME=iHD` |
| Lores shape | Native aspect (BirdBox 704×576), **no square force** |

### Inference modes

| Mode | When | Config |
|------|------|--------|
| **LATENCY** | Live detect loop (1–2 cameras) | `performance_mode=LATENCY`, 1 async request/stream |
| **THROUGHPUT** | Batch track regen / offline benchmark | Multi-request only in regen worker |
| FP16 | Default GPU compile | OpenVINO export |
| INT8/NNCF | Wave 5 (#644) after IoU gate green | Requires golden re-validation |

### Preprocessing contract

```text
detect frame (WxH native) → letterbox to model [1,3,H,W] (pad 114)
  → inference → bbox in lores space → remap to main/MP4 norm
```

- Export IR with fixed rectangular `[1,3,H,W]` matching `inference_lores_wh`.
- Postprocess: inverse letterbox scale before `yolo_geometry` remap.
- Metric: `bbox_remap_mismatch_total`, backend downgrade counter.

### Anti-patterns (incident lessons)

1. `inference_lores_px` square on 4:3 stream → shrunk birds (a656199a).
2. Silent torch fallback without `inference_backend_fallback_total`.
3. Treating OpenVINO conf parity with torch without `compare_detector_bboxes` gate (#640).

---

## 10. Wave roadmap (0–4) & parallel workstreams

```mermaid
gantt
  title Pipeline simplification waves
  dateFormat YYYY-MM-DD
  section Wave0
  ADR hints #634           :w0, 2026-06-10, 5d
  section Wave1
  Recording #635           :w1a, after w0, 7d
  Geometry #636            :w1b, after w0, 10d
  Multicam #639            :w1c, after w1a, 5d
  CI IoU #640              :w1d, after w1b, 5d
  section Wave2
  Track hygiene #637       :w2a, after w1b, 7d
  Salvage demote #638      :w2b, after w2a, 7d
  section Wave3
  Hints module #641        :w3a, after w2b, 10d
  DINOv2 gate #642         :w3b, after w3a, 5d
  section Wave4
  Config cleanup #643      :w4a, after w2b, 5d
  Perf audit #644          :w4b, after w3b, 7d
```

### Wave 0 — Contract (sequential blocker)

| Stream | Issue | Output |
|--------|-------|--------|
| A | #634 ADR | `adr-classifier-hints-only.md` + drift lint |

**Gate:** ADR merged before any Wave 1 code merge.

### Wave 1 — Spine restore (parallel after #634)

| Stream | Issue | Parallel with | Depends |
|--------|-------|---------------|---------|
| A | #635 Recording contract | B | #634 |
| B | #636 Dual-stream geometry | A | #634 |
| C | #639 Multicam sessions | — | #635 (soft: can start when A is in review) |
| D | #640 Frigate-parity CI | — | #636 partial (native lores landed) |

**Recommended start order (Wave 1):**

1. **#634** — ADR + drift tests (1–2 days).
2. **#635 + #636 in parallel** — recording gate removal + geometry contract.
3. **#639** — после merge или draft PR #635.
4. **#640** — после native lores stable в #636.

### Wave 2 — Track & demotion

| Stream | Issue | Parallel with |
|--------|-------|---------------|
| A | #637 Track hygiene | — |
| B | #638 Salvage demotion | #639 if idle |

### Wave 3 — Hints & advanced layers

| Stream | Issue | Gate |
|--------|-------|------|
| A | #641 Classifier hints module | #638 + #640 green |
| B | #642 DINOv2/behavior gate | #641 + IoU SLO |

### Wave 4 — Cleanup & perf

| Stream | Issue | Notes |
|--------|-------|-------|
| A | #643 Dead config/UI | After #638 |
| B | #644 OpenVINO iGPU perf | Intel-only; after #642 |

---

## 11. Classifier hints module — design sketch

### Purpose

Единая точка входа для внешних сигналов в **scoring** классификатора. Никогда не создаёт persist row, не gate'ит record/detect.

### Module layout (target)

```text
processor/src/classifier_hints/
  __init__.py          # public API
  types.py             # HintSource, HintPayload, ScoringContext
  collectors.py        # Frigate MQTT, BirdNET FIFO, eBird API, multicam peer
  precedence.py        # filter order (range → conf → repeat)
  scorer.py            # merge hints into species scores
  config.py            # weight table (tier: advanced)
```

### Public API

```python
def collect_hints(
    *,
    camera_id: str,
    track: dict,
    mqtt_events: Iterable[dict],
    app_config: Mapping,
    window_sec: float,
) -> list[HintPayload]: ...

def apply_hints_to_rows(
    rows: list[dict],
    hints: list[HintPayload],
    *,
    app_config: Mapping,
) -> list[dict]: ...
```

### Hint sources & weights (default)

| Source | Key | Default weight | Max delta | Gate? |
|--------|-----|----------------|-----------|-------|
| YOLO+classifier base | `base_confidence` | 0.55 | — | N/A (primary) |
| Detector conf | `detector_confidence` | 0.15 | — | No |
| Classifier top-1 | `classifier_confidence` | 0.12 | — | No |
| BirdNET audio | `birdnet_prior` | 0.08 | +0.15 score | No |
| eBird regional | `regional_prior` | 0.05 | +0.10 if in list | No |
| Multicam peer | `multicam_support` | 0.05 | +0.10 | No |
| Frigate label | `frigate_label_hint` | 0.06 | +0.12 | No |

Weights migrate from `weighted_species_arbiter.py`; arbiter becomes thin wrapper → `scorer.py`.

### Precedence (BirdNET-Go inspired)

```text
1. Regional range filter (eBird) — zero weight if species out of range
2. Min confidence floor (classifier) — unchanged
3. Hint score blend (weighted sum, capped)
4. Optional repeat-confirmation: same Frigate/BirdNET species ≥2 in window_sec
5. Output: adjusted confidence + hint_trace[] for decision_trace
```

### Forbidden paths (ADR #634 lint)

- `birdnet_fifo_persist` creating rows without track
- `restore_detect_first_persist_rows`
- `frigate_live_track` / `mqtt_frigate_geometry_trigger` as record start
- `linear_skip_*_salvage` as persist bypass

### Integration point

`finalize_classification.py` → single call:

```python
hints = collect_hints(camera_id=..., track=..., mqtt_events=..., app_config=cfg)
rows = apply_hints_to_rows(classifier_rows, hints, app_config=cfg)
```

### Tests

- `test_classifier_hints.py`: hint nudges top-1; zero rows when tracks empty
- `test_verify_processor_config_drift.py`: forbidden gate keys fail CI

---

## 12. Metrics & SLO per phase

| Phase | Issue | Primary SLO | Secondary metrics | CI gate |
|-------|-------|-------------|-------------------|---------|
| 0 ADR | #634 | Drift lint 100% forbidden patterns | ADR linked in contributor docs | `verify_processor_config_drift` |
| 1a Record | #635 | Motion→MP4 p95 ≤ baseline post-`2ff464057` | `sessions_without_pre_detect_anchor` | `test_recording_session*.py` |
| 1b Geometry | #636 | Overlay IoU median ≥ gate on 3 clips | `bbox_remap_mismatch_total` → 0 trend | `test_yolo_geometry*.py` |
| 1c Multicam | #639 | 2 cameras / 5s → 2 MP4 + 2 DB rows | `multicam_blocked_by_peer_total` → 0 | `test_concurrent_recording_smoke.py` |
| 1d CI parity | #640 | Median IoU ≥ T (conservative start 0.45) | Per-clip debug artifact | `compare_detector_bboxes` job |
| 2a Tracks | #637 | 2-zone clip → ≥2 tracks | TG crop position delta < 5% norm | `test_track_spatial_split.py` |
| 2b Salvage | #638 | `tracks>0 → persist=0` < 25% staging | `salvage_persist_total` → 0 | golden finalize pack |
| 3a Hints | #641 | Golden pack top-1 ±0% with hints off; +2pp with hints on fixture | `hint_trace` in decision_trace | `test_classifier_hints.py` |
| 3b DINOv2 | #642 | Layers skip when `bbox_slo_ok=false` | readiness `bbox_slo_ok` exposed | behavior tests unchanged when green |
| 4a Config | #643 | 0 fusion gate keys in default_config | Settings search clean | drift + UI snapshot |
| 4b Perf | #644 | Finalize p95 < 8s; persist ≤ 40% critical path | OpenVINO LATENCY p50 detect < 80ms | `test_processor_runtime_profile_openvino.py` |

### Program exit SLO (unchanged)

- 7-day prod: `tracks>0 → persist=0` **< 10%**
- Golden IoU CI green on `dev`
- Operator 5-step explainability

---

## 13. References

- Research: [`pipeline_simplification_research.md`](pipeline_simplification_research.md)  
- Commit: [2ff464057](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057) — partial root fix (a656199a)  
- Closed EPIC: [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601) — storage/NVR; superseded for CV spine by this plan  
- CV recovery: [#606](https://github.com/Gfermoto/BirdLense-Hub/issues/606) — dual-stream phases E–G  
- Dual-stream: [`DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md`](DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md)  
- Code: `detect_first.py`, `recording_session.py`, `track_spatial_split.py`, `inference_lores.py`, `recording_finalize_parts/salvage.py`, `recording_concurrency.py`, `weighted_species_arbiter.py`  
- Scripts: `scripts/compare_detector_bboxes.py`, `scripts/report_failure_mode_funnel.py`  
- Reports: `docs/reports/perf/runtime_pipeline_profile_latest.md`, `review_report.md`
