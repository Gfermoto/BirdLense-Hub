# Domain Fine-tune Closure Package 30/60/90

## Decision Log
- Enforced contract-first rollout: `dataset_contract_registry@v1`, `domain_finetune_loop_report@v1`, `stream_quality_metrics@v1`.
- Promote policy locked to champion/challenger shadow pass + rollback-ready evidence.
- ReID constrained to private backup flow; community export only for detector/classifier/behavior.

## Roadmap 30/60/90
- **30 days**: stabilize detector precision/recall and reduce `fn_hour` drift.
- **60 days**: improve classifier `top1/top3/macro_f1` with domain-labelled refresh.
- **90 days**: converge behavior + ReID quality and tighten thresholds for production promote.

## Risk Register
- **R1: classifier quality lag** -> mitigation: prioritized curation and stricter acceptance splits.
- **R2: trigger-domain drift** -> mitigation: weekly stream-quality gate and parity hold checks.
- **R3: unsafe promote** -> mitigation: mandatory shadow gate + rollback runbook execution.

## Runbooks
- Export: `docs/runbooks/domain-export-runbook.md`
- Retrain: `docs/runbooks/domain-retrain-runbook.md`
- Rollback: `docs/runbooks/domain-rollback-runbook.md`

## Quality Uplift Evidence
- `champion_challenger_latest.json`: `shadow_pass_rate=1.0`, `unsafe_promotions=[]`.
- `domain_finetune_loop_latest.json`: all checks `true` (including rollback-ready evidence).
- `stream_quality_latest.json`: detector/behavior/reid metric gates pass, including `reid.link_accuracy=1.0`, `reid.id_switches=0`.
