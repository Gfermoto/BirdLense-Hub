# SLSA Build Track Gate

## Goal

`SOTA-5-03`: ensure build pipeline integrity progression against SLSA track plan.

## Contract

Gate verifies:

- CI workflow exists and remains the canonical build-track source
- required SLSA controls from plan are present in workflow:
  - `workflow_dispatch`
  - `concurrency` with `cancel-in-progress`
  - `bandit` security scan
  - `pip-audit` dependency scan
  - no `self-hosted` runner usage in CI workflow
- control adoption percentage meets plan threshold

## Commands

```bash
make slsa-build-track-gate
```

Manual:

```bash
python3 scripts/verify_slsa_build_track.py \
  --plan docs/reports/slsa/slsa_build_track.json
```

## Integrations

- CI docs job: `SLSA build-track gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.60`.

## Artifacts

- `docs/reports/slsa/slsa_build_track.json`
- `docs/reports/slsa/slsa_build_track_latest.json`
- `docs/reports/slsa/slsa_build_track_latest.md`

## Rollback / mitigation

1. Restore missing required control in workflow.
2. Re-run `make slsa-build-track-gate`.
3. Re-run CI docs/security jobs before release.
