# Champion Challenger Shadow Gate

## Goal

`SOTA-2-04`: enforce safe model promotion via champion/challenger shadow evidence.

## Contract

Gate verifies:

- all required candidate models have shadow-history entries
- required shadow coverage ratio is met
- every history entry has `shadow_passed=true`
- no unsafe promotions are present
- documented evidence file exists for each candidate entry

## Commands

```bash
make champion-challenger-shadow-gate
```

Manual:

```bash
python3 scripts/verify_champion_challenger_shadow.py \
  --contract docs/reports/ml_shadow/champion_challenger_contract.json \
  --history docs/reports/ml_shadow/shadow_pipeline_history.jsonl
```

## Integrations

- CI docs job: `Champion challenger shadow gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.64`.

## Artifacts

- `docs/reports/ml_shadow/champion_challenger_contract.json`
- `docs/reports/ml_shadow/shadow_pipeline_history.jsonl`
- `docs/reports/ml_shadow/champion_challenger_latest.json`
- `docs/reports/ml_shadow/champion_challenger_latest.md`

## Rollback / mitigation

1. Add missing candidate entries to shadow history.
2. Ensure `unsafe_promotion=false` and `shadow_passed=true`.
3. Add missing evidence files.
4. Re-run `make champion-challenger-shadow-gate`.
