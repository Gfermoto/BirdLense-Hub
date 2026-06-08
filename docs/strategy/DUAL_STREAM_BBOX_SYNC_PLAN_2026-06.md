# Dual-stream bbox sync & hi-res notify (Jun 2026)

**Статус:** Phase E/F/G в dev + prod; #607–#609 закрыты 2026-06-08 после prod verify  
**Связано:** [#606](https://github.com/Gfermoto/BirdLense-Hub/issues/606) EPIC, [#607](https://github.com/Gfermoto/BirdLense-Hub/issues/607) tracks, [#608](https://github.com/Gfermoto/BirdLense-Hub/issues/608) bbox  
**Предшествующий план:** `CV_PIPELINE_RECOVERY_PLAN_2026-06.md`

---

## 0. Полевая картина (Jun 2026)

| Путь | Качество | Почему |
|------|----------|--------|
| **TG crop** | Отличный | `best_frame` с **detect/lores** — тот же кадр, что YOLO/ByteTrack |
| **Video overlay** | Промахи, отставание, редко треки | bbox remap detect→main + desync двух RTSP + sparse `frames[]` @ ~7 fps |
| **Ссылки TG** | OK | notify после `create_video`, `link=videos/{id}` (fix `fdcd2b4ae`) |

**Prod geometry (BirdBox):** detect ~704×576 (`inference_lores_wh`), record 1920×1080, `openvino_binary_track_ultralytics_conf: 0.12`.

---

## 1. Референс: Frigate dual-stream

Frigate использует **detect substream** (motion + object detection) и **record stream** (main) без типичных симптомов Hub:

- Единая **timeline модель**: события и bbox привязаны к **record timeline**, detect — только источник сигнала.
- **Стабильная геометрия**: нормализация bbox относительно **одной** playback-рамки (main), detect масштабируется предсказуемо.
- **Нет «лучшего кадра на lores, overlay на main»** в UI: preview и clip согласованы.
- **Tracker на detect**, persist/clip на record — но **remap + timestamps** согласованы в одном конвейере.

**Цель Hub:** не отказ от dual-stream (как Frigate), а **parity контракта** detect↔record, не «один RTSP».

---

## 2. Принципы реализации

1. **Один playback frame of reference** — все bbox в БД/UI в norm coords **main/MP4**; detect только inference canvas.
2. **Проверяемый remap** — ffprobe MP4 vs `main_size` / `set_playback_frame_shape`; auto-correct + metric.
3. **Timeline sync** — `frame_time` detect + известный offset / shared clock; golden IoU gate.
4. **Плотные track keyframes** — bbox каждый processed detect frame (7 fps достаточно при верном remap).
5. **TG hi-res optional** — crop из `video.mp4` по remapped bbox лучшего keyframe; lores `best_frame` fallback.
6. **Малые PR** — geometry → tracks → notify hires; каждый с тестом и полевой метрикой.

---

## 3. Фазы

### Phase E — Geometry & playback parity (P0)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| E1 | ffprobe session MP4 → `set_playback_frame_shape` (override config mismatch) | IoU median ↑ на 3 favorite clips |
| E2 | Unit + golden: `_storage_bbox_norm_for_overlay` detect 704×576 → main 1920×1080 | test_yolo_geometry extended |
| E3 | Log/metric: `bbox_remap_mismatch_total`, shapes in `decision_trace` | ops visible in readiness |
| E4 | Audit camera detect URL vs main (FOV/aspect) | doc + user_config hint |

**Issue:** child of #607 / #608

### Phase F — Track timeline (P0) — частично в dev

| ID | Deliverable | Status |
|----|-------------|--------|
| F1 | ByteTrack conf contract log + metrics | `bytetrack_contract.py` |
| F2 | Dense frames[] | уже каждый кадр в `update_track` |
| F3 | Scoring moving ROI → REVIEW not REJECT | `scoring_moving_roi_*` |
| F4 | `detect_record_time_offset_sec` per camera | `dual_stream_timeline.py` |

### Phase G — Hi-res TG notify (P1)

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| G1 | `processor.notify_preview_source`: `best_frame_lores` \| `record_hires` \| `auto` | activity_log `preview_source` |
| G2 | `record_hires`: seek MP4 @ best keyframe `t`, crop remapped bbox + pad | visual parity with lores position |
| G3 | Fallback chain: hires → lores best_frame → bbox_crop | no empty TG |

---

## 4. Rollback

```bash
git checkout 770b5f080   # или tag после checkpoint commit
# user_config на VPS не откатывается деплоем — бэкап отдельно
```

---

## 5. Не делаем в этой волне

- Single-stream YOLO на main (cost/latency) — только если E–F не дадут parity.
- Массовый refactor fusion/legacy — linear only.
- Автокоммит `docs/reports/*` от deploy gates.
