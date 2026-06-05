# Golden Set Mandatory Gate

- generated_at: `2026-06-05T16:00:58Z`
- base_ref: `HEAD~1`
- head_ref: `HEAD`
- gate_required: `True`
- ok: `True`

## Trigger files

- `app/processor/src/detection_fusion.py`

## Runs

- `make validate-pipeline-golden` -> ok=`True` (exit=0, 1.667s)
- `python3 scripts/stress_test_offline.py --no-yolo` -> ok=`True` (exit=0, 3.946s)
