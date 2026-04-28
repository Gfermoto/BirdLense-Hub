# CV / ML roadmap — execution phases

[Русский](./CV_ML_ROADMAP_PHASES.ru.md)

This document fixes the **implementation order** for epic
[#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) and child issues, after gap analysis. It
supplements the prep contract in [CV_ML_PREP.md](CV_ML_PREP.md).

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
- [#374] [REID_ROADMAP.md](REID_ROADMAP.md).
- [#375] Runnable **`scripts/federated/simulate_fedavg.py`** + [FEDERATED_LEARNING.md](FEDERATED_LEARNING.md) (**not production**).

### Child issues — what landed in the repo (ML branch snapshot)

| Issue | Deliverable |
|-------|-------------|
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) | `detector_weight_contract` + tests including **3-class** weights (`Background` in model, not in scope). Train/calibrate/INT8 — still issue-owned. |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) | torch/OpenVINO + cache + optional **`BIRDLENSE_INFERENCE_AUTO_BENCHMARK`** → `cold_start_predict_ms`. ONNX/TensorRT remain `NotImplementedError`. |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) | Benchmark scripts + CI + reference JSON (drift/Grafana still future). |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) | Decode/resize script + docs table. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) | Pool manifest schema + template emitter + docs. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) | Design doc only (embeddings DB/UI later). |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) | FedAvg toy simulation + threat-model doc. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) | Documented hook points; full product uncertainty flags still roadmap. |

### Epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) — 3-class detector **dataset** (Phase 1 entrypoint)

- **`scripts/datasets/merge_datasets_three_class.py`** + **`make dataset-merge-three-class`** → `Bird` / `Rodent` / `Background` `dataset.yaml` ([#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) trains/rolls up separately).
- Optional **`hard_negatives_manifest@v1`** schema + merge **`--manifest-out`**; see [DATASETS.md](DATASETS.md).

---

## Configuration keys (processor)

| Key | Meaning |
|-----|---------|
| `processor.inference_backend` | `torch` (default) \| `openvino` (binary detector IR). ONNX/TensorRT: [#371]. |
| `processor.models.binary_openvino` | Path to OpenVINO export dir or `.xml` when `inference_backend` is `openvino`. |
| `processor.detector_weight_contract` | `off` \| `warn` \| `enforce` — detector class names vs `processor.detector_scope` ([#368]). |
| Env `BIRDLENSE_INFERENCE_BACKEND` | Overrides `processor.inference_backend`. |
| Env `BIRDLENSE_BINARY_OPENVINO_PATH` | Optional override for OpenVINO binary weights path. |
| Env `BIRDLENSE_INFERENCE_AUTO_BENCHMARK` | Optional one-shot binary `predict` timing → `inference_backend_cache.json` ([#371]). |

---

## Parallel branch `ML` (recovery baseline on `dev`)

Inference and benchmarks land on **`ML`** first. **`dev`** stays the branch for restoring a known-good hub deploy. **Merge `ML` → `main` only after** the stack is proven working on your side (deployed or otherwise validated — green CI alone is not the gate). Until then, iterate on **`ML`**; PR [#382](https://github.com/Gfermoto/BirdLense-Hub/pull/382) tracks the eventual merge but does not imply a timeline.

---

## References

- Prep contract: [CV_ML_PREP.md](CV_ML_PREP.md)
- Epic: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)
