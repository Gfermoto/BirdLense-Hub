# Domain Retrain Runbook

## Scope
- Execution path `collect -> curate -> train -> eval -> shadow -> promote`.

## Steps
1. Collect and curate dataset with strict-quality export enabled.
2. Run training/eval and produce candidate evidence.
3. Validate `champion_challenger_latest.json` and `domain_finetune_loop_latest.json`.
4. Confirm Stream E quality matrix is green before promote.
5. Promote only when `shadow_pass_rate_ok=true` and `safe_promotion_only_ok=true`.

## Evidence required
- Candidate evidence files in `docs/reports/ml_shadow/evidence/`.
- Latest domain loop report and stream quality report.
