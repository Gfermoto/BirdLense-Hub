# Pipeline simplification — external research (2026-06-10)

**Связано:** [`pipeline_simplification_plan.md`](pipeline_simplification_plan.md), EPIC [#633](https://github.com/Gfermoto/BirdLense-Hub/issues/633)

Цель: сравнить референсные архитектуры с планом BirdLense Hub, выделить adopt / over-built, зафиксировать ограничения Intel OpenVINO+iGPU (без Coral, без CUDA).

---

## 1. Frigate NVR — dual-stream benchmark

### Архитектура

Frigate разделяет **роли RTSP-потоков** на уровне камеры:

| Role | Назначение | Типичные параметры |
|------|------------|-------------------|
| `detect` | Motion + object detection (единственный декодируемый поток для inference) | Substream, 5 fps, низкое разрешение |
| `record` | Сегменты MP4 для архива | Main stream, 15 fps, max resolution |
| `audio` | Audio-based detection (опционально) | Отдельный feed |

Источники:
- [Frigate camera configuration — stream roles](https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/configuration/cameras.md)
- [Frigate camera setup guide](https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/frigate/camera_setup.md)
- [Discussion #20367 — detect stream required even for record-only](https://github.com/blakeblackshear/frigate/discussions/20367)
- [Discussion #18274 — low-res detect lowers GPU decode load](https://github.com/blakeblackshear/frigate/discussions/18274)

### Ключевые практики

1. **Detect substream обязателен** даже при `detect.enabled: false` — motion, Birdseye, API snapshots требуют decode.
2. **Совпадение aspect ratio** detect и record — рекомендация Frigate для seamless UI (например 640×360 + 1920×1080, не 640×480 + 16:9 main).
3. **Detector crop, не full frame** — в detect canvas вырезается ROI ~320×320 для модели; полный кадр не подаётся в ONNX/TFLite/OpenVINO detector.
4. **Tracker на detect**, clip на record — но **timeline и bbox** согласованы в одном playback frame of reference (main).
5. **Record-only mode** — всё равно нужен low-res detect role для экономии CPU/GPU decode.

### Сравнение с BirdLense

| Аспект | Frigate | BirdLense (текущий / план) | Вердикт |
|--------|---------|---------------------------|---------|
| Dual-stream | Роли `detect` + `record` | go2rtc detect/main RTSP | **KEEP** — parity, не удалять |
| Bbox space | Main/record timeline | Частично lores для overlay (incident) | **ADOPT** — один playback space (#636) |
| Motion→record | Motion на detect → record segments | Detect-first gate блокировал record | **ADOPT** — P1 motion→hires (#635) |
| External NVR | Frigate **is** the NVR | Frigate MQTT как hint | **Правильно** — hint only, не driver |
| Detector fps | 5 fps detect | ~7 fps processed | OK для feeder; не гнаться за 10+ без need |
| OpenVINO | Default CPU detector init | OpenVINO binary + iGPU deploy | **ADOPT** latency mode, native lores |

**Over-built у нас (vs Frigate):**
- Salvage/fusion persist paths — Frigate не имеет «восстановить persist из внешнего label».
- Detect-first как recording gate — Frigate record не ждёт object confirmation.
- Multicam implicit lock — Frigate камеры независимы.
- Config kostyli (`linear_skip_*`, salvage toggles) — Frigate: config = roles + thresholds, не gate semantics.

**Не копировать слепо:**
- Frigate object detector = generic COCO; у нас custom binary + species classifier — двухстадийность оправдана.
- Frigate не делает DINOv2/behavior — наш стек глубже, но только после bbox SLO (#642).

---

## 2. BirdNET-Go — audio hint pipeline

### Архитектура

```
Audio capture (48kHz) → AudioRouter → per-model AnalysisBuffer
  → analysisBufferMonitor (poll ~100ms) → TFLite/ONNX inference
  → ResultsQueue → processDetections → PendingDetections (cross-model merge)
  → Flush (1s) → Deep Detection filter → JobQueue (async actions)
```

Источники:
- [ARCHITECTURE.md](https://github.com/tphakala/birdnet-go/blob/main/ARCHITECTURE.md)
- [Detection pipeline wiki](https://github.com/tphakala/birdnet-go/wiki/detection-pipeline.md)
- [BirdNET-Go Guide — filter precedence](https://github.com/tphakala/birdnet-go/wiki/BirdNET%E2%80%90Go-Guide)
- [PR #2625 — multi-model buffer architecture](https://github.com/tphakala/birdnet-go/pull/2625)

### Ключевые практики

1. **Фильтры по precedence:** Range → Confidence → Deep Detection (repeat within window) → Privacy/Dog bark.
2. **Deep Detection** — требует N совпадений species в окне (~15s) перед accept; снижает false positives **без** bypass geometry.
3. **Cross-model merge** по `sourceID:commonName` — BirdNET + Perch consensus усиливает confidence.
4. **Job queue async** — DB/MQTT/SSE не блокируют inference loop.
5. **Geomodel v3** — location prior как **filter**, не как «создать detection без audio».

### Сравнение с BirdLense

| Аспект | BirdNET-Go | BirdLense | Вердикт |
|--------|------------|-----------|---------|
| Audio→persist | Audio **is** primary for audio-only product | BirdNET = hint к visual track | **Правильно** для video-first Hub |
| FIFO persist gate | N/A (audio-native) | `birdnet_fifo_persist` gate | **REMOVE** — demote to hint (#638) |
| Repeat confirmation | Deep Detection window | Нет аналога в classifier | **ADOPT optional** — `hint_repeat_window_sec` в hints module |
| Regional filter | Geomodel + range | `ebird_regional_confidence` | **KEEP** — уже hint-shaped |
| Async actions | JobQueue | Finalize worker W1 | **ADOPT** — не блокировать detect loop |

---

## 3. Yet Another WhosAtMyFeeder (YA-WAMF) — Frigate-adjacent classifier

### Архитектура

```
Frigate MQTT (bird detected) → snapshot/clip frame → TFLite/ONNX classifier
  → optional BirdNET-Go audio correlation → store + notify
  → optional multi-frame clip analysis (15+ frames)
```

Источники:
- [YA-WAMF README](https://github.com/Jellman86/YetAnother-WhosAtMyFeeder/blob/main/README.md)
- [Performance docs](https://github.com/Jellman86/YetAnother-WhosAtMyFeeder/tree/main/docs)

### Ключевые практики

1. **Frigate как event source**, не как bbox owner — YA-WAMF берёт snapshot/clip от Frigate, классифицирует локально.
2. **Trusted Frigate sublabels** — можно принять Frigate label как hint, но классификатор — primary для species.
3. **Multi-frame clip analysis** — опционально 15+ кадров для ambiguous cases (аналог нашего best-keyframe + regen).
4. **Backend:** ONNX Runtime / TFLite на CPU; MobileNet fastest, EVA-02 для accuracy.

### Сравнение с BirdLense

| Аспект | YA-WAMF | BirdLense | Вердикт |
|--------|---------|-----------|---------|
| Detection owner | Frigate | YOLO+ByteTrack | **Правильно** — мы не Frigate plugin |
| Classifier | Standalone service | In-processor finalize | **KEEP** — меньше moving parts |
| Frigate label | Trusted sublabel option | `frigate_bbox` + salvage | **DEMOTE** — hint weight only (#641) |
| Multi-frame | Optional deep analysis | `track_regen`, best keyframe | **KEEP** — после geometry green |
| Hardware | CPU TFLite/ONNX | OpenVINO iGPU | Разный target; наш путь — Intel |

**Over-built у нас vs YA-WAMF:**
- Полный fusion/salvage stack — YA-WAMF: classify → store, без «weak salvage persist».
- Live overlay merge Frigate+YOLO polygons — YA-WAMF не смешивает bbox sources в real-time.

---

## 4. Другие bird feeder проекты (кратко)

| Project | Stack | Motion→record | Detection | Classify | Заметка |
|---------|-------|---------------|-----------|----------|---------|
| [Original BirdLense](https://github.com/AleksandrRogachev94/BirdLense) | Pi, YOLO+ByteTrack, BirdNET | PIR/motion | Binary YOLO | Species CNN | Близкий продуктовый spine; Hub расширение |
| [FeatherFeed](https://github.com/pfortune/featherfeed) | Pi+Coral TPU | Ultrasonic trigger | Coral TFLite | TFLite | **Не adopt** — Coral out of scope |
| [BirdFeederCam](https://github.com/nukeem/BirdFeederCam) | Pi, Roboflow API | OpenCV motion | Cloud API | Cloud | **Не adopt** — cloud dependency |

---

## 5. Intel OpenVINO + iGPU — constraints & best practices

### Platform (BirdLense deploy)

- Target: **Intel CPU + iGPU** (iHD), Docker `/dev/dri/renderD*`, `LIBVA_DRIVER_NAME=iHD`.
- **Исключено:** Google Coral, NVIDIA CUDA.
- WSL2: GPU passthrough требует свежий host driver (≥30.0.100.9955) + OpenCL в Linux guest.

Источники:
- [OpenVINO Intel GPU configuration](https://docs.openvino.ai/nightly/get-started/install-openvino/configurations/configurations-intel-gpu.html)
- [Ultralytics OpenVINO integration](https://docs.ultralytics.com/integrations/openvino/)
- [Ultralytics — latency vs throughput modes](https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/optimizing-openvino-latency-vs-throughput-modes.md)
- [OpenVINO YOLOv9 letterbox preprocessing](https://docs.openvino.ai/2024/notebooks/yolov9-optimization-with-output.html)
- [OpenVINO model_api resize_type letterbox](https://github.com/openvinotoolkit/model_api/blob/master/docs/source/guides/model-configuration.md)
- [Ultralytics #9164 — rectangular OpenVINO export](https://github.com/ultralytics/ultralytics/issues/9164)

### Рекомендации для feeder pipeline (1–2 cameras, real-time)

| Topic | Recommendation | Rationale |
|-------|----------------|-----------|
| Device | `intel:gpu` binary detect; `intel:cpu` fallback logged | iGPU ~10× headroom vs single-stream need; latency mode для live |
| Performance hint | `LATENCY` для live detect; `THROUGHPUT` только для batch regen | [Ultralytics guide](https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/optimizing-openvino-latency-vs-throughput-modes.md) |
| Input shape | **Native lores aspect** (704×576), letterbox в detector — не square force | Incident a656199a; commit `2ff464057` |
| Export | OpenVINO IR с фиксированным `[1,3,H,W]` под lores; FP16 на GPU | Rectangular export — кастом dataset при INT8 |
| Preprocessing | Letterbox pad 114; inverse scale bbox → lores → remap main | OpenVINO YOLO notebooks |
| Async | Single inference request per live stream (LATENCY) | Multi-stream throughput — только regen worker |
| INT8/NNCF | Phase 5 (#644) optional; validate IoU gate first | Quantization риск на мелких birds |
| Driver | `renderD128` + group_add в compose override | Deploy rule `deploy.mdc` |

### Anti-patterns (наблюдали в prod)

1. **Square `inference_lores_px`** на 4:3 substream → birds shrink → blind detector.
2. **Silent torch fallback** без metric — маскирует OpenVINO misconfig.
3. **Coral path в perf audit** — irrelevant для Intel-only; переименовать scope #644.

---

## 6. Synthesis — adopt vs over-built

### Adopt (from research)

1. Frigate **dual-stream roles** + **single playback bbox space** — benchmark, не driver.
2. Motion→record **без** detect confirmation gate.
3. BirdNET-Go **filter precedence** и optional repeat-confirmation для hints.
4. YA-WAMF **thin MQTT adapters** + optional multi-frame classify.
5. OpenVINO **LATENCY + native aspect letterbox** на iGPU.
6. Independent per-camera sessions (Frigate model).

### Over-built (trim in this EPIC)

1. Salvage persist (`restore_detect_first_persist_rows`, weak/frigate salvage).
2. Detect-first / Frigate / BirdNET **recording or persist gates**.
3. Multicam implicit single-cam lock.
4. Fusion config surface (`linear_skip_*`, salvage toggles in UI).
5. Coral backend references in perf track — Intel-only audit.
6. Live overlay **Frigate bbox merge** as detection input — demote to diagnostic overlay only.

### Keep (differentiated value)

1. Two-stage binary + species classifier (vs Frigate generic detector).
2. ByteTrack + spatial split for multi-bird feeder zones.
3. DINOv2 + behavior layers (gated, #642).
4. Dual-stream with go2rtc (Frigate-parity geometry).
5. MCP + local-first Hub (vs YA-WAMF sidecar).

---

## 7. Links index

| Resource | URL |
|----------|-----|
| Frigate cameras.md | https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/configuration/cameras.md |
| Frigate camera_setup.md | https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/frigate/camera_setup.md |
| BirdNET-Go ARCHITECTURE | https://github.com/tphakala/birdnet-go/blob/main/ARCHITECTURE.md |
| BirdNET-Go detection pipeline | https://github.com/tphakala/birdnet-go/wiki/detection-pipeline.md |
| YA-WAMF | https://github.com/Jellman86/YetAnother-WhosAtMyFeeder |
| OpenVINO Intel GPU config | https://docs.openvino.ai/nightly/get-started/install-openvino/configurations/configurations-intel-gpu.html |
| Ultralytics OpenVINO | https://docs.ultralytics.com/integrations/openvino/ |
| Ultralytics latency/throughput | https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/optimizing-openvino-latency-vs-throughput-modes.md |
| Hub dual-stream plan | [`DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md`](DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md) |
| Hub perf baseline | [`../reports/perf/runtime_pipeline_profile_latest.md`](../reports/perf/runtime_pipeline_profile_latest.md) |
