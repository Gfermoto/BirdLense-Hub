# Pipeline simplification — external research (2026-06-10)

**Связано:** [`pipeline_simplification_plan.md`](pipeline_simplification_plan.md), EPIC [#633](https://github.com/Gfermoto/BirdLense-Hub/issues/633), [`intel_igpu_inference_guide.md`](intel_igpu_inference_guide.md)

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
- Frigate object detector = generic COCO; у нас custom binary + species classifier — двухстадийность оправданa.
- Frigate не делает DINOv2/behavior — наш stек глубже, но только после bbox SLO (#642).

### 1.1 Frigate OpenVINO detector — Intel iGPU benchmark (без Coral/CUDA)

Frigate на Intel использует **OpenVINO IR/ONNX** в default image; Coral/TensorRT/Hailo — **out of scope** для BirdLense deploy.

| Параметр | Frigate (OpenVINO) | BirdLense Hub | Вердикт |
|----------|-------------------|---------------|---------|
| Detector type | `type: openvino`, `device: GPU` / `NPU` / `CPU` | `inference_backend: openvino`, `inference_device: intel:gpu` | **ADOPT** naming parity |
| Default model | SSDLite MobileNet v2 FP16 IR (`/openvino-model/`) | Custom binary YOLO IR (`best_openvino_model/`) | **KEEP** domain model |
| YOLO on iGPU | YOLOv9 recommended; `model_type: yolo-generic`, square 320 typical | Rectangular native lores 704×576 (`2ff464057`) | **DIFFER** — feeder needs aspect, not Frigate square |
| Input tensor | `nchw`, `input_dtype: float`, letterbox in postprocess | Letterbox pad 114 + inverse remap | **ADOPT** contract (#636) |
| Multi-detector | `ov_0`, `ov_1` on same GPU when camera count high | Single binary track; classifier async worker | OK for 1–2 feeder cams |
| NPU + GPU split | Core Ultra: NPU for detect, GPU for enrichments | Classifier on GPU, binary on GPU (or CPU fallback) | **WATCH** — split only if VRAM-bound (#644) |
| Enrichments on GPU | Face/semantic search OpenVINO GPU (0.17+) | DINOv2/behavior gated (#642) | Same ordering principle |

**Frigate OpenVINO supported models (GPU/NPU):** YOLOv9 ✅, RF-DETR ✅ (XE iGPU+), YOLO-NAS ✅, MobileNet v2 ✅, YOLOX ✅; D-FINE/DEIMv2 — **CPU only** (GPU compile fails).

Источники:
- [Frigate object detectors — OpenVINO](https://docs.frigate.video/configuration/object_detectors/)
- [Frigate GPU troubleshooting](https://docs.frigate.video/troubleshooting/gpu)

**Docker / iGPU (Frigate = BirdLense):**
- Map **entire** `/dev/dri` (not only `renderD128`) — mixed Intel+Nvidia hosts swap render nodes.
- `group-add=$(stat -c "%g" /dev/dri/render* | head -n 1)` or `group_add: render` in compose.
- WSL2: `/dev/dxg` + `/usr/lib/wsl` mount; host driver ≥ 30.0.100.9955.

**Frigate 0.17 + OpenVINO version pitfalls (Intel-only ops):**

| Symptom | OpenVINO | Fix |
|---------|----------|-----|
| `stoi` RuntimeError on `compile_model()` (Gen12 UHD 770) | 2025.3 and older | Upgrade to **2026.1.0+** |
| `clCreateSubBuffer … CL_INVALID_VALUE` on GPU enrichments | 2025.3 | **2025.4+** ([openvino#31180](https://github.com/openvinotoolkit/openvino/pull/31180)) |
| MVN compile / `work_group_reduce_add` on Jasper Lake | 2025.3 GPU | Prefer CPU detect or upgrade OV |
| TensorFlow SIGILL on non-AVX CPUs (N6005) | Frigate 0.17 TF paths | **AVX required** for 0.17; use OpenVINO-only detect |
| GPU not listed in `available_devices` | Driver/permissions | HDMI dummy plug (some boards); verify render group |

BirdLense не Frigate-container — но **те же OV/runtime баги** на том же iGPU. Wave 5 (#644): pin OV version + smoke `compile_model` on deploy host.

**Motion→record (Frigate contract we adopt):**
- `record` segments start on motion/trigger; object detection **не** блокирует запись.
- `detect` role decodes substream even when `detect.enabled: false` (motion/Birdseye need decode).
- Frigate MQTT `frigate/events` — **downstream hint**, не bbox owner для species (см. YA-WAMF).

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

### 2.1 BirdNET-Go inference on Intel (без Coral, без CUDA)

BirdNET-Go **не** использует OpenVINO напрямую. Intel-путь для audio sidecar:

| Backend | Status | Intel iGPU | Notes |
|---------|--------|------------|-------|
| **ONNX Runtime 1.25.x** | Primary (TFLite phased out) | CPU default; GPU via ORT CUDA/TensorRT EP **out of scope** | Docker image bundles ORT |
| TFLite + XNNPACK | Legacy default in older builds | CPU only | `usexnnpack: true`, ~500ms/3s clip on Pi 3B+ |
| ORT **OpenVINO EP** | Possible, **not** BirdNET-Go default | `device_type=GPU_FP16` on Intel iGPU | Experimental sidecar only; Hub MQTT hint unchanged |

**BirdNET-Go ONNX (2026):**
- Requires **ORT 1.25.x** (`ORT_API_VERSION 25`); 1.24 and 2.x fail to load.
- Models: BirdNET v2.4/v3.0, Perch v2, BattyBirdNET, Geomodel v3 — `.onnx` auto-selects ONNX backend.
- Build tag `onnx` gates ONNX code; release tarballs bundle `libonnxruntime.so`.

**Intel Hub integration (hint-only):**
```text
BirdNET-Go (ORT CPU on same NUC) → MQTT sightings → Hub classifier_hints collector
  → apply_hints_to_rows (weight birdnet_prior, max +0.15)
  → NEVER birdnet_fifo_persist without YOLO track
```

**Optional ORT OpenVINO EP** (research only, not prod default):
- ONNX Runtime OpenVINO Execution Provider: `device_type=GPU_FP16` for Intel iGPU.
- Requires separate ORT build with OpenVINO EP — BirdNET-Go Docker does **not** ship this.
- BirdLense audio hint latency (~3s clip) tolerates CPU ORT on Intel NUC; iGPU reserved for YOLO (#644).

**birdnet-onnx-converter** ([repo](https://github.com/tphakala/birdnet-onnx-converter)):
- FP32 for desktop CPU; FP16 for modern Intel iGPU **if** using ORT OpenVINO EP manually.
- Not required for Hub — MQTT hint path only.

Источники:
- [BirdNET-Go ONNX Runtime Installation](https://github.com/tphakala/birdnet-go/wiki/ONNX-Runtime-Installation) (May 2026: ORT sole backend roadmap)
- [PR #2619 — ONNX inference backend](https://github.com/tphakala/birdnet-go/pull/2619)
- [ONNX Runtime OpenVINO EP docs](https://onnxruntime.ai/docs/execution-providers/OpenVINO-ExecutionProvider.html)

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
| [birdwatch-ai](https://github.com/louistrue/birdwatch-ai) | Pi5 + **Hailo-8** NPU | RTSP | Hailo YOLOv8 | TFLite CPU | **Не adopt** — Hailo NPU out of scope |
| [bird-monitoring-pipeline](https://github.com/pdkyll/bird-monitoring-pipeline) | Research batch | FFmpeg split | YOLOv10 + BirdNET | TransFG | **Partial** — A/V correlation pattern only |

### 4.1 Explicit hardware exclusion (EPIC scope)

| Accelerator | Used by | BirdLense EPIC #633 / #644 |
|-------------|---------|---------------------------|
| Google Coral EdgeTPU | Frigate, FeatherFeed | **Excluded** |
| NVIDIA CUDA / TensorRT | Frigate `-tensorrt`, birdnet-onnx CUDA | **Excluded** |
| AMD ROCm | Frigate `-rocm` | **Excluded** |
| Hailo-8 / MemryX / DeGirum | Frigate community detectors | **Excluded** |
| **Intel CPU + iGPU (OpenVINO)** | Frigate default, BirdLense Hub | **In scope** |
| Intel NPU (Core Ultra) | Frigate detect on NPU | **Future watch** — not current deploy |

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

### 5.1 OpenVINO version matrix (Frigate field data → BirdLense #644)

| Version | Intel iGPU status | BirdLense action |
|---------|-------------------|------------------|
| ≤ 2025.3 | `stoi` compile fail (Gen12); `CL_INVALID_VALUE` GPU runtime | **Do not pin** |
| 2025.4+ | Fixes `clCreateSubBuffer` GPU sub-buffer bug | Minimum for GPU enrichments |
| 2026.1.0+ | Fixes Gen12 `stoi` on `compile_model` | Recommended pin in container smoke |

Post-deploy smoke (from [`intel_igpu_inference_guide.md`](intel_igpu_inference_guide.md)):

```bash
docker compose exec birdlense python3 -c "
import openvino as ov
c = ov.Core()
print('devices:', c.available_devices)
m = c.read_model('processor/models/detection/weights/best_openvino_model/best.xml')
c.compile_model(m, 'GPU')
print('GPU compile OK')
"
```

### 5.2 Frigate ↔ BirdLense preprocessing parity (#640)

| Step | Frigate YOLO-generic | BirdLense binary track |
|------|---------------------|------------------------|
| Detect canvas | Substream native aspect | `inference_lores_wh` native |
| Model input | Fixed W×H from export | Rectangular IR `[1,3,H,W]` |
| Letterbox | pad 114, inverse on bbox | Same via Ultralytics OpenVINO path |
| Playback bbox | Remap to **record** timeline | `_storage_bbox_norm_for_overlay` → main |
| CI gate | N/A | `compare_detector_bboxes.py` torch vs OV |

Frigate default SSDLite uses **300×300 nhwc BGR** — другой контракт; parity benchmark только для **YOLO letterbox + dual-stream geometry**, не для SSD weights.

### 5.3 Operator guide cross-reference

Детальный deploy/runbook: [`intel_igpu_inference_guide.md`](intel_igpu_inference_guide.md) — Docker DRI, `user_config` pins, LATENCY profile, Trapper 704×576.

### Anti-patterns (наблюдали в prod + Frigate discussions)

1. **Square `inference_lores_px`** на 4:3 substream → birds shrink → blind detector (a656199a).
2. **Silent torch fallback** без metric — маскирует OpenVINO misconfig.
3. **Coral/CUDA docs in perf track** — irrelevant; Intel-only audit (#644).
4. **OpenVINO 2025.3 pin** in community Frigate images — known GPU compile/runtime bugs.
5. **BirdNET FIFO persist gate** — anti-pattern vs BirdNET-Go (audio-native ≠ video-first Hub).
6. **Frigate sublabel as persist salvage** — YA-WAMF allows trusted sublabel; Hub demotes to hint weight.

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

## 7. Decision trace — research → plan mapping

| Research finding | Plan phase | Issue |
|------------------|------------|-------|
| Frigate motion→record без object gate | Wave 1 spine | #635 |
| Native aspect + single bbox space | Wave 1 geometry | #636 |
| Frigate OpenVINO GPU version pins | Wave 5 perf | #644 |
| BirdNET filter precedence | Wave 3 hints | #641 |
| YA-WAMF thin MQTT, no salvage persist | Wave 2 demotion | #638 |
| `compare_detector_bboxes` parity | Wave 1 CI | #640 |
| intel_igpu_inference_guide ops | Deploy / #644 | runbook |

---

## 8. Links index

| Resource | URL |
|----------|-----|
| Frigate object detectors (OpenVINO) | https://docs.frigate.video/configuration/object_detectors/ |
| Frigate cameras.md | https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/configuration/cameras.md |
| Frigate camera_setup.md | https://github.com/blakeblackshear/frigate/blob/dev/docs/docs/frigate/camera_setup.md |
| Frigate GPU troubleshooting | https://docs.frigate.video/troubleshooting/gpu |
| Frigate OpenVINO stoi fix (Gen12) | https://github.com/blakeblackshear/frigate/discussions/23016 |
| Frigate OpenVINO 2025.3 GPU bugs | https://github.com/blakeblackshear/frigate/discussions/22059 |
| BirdNET-Go ARCHITECTURE | https://github.com/tphakala/birdnet-go/blob/main/ARCHITECTURE.md |
| BirdNET-Go detection pipeline | https://github.com/tphakala/birdnet-go/wiki/detection-pipeline.md |
| BirdNET-Go ONNX install (ORT 1.25) | https://github.com/tphakala/birdnet-go/wiki/ONNX-Runtime-Installation |
| BirdNET ONNX converter | https://github.com/tphakala/birdnet-onnx-converter |
| ONNX Runtime OpenVINO EP | https://onnxruntime.ai/docs/execution-providers/OpenVINO-ExecutionProvider.html |
| YA-WAMF | https://github.com/Jellman86/YetAnother-WhosAtMyFeeder |
| OpenVINO Intel GPU config | https://docs.openvino.ai/nightly/get-started/install-openvino/configurations/configurations-intel-gpu.html |
| OpenVINO Model Server GPU Docker | https://docs.openvino.ai/nightly/model-server/ovms_docs_target_devices.html |
| Ultralytics OpenVINO | https://docs.ultralytics.com/integrations/openvino/ |
| Ultralytics latency/throughput | https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/optimizing-openvino-latency-vs-throughput-modes.md |
| Hub intel iGPU guide | [`intel_igpu_inference_guide.md`](intel_igpu_inference_guide.md) |
| Hub dual-stream plan | [`DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md`](DUAL_STREAM_BBOX_SYNC_PLAN_2026-06.md) |
| Hub perf baseline | [`../reports/perf/runtime_pipeline_profile_latest.md`](../reports/perf/runtime_pipeline_profile_latest.md) |
