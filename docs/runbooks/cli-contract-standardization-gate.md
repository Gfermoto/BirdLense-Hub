# CLI Contract Standardization Gate

## Goal

`SOTA-7-02`: enforce predictable CLI contracts (`--help`, exit codes, structured output).

## Contract

Gate verifies:

- required critical CLI tools are present in registry
- `--help` exits with code `0` and contains usage banner
- invalid argument probe exits non-zero
- tool source contains structured JSON output pattern
- each CLI tool has assigned owner

## Commands

```bash
make cli-contract-standardization-gate
```

Manual:

```bash
python3 scripts/verify_cli_contract_standardization.py \
  --registry docs/reports/tooling/cli_contract_registry.json
```

## Integrations

- CI docs job: `CLI contract standardization gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.68`.

## Artifacts

- `docs/reports/tooling/cli_contract_registry.json`
- `docs/reports/tooling/cli_contract_latest.json`
- `docs/reports/tooling/cli_contract_latest.md`

## Rollback / mitigation

1. Fix failing CLI (`--help`, invalid arg exit, JSON output).
2. Update registry owner/paths for changed tools.
3. Re-run `make cli-contract-standardization-gate`.
4. Re-run CI/deploy gates before release.
