# CV / ML roadmap — execution phases

[Русский](./CV_ML_ROADMAP_PHASES.ru.md)

This document fixes the **implementation order** for epic
[#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) and child issues, after gap analysis. It
supplements the prep contract in [CV_ML_PREP.md](CV_ML_PREP.md).

**GitHub Project board:** [BirdLense Hub — Roadmap](https://github.com/users/Gfermoto/projects/2/views/1) — track issue Status / «Поток» alongside this table.

---

## Task status (GitHub issues)

Legend: **Done** = shipped on branch `ML` in the repo (code/docs/scripts). **In progress** = active work now (operator training, measurements on your hardware, or deploy validation). **Planned** = next phase / not started.

| Issue | Status | Notes |
|-------|--------|--------|
| [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) Epic | **In progress** | Repo Phase‑1 delivered; **your** new weights + optional merge `ML`→`main` when validated on hub. |
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) Train & ship detector | **In progress** | Runtime contract + dataset merge helpers **done** in repo; **training detector weights** (Colab) — operator. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) Active learning | **Done** (Phase‑1 repo) / **In progress** (product) | Manifest schema + template + **`decision_trace_to_pool_manifest.py`** + SQLite **`export_pool_from_sqlite.py`** + docs **done**; UI/API **pool preview** shipped; scheduled retrain — later. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) Classifier roadmap | **In progress** / **Planned** | Fine-tune in Colab ([TRAINING](./TRAINING.md)) — operator; **entropy / margin + `classifier_needs_review` in decision_trace** — repo (config thresholds); **fusion training CSV + fusion-trace UI steps** ship those fields; Unknowns review queue + AL preview use those fields. Optional **DINO/DINOv2** backbone — [REID_ROADMAP](./REID_ROADMAP.md); [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383). |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) Multi-backend inference | **Done** / **Planned** | torch + OpenVINO + cache **done**; ONNX Runtime / TensorRT — **planned** (`NotImplementedError`). |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) Benchmarking | **Done** / **Planned** | Scripts + CI + docker smoke + optional **PSI drift gate** **done**; Grafana dashboard — **planned**. |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) Video decode | **In progress** | Benchmark script + FFmpeg VA-API option + `video.capture_backend` path **done**; UI/API **ML runtime status** shipped; **filling decode matrix** on your platforms — in progress. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) Re-ID | **In progress** / **Planned** | Design doc + DINO scope; [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383) — offline embed/cosine/export scripts + SQLite sidecar import **shipped**; UI/API **sidecar summary** shipped; gallery / similar-crop UI — planned. |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) Federated | **Done** (research) / **Planned** (prod) | Toy simulation + threat-model doc **done**; opt-in prod channel — **planned**. |

*Refresh this table when a milestone closes or scope shifts.*

---

## Order correction (vs a naive “decode first” stack)

GitHub priorities differ slightly from “hardware decode before everything”:

| Topic | Issue | Priority in tracker | Note |
|--------|--------|---------------------|------|
| Multi-backend inference (OpenVINO / ORT / torch) | [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) | **High** | Abstraction and optional backends before mandating zero-copy decode. |
| Hardware video decode (VA-API / NVDEC) | [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) | Low–**Medium** | **Does not block** OpenVINO inference per issue text; start with **measurement + docs**, then optional HW path. |
| Train/ship 3-class detector + class contract | [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) | **High** | Fail-fast `model.names` vs `detector_scope` when `processor.detector_weight_contract` is `enforce`. |
| Active learning / hard negatives | [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) | **High** | After stable inference export hooks. |
| Classifier roadmap | [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) | **High** | Parallel track to detector improvements. |
| Continuous benchmarking | [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) | Medium | Extended scripts + CI gates. |
| Re-ID, federated | [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374), [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) | Medium / Low | Non-blocking for core detector/classifier. |

---

## Phases (repository execution plan)

### Phase 1 — Foundation (done)

- Shared **`normalize_detector_label`** in `app/processor/src/detector_labels.py` (same semantics as legacy `TwoStageStrategy`).
- **`inference/`** package: **`resolve_inference_backend`**, **`torch_backend`** loaders, **`validate_detector_weight_contract`** (`off` / `warn` / `enforce`).
- Config: **`processor.inference_backend`** (default `torch`), **`processor.detector_weight_contract`** (default `warn`).
- Env override: **`BIRDLENSE_INFERENCE_BACKEND`**.
- **Do not** change `go2rtc_stream_source.py` / stream ingestion semantics in Phase 1.

### Phase 2 — Inference backends + benchmarks (core done; CI/docs shipped)

- **OpenVINO** for the binary detector: **`processor.models.binary_openvino`** or **`BIRDLENSE_BINARY_OPENVINO_PATH`**, optional **`inference_backend_cache.json`** after successful stack build ([#371]).
- Shared resolver **`inference/binary_paths.py`**: provenance fingerprint, ML lineage, processor weights status UI.
- ONNX Runtime / TensorRT: planned (`NotImplementedError` until implemented).
- **`scripts/benchmark-track-regen.py`** / **`compare_benchmark_reports.py`** / **`verify_benchmark_report_schema.py`**; эталон **`scripts/ci/reference_smoke_report.json`**; CI: unit-тесты + **`benchmark-regen-integration.yml`** (Docker smoke → verify → compare к эталону, [#372]).

### Phase 3 — Video pipeline optimization

- [#373] **`scripts/benchmark_video_decode_resize.py`** + measurement matrix template [CV_ML_DECODE.md](CV_ML_DECODE.md). Optional GStreamer/ffmpeg hwaccel **after** measured win on your platforms.

### Phase 4 — Product / research tracks

- [#369] Active learning: JSONL schema + `scripts/active_learning/emit_pool_template.py` + [ACTIVE_LEARNING.md](ACTIVE_LEARNING.md).
- [#370] Classifier uncertainty product wiring (entropy/margin → DB/UI) — hook documented at `_classify_crop`; rollout TBD.
- [#374] [REID_ROADMAP.md](REID_ROADMAP.md) — **DINO / DINOv2**: planned for **Re-ID embeddings** and optional **species** fine-tune / AL; **one backbone** on-hub can feed both heads when integrated · [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383).
- [#375] Runnable **`scripts/federated/simulate_fedavg.py`** + [FEDERATED_LEARNING.md](FEDERATED_LEARNING.md) (**not production**).

### Child issues — what landed in the repo (ML branch snapshot)

| Issue | Deliverable |
|-------|-------------|
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) | `detector_weight_contract` + tests including **3-class** weights (`Background` in model, not in scope). Train/calibrate/INT8 — still issue-owned. |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) | torch/OpenVINO + cache + optional **`BIRDLENSE_INFERENCE_AUTO_BENCHMARK`** → `cold_start_predict_ms`. ONNX/TensorRT remain `NotImplementedError`. |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) | Benchmark scripts + CI + reference JSON (drift/Grafana still future). |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) | Decode/resize script + docs table. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) | Pool manifest schema + template emitter + `decision_trace`/SQLite exporters + docs. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) | Design doc + offline [`embed_dinov2_crop.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_dinov2_crop.py) + [`embed_cosine_report.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_cosine_report.py) + [`export_crops_from_sqlite.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/export_crops_from_sqlite.py) + SQLite [`import_embeddings_sqlite.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/import_embeddings_sqlite.py); UI later. |
| [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383) | Sub-issue of [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374): [`embed_dinov2_crop.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_dinov2_crop.py) + [`embed_cosine_report.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/embed_cosine_report.py) + [`export_crops_from_sqlite.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/reid/export_crops_from_sqlite.py); hub gallery / prod — later. |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) | FedAvg toy simulation + threat-model doc. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) | `decision_trace` fields + fusion export CSV columns + fusion-trace UI steps; dedicated review-queue UI still roadmap. |
| [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379) | Weightless weak-label action events API: arrival / departure from tracks, possible feeding from feeder weight delta. |
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) dataset guard | `scripts/datasets/validate_yolo_labels.py` + `make dataset-validate-yolo-labels` for pre-Colab label sanity checks. |

### Epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) — 3-class detector **dataset** (Phase 1 entrypoint)

- Local layout: **`scripts/datasets/binary/birds`**, **`binary/rodent`**, **`binary/background`** — see [binary/README.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/datasets/binary/README.md).
- **`scripts/datasets/merge_datasets_three_class.py`** + **`make dataset-merge-three-class`** → `Bird` / `Rodent` / `Background` `dataset.yaml` under `scripts/datasets/binary/merged/` ([#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) trains/rolls up separately).
- Optional **`hard_negatives_manifest@v1`** schema + merge **`--manifest-out`**; see [DATASETS.md](DATASETS.md).

---

## Configuration keys (processor)

| Key | Meaning |
|-----|---------|
| `processor.inference_backend` | `torch` (default) \| `openvino` (binary detector IR). ONNX/TensorRT: [#371]. |
| `processor.models.binary_openvino` | Path to OpenVINO export dir or `.xml` when `inference_backend` is `openvino`. |
| `processor.detector_weight_contract` | `off` \| `warn` \| `enforce` — detector class names vs `processor.detector_scope` ([#368]). |
| `video.capture_backend` | `auto` (default) \| `opencv` \| `ffmpeg_vaapi` — live inference frame capture path; `auto` uses FFmpeg VA-API only with `video.encoding: intel` and working `/dev/dri`. |
| Env `BIRDLENSE_INFERENCE_BACKEND` | Overrides `processor.inference_backend`. |
| Env `BIRDLENSE_BINARY_OPENVINO_PATH` | Optional override for OpenVINO binary weights path. |
| Env `BIRDLENSE_INFERENCE_AUTO_BENCHMARK` | Optional one-shot binary `predict` timing → `inference_backend_cache.json` ([#371]). |

---

## Weightless operator APIs

These endpoints do not require new model weights and are meant for review, labeling,
and rollout diagnostics:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/ui/videos/{video_id}/action-events` | Weak behavior labels (#379): `arrival`, `departure`, and `possible_feeding` from existing tracks + feeder weight delta. |
| `GET /api/ui/system/active-learning/pool-preview` | Review/uncertainty candidates for active-learning pool export (#369). |
| `GET /api/ui/system/reid/summary` | Read-only status of offline `reid_embedding` sidecar table (#374). |
| `GET /api/ui/system/ml-runtime` | Operator snapshot of ML/video runtime config (#373/#372). |

---

## Parallel branch `ML` (recovery baseline on `dev`)

Inference and benchmarks land on **`ML`** first. **`dev`** stays the branch for restoring a known-good hub deploy. **Merge `ML` → `main` only after** the stack is proven working on your side (deployed or otherwise validated — green CI alone is not the gate). Until then, iterate on **`ML`**; PR [#382](https://github.com/Gfermoto/BirdLense-Hub/pull/382) tracks the eventual merge but does not imply a timeline.

---

## References

- Prep contract: [CV_ML_PREP.md](CV_ML_PREP.md)
- **Repository vs training responsibilities:** [ML_OPERATOR_HANDOFF.md](ML_OPERATOR_HANDOFF.md) · [RU](ML_OPERATOR_HANDOFF.ru.md)
- Detector Colab guide: [ML_DETECTOR_COLAB.md](ML_DETECTOR_COLAB.md) · [RU](ML_DETECTOR_COLAB.ru.md)
- Epic: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)
