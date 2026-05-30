# SSDF Control Map Gate

## Goal

`SOTA-8-01`: maintain explicit SSDF mapping and fail release when mandatory controls drift.

## Contract

Gate validates:

- all required SSDF practices are present (`PO.1`, `PO.3`, `PS.1`, `PS.2`, `PW.4`, `PW.8`, `RV.1`, `RV.3`)
- each control has owner and evidence
- no open `P0/P1` controls with non-implemented status

## Commands

```bash
make ssdf-control-map
```

Manual:

```bash
python3 scripts/verify_ssdf_control_map.py \
  --map-file docs/reports/ssdf/ssdf_control_map.json
```

## Deploy integration

`scripts/public/deploy.sh` runs gate at step `0.49`.

- fail blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_SSDF_MAP_GATE=1`

## Artifacts

- `docs/reports/ssdf/ssdf_control_map.json` (source map)
- `docs/reports/ssdf/ssdf_control_map_latest.json`
- `docs/reports/ssdf/ssdf_control_map_latest.md`

## Rollback / mitigation

1. Keep current release unchanged.
2. Check missing/malformed entries in `ssdf_control_map_latest.json`.
3. Update source map (`ssdf_control_map.json`) with owner/evidence/status.
4. Re-run `make ssdf-control-map` and `make verify`.
