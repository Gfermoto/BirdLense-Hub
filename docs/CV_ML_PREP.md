# CV / ML prep contract

[Русский](./CV_ML_PREP.ru.md)

This page freezes the prep contract for
[issue #377](https://github.com/Gfermoto/BirdLense-Hub/issues/377) before
starting the larger CV / ML roadmap epic ([#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)).

The scope is intentionally narrow: document the detector/classifier boundary,
future inference backend boundary, training-data reproducibility rules, and the
process for unblocking the epic. It does not implement OpenVINO/ONNX Runtime,
new training jobs, or a processor refactor.

**Execution order** for implementation after prep: [CV_ML_ROADMAP_PHASES.md](CV_ML_ROADMAP_PHASES.md).

---

## 1. Detector class contract

Runtime currently uses the two-stage pipeline:

```text
YOLO detector -> scoped target boxes -> species classifier -> fusion
```

The first-stage detector labels are normalized by
`TwoStageStrategy._normalize_detector_label`:

| Raw detector label family | Canonical runtime label |
|---------------------------|-------------------------|
| `bird`, `avian`, case/underscore/hyphen variants | `Bird` |
| `squirrel`, `chipmunk`, `rodent`, `грызун`, case/underscore/hyphen variants | `Rodent` |
| `background`, exact planned third class for hard negatives | `Background` |
| any other class name | title-cased normalized label, still outside the default scope |

The default first-stage runtime scope is:

```yaml
processor:
  detector_scope: ["Bird", "Rodent"]
```

Only valid boxes whose normalized label is in `processor.detector_scope` enter
the second-stage species classifier. A detector class such as `background`,
`negative`, `empty`, or any other hard-negative class must remain outside
`detector_scope`; those boxes are discarded before crop classification and must
not create species candidates.

For the planned three-class detector, the YOLO `dataset.yaml` / `model.names`
canonical class names are:

```yaml
names:
  0: Bird
  1: Rodent
  2: Background
```

`Background` is the canonical third class for detector hard negatives. Other
raw hard-negative names such as `negative` or `empty` still normalize outside
the default scope, but they do not satisfy the canonical three-class rollout
contract unless the rollout notes explicitly document the deviation.

For new detector weights, the validation contract is:

1. At least one class must normalize to `Bird`.
2. At least one class must normalize to `Rodent` if rodent detection is expected
   for that rollout.
3. Any background / hard-negative class must normalize to a label outside the
   configured `processor.detector_scope`.
4. The class-name mapping must be recorded in the weight rollout notes together
   with the exact `processor.detector_scope` used in production.

Fail-fast validation for loaded detector weights belongs to the first
implementation issue of the epic: on model load, compare `model.names` after
normalization with the expected three-class contract and configured scope, fail
with an actionable error if a target class is missing, and fail if
`Background` or another hard-negative class is accidentally included in scope.

---

## 2. Inference backend boundary

Current entry point:

- `app/processor/src/detection_stack.py` resolves config and creates
  `TwoStageStrategy`.
- `TwoStageStrategy` in `app/processor/src/detection_strategy.py` calls
  Ultralytics YOLO directly for detector tracking and classifier inference.
- `FrameProcessor` consumes `DetectionStrategy.detect(...)` results and should
  not know whether inference is Torch, OpenVINO, or ONNX Runtime.

Future backend abstraction should be inserted below `detection_stack.py` and
inside the strategy layer, not across `FrameProcessor`. The stable boundary is:

```text
detection_stack factory
  -> strategy constructor
    -> detector backend: frame -> tracked boxes with class name, confidence, bbox
    -> classifier backend: crop -> top label / confidence or probability vector
```

Draft config names reserved for the epic:

| Key / env overlay | Purpose | Initial value |
|-------------------|---------|---------------|
| `processor.inference_backend` / `BIRDLENSE_INFERENCE_BACKEND` | backend selector | `torch` (also `openvino` for binary IR) |
| `processor.inference_device` / `BIRDLENSE_INFERENCE_DEVICE` | device hint (`cpu`, `cuda`, `auto`, `openvino:CPU`) | `auto` |
| `processor.inference_precision` / `BIRDLENSE_INFERENCE_PRECISION` | precision hint (`fp32`, `fp16`, `int8`, `auto`) | `auto` |
| `processor.models.binary` | Torch `.pt` binary detector path | existing path |
| `processor.models.binary_openvino` | OpenVINO export dir or `.xml` when backend is `openvino` | empty until configured |
| `processor.models.classifier` | current classifier path; stays authoritative for Torch `.pt` | existing path |

Do not rename the existing `processor.models.binary` and
`processor.models.classifier` keys during the OpenVINO work. If converted model
artifacts are added, prefer backend-specific optional keys under
`processor.models.*` while keeping the current keys as the Torch default.

---

## 3. Data and reproducibility

The train-ready export path in `docs/DATASETS.md` is the canonical baseline for
Phase 1:

- use `ready_for_train=1` for automatic `train/val` split;
- use `strict_quality=1` for rollout candidates;
- keep `split_seed` fixed for repeatability;
- keep `dataset_info.json` and `classes.txt` with the trained weights;
- reject rollout evidence with duplicate `(video_id, track_id)` rows or
  cross-split `video_id` leakage.

Minimum class size is controlled by `min_images_per_class`. For formal rollout
candidates, classes below that minimum are excluded and, with `strict_quality=1`,
the export fails instead of silently producing weak classes.

Hard negatives for the detector should be tracked in a manifest rather than
mixed into species-class folders. The manifest should follow the
`dataset_info.json` pattern: schema/version, source path, class label, split,
source video or collection id when available, and a fingerprint/hash for audit.
Background / hard-negative detector labels are detector-only evidence and must
not appear in classifier `classes.txt`.

---

## 4. Legacy config hygiene

Production runtime supports only `two_stage`. If `user_config.yaml` still
contains `processor.detection_strategy: single_stage` or old single-stage model
paths, `detection_stack.py` logs that the value is ignored and builds the
two-stage stack.

Recommended cleanup before starting the epic:

1. Remove `processor.detection_strategy: single_stage` from local
   `user_config.yaml`.
2. Do not tune `processor.models.single_stage`; it is a compatibility artifact,
   not a production runtime input.
3. Keep `processor.detector_scope` explicit when testing new detector weights so
   rollout notes can reproduce the exact first-stage scope.

---

## 5. Unblocking process for the epic

After the acceptance checklist in issue #377 is complete and merged:

1. Close issue #377.
2. Remove the `epic:blocked` label from epic #367.
3. Move epic #367 on the Roadmap board from Backlog to Ready, or to In progress
   if implementation starts immediately.
4. Add a short comment on #367: `Prep completed in #377`.

The epic should stay blocked until this page, `docs/DATASETS.md`, and
`docs/CONFIGURATION.md` agree on the detector/classifier contract and legacy
configuration guidance.
