# Domain Rollback Runbook

## Scope
- Safe rollback after failed canary/shadow/promote checks.

## Steps
1. Restore previous champion model/config snapshot.
2. Restart stack and run `make verify`.
3. Re-run domain loop and stream-quality gates to confirm rollback safety.
4. Log rollback reason in issue evidence and review board notes.

## Mandatory checks
- `docs/reports/ml_shadow/champion_challenger_latest.json` has no unsafe promotions.
- `docs/reports/domain_finetune/domain_finetune_loop_latest.json` remains `ok=true`.
