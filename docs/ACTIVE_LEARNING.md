# Active learning & hard-negative mining (#369)

[Русский](./ACTIVE_LEARNING.ru.md)

Phase 1 targets a **Hub-realistic** export path: candidate crops + JSONL manifest + reproducible `--seed`, without mandatory review UI.

## Layout (proposed)

Under `DATA_DIR` (e.g. `/app/data`):

- `active_learning_pool/` — image crops or symlinks
- `active_learning_pool/manifest.jsonl` — one JSON object per line

Schema: `scripts/active_learning/pool_entry_v1.schema.json`.

## Uncertainty signals

Use **existing** two-stage outputs: classifier **entropy** or **top1−top2 margin** from YOLO-cls `probs` (hook point: `TwoStageStrategy._classify_crop` in `detection_strategy.py`). Thresholds stay operator-tuned; document them here when frozen.

## Relation to detector dataset

Curated hard negatives feed the **3-class detector** pipeline (`merge_datasets_three_class.py`, epic [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)).

## Stub exporter

```bash
python3 scripts/active_learning/emit_pool_template.py --out /tmp/manifest.jsonl
```

writes one valid template line for tooling tests.
