# Golden Set Mandatory Gate

- generated_at: `2026-06-22T17:23:23Z`
- base_ref: `HEAD~1`
- head_ref: `HEAD`
- gate_required: `True`
- ok: `True`

## Trigger files

- `app/app_config/user_config.jetson-bootstrap.yaml`
- `app/app_config/user_config.jetson-operational.example.yaml`

## Runs

- `make validate-pipeline-golden` -> ok=`True` (exit=0, 1.008s)
- `python3 scripts/stress_test_offline.py --no-yolo` -> ok=`True` (exit=0, 3.714s)
