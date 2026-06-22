# OWASP API Controls

- generated_at: `2026-06-22T17:30:36Z`
- coverage: `8/10`
- coverage_pct: `80.0`
- ok: `False`

## Inputs

- strict_api_auth_ok: `True`
- secrets_ok: `True`
- protected_unauth_status: `403`
- protected_auth_status: `403`

## Control Map

- `API1` covered=False — auth guards + protected route smoke
- `API2` covered=True — BIRDLENSE_STRICT_API_AUTH gate
- `API3` covered=True — require_ui_settings_password on system endpoints
- `API4` covered=True — password + visitor rate limit and runtime SLI gates
- `API5` covered=False — admin/contributor guards on privileged API
- `API6` covered=True — sensitive system routes require password/token
- `API7` covered=True — controlled integration config and strict env validation
- `API8` covered=True — verify-prod-env + readiness security_gates
- `API9` covered=True — OpenAPI contract + route tests in CI
- `API10` covered=True — dependency scans + CI security checks
