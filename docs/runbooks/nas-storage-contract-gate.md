# NAS Storage Contract Gate

## Goal

Issue `#350`: ensure NAS/SFTP recordings storage path remains operational and documented.

## Contract

Gate verifies:

- critical NAS components exist (processor mirror, UI card, API route, default config, docs)
- required operational modes are implemented:
  - local recording + background sync
  - offload after successful mirror
- user docs include required NAS/SFTP contract keywords
- UI API test file for mirror endpoint exists

## Commands

```bash
make nas-storage-contract-gate
```

Manual:

```bash
python3 scripts/verify_nas_storage_contract.py \
  --contract docs/reports/storage/nas_storage_contract.json
```

## Integrations

- CI docs job: `NAS storage contract gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.69`.

## Artifacts

- `docs/reports/storage/nas_storage_contract.json`
- `docs/reports/storage/nas_storage_contract_latest.json`
- `docs/reports/storage/nas_storage_contract_latest.md`

## Rollback / mitigation

1. Restore missing NAS component files.
2. Fix docs/config drift for `recordings_mirror` and `delete_local_after_success`.
3. Re-run `make nas-storage-contract-gate`.
4. Re-run CI/deploy gates before release.
