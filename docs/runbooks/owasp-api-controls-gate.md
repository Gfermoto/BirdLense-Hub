# OWASP API Controls Gate

## Goal

`SOTA-1-02`: close API security baseline against OWASP API Top 10 with automated evidence.

## Contract

Gate verifies:

- readiness security gates are green (`strict_api_auth`, `flask_secret_key`, `processor_secret`)
- protected endpoint blocks unauthenticated access (`401/403`)
- protected endpoint allows authorized access (`200`)
- OWASP API1..API10 control map is fully covered (`100%`)

## Commands

```bash
make owasp-api-controls
```

Manual:

```bash
python3 scripts/verify_owasp_api_controls.py --base-url "${DEPLOY_URL}"
```

## Deploy integration

`scripts/public/deploy.sh` runs this gate at step `0.48`.

- fail blocks deploy
- temporary bypass only via `BIRDLENSE_SKIP_OWASP_API_GATE=1`

## Artifacts

- `docs/reports/owasp_api_controls/owasp_api_controls_latest.json`
- `docs/reports/owasp_api_controls/owasp_api_controls_latest.md`

## Rollback / mitigation

1. Keep current release active.
2. Inspect failed rows in `owasp_api_controls_latest.json`.
3. Re-check `strict_api_auth` and secrets via readiness (`/api/ui/readiness`).
4. Validate auth guards on protected endpoints.
5. Re-run `make verify` and `make owasp-api-controls`.
