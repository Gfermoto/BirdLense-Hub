# Golden Set Mandatory Gate

- generated_at: `2026-05-30T19:36:27Z`
- base_ref: `HEAD~1`
- head_ref: `HEAD`
- gate_required: `True`
- ok: `True`

## Trigger files

- `app/app_config/default_config.yaml`

## Runs

- `make validate-pipeline-golden` -> ok=`True` (exit=0, 1.185s)
- `python3 scripts/stress_test_offline.py --no-yolo` -> ok=`True` (exit=0, 3.147s)
