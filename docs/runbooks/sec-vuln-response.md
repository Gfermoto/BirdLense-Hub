# Secrets & Vulnerability Response

## Goal

`SOTA-8-02`: enforce end-to-end controls for secrets exposure prevention and vulnerability response SLA.

## Contract

Gate verifies:

- `.gitleaks.toml` exists (secrets scan config)
- CI includes `Bandit` and `pip-audit`
- repository has `security-gitleaks` target
- vulnerability response runbook exists
- open `P0/P1` vulnerabilities have both `owner` and `eta`

## Commands

```bash
make secrets-vuln-response-gate
```

Manual:

```bash
python3 scripts/verify_sec_vuln_response.py \
  --vuln-register docs/reports/security/vulnerability_register.json
```

## Deploy integration

`scripts/public/deploy.sh` runs this gate at step `0.50`.

- fail blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_SECRETS_VULN_GATE=1`

## Artifacts

- `docs/reports/security/vulnerability_register.json`
- `docs/reports/security/sec_vuln_response_latest.json`
- `docs/reports/security/sec_vuln_response_latest.md`

## Rollback / mitigation

1. Keep current release unchanged.
2. If gate fails, inspect `sec_vuln_response_latest.json`.
3. For each open `P0/P1` entry, fill `owner` and `eta` in vulnerability register.
4. Re-run `make secrets-vuln-response-gate` and then `make verify`.
