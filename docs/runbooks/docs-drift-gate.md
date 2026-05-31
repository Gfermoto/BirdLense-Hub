# Docs Drift Gate

## Goal

`SOTA-4-02`: prevent divergence between documentation structure and real project docs routing.

## Contract

Gate verifies:

- MkDocs nav paths are present in `docs/_meta/docs_inventory.csv` (`status=keep`)
- redirect-stub inventory entries are present in MkDocs redirect map
- generated redirect snippet `docs/_meta/redirect_maps.yml` is in sync with `mkdocs.yml`
- all `status=keep` inventory files exist in repository

## Commands

```bash
make docs-drift-gate
```

Manual:

```bash
python3 scripts/verify_docs_drift_gate.py
```

## Integrations

- CI docs job: `Docs drift CI gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.59`.

## Artifacts

- `docs/reports/docs_drift/docs_drift_latest.json`
- `docs/reports/docs_drift/docs_drift_latest.md`

## Rollback / mitigation

1. Fix nav/inventory mismatch.
2. Update redirect maps or regenerate stubs if drift detected.
3. Restore missing `status=keep` docs files.
4. Re-run `make docs-drift-gate` and docs CI checks.
