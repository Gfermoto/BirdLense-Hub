# Domain Export Runbook

## Scope
- Dataset export packaging for `detector`, `classifier`, `behavior`.
- ReID artifacts are `private_backup_only` and never exported to community.

## Steps
1. Verify contracts: `docs/reports/datasets/dataset_contract_registry_latest.json`.
2. Verify stream quality matrix: `docs/reports/stream_quality/stream_quality_latest.json`.
3. Export train-ready dataset from Hub (`ready_for_train=1`, `strict_quality=1`).
4. Archive `dataset_info.json`, `classes.txt`, and export fingerprint in release evidence.
5. For ReID, create backup artifact only and mark `reid_private_backup=true`.

## Rollback trigger
- Any contract drift or stream-quality gate failure => block export and keep previous artifact version.
