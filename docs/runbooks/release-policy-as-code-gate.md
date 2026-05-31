# Release Policy-as-Code Gate

## Goal

`SOTA-9-02`: enforce key release governance policies through code-driven gates.

## Contract

Gate verifies:

- required release policies are represented in audit stream
- minimum number of release audit events is met
- policy coverage ratio meets target
- every event has `gate_enforced=true`
- manual override ratio stays within configured limit
- every override has full audit trail (`reason`, `approved_by`, `ticket`)

## Commands

```bash
make release-policy-as-code-gate
```

Manual:

```bash
python3 scripts/verify_release_policy_as_code.py \
  --contract docs/reports/governance/release_policy_contract.json \
  --audit docs/reports/governance/release_policy_audit.jsonl
```

## Integrations

- CI docs job: `Release policy as code gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.67`.

## Artifacts

- `docs/reports/governance/release_policy_contract.json`
- `docs/reports/governance/release_policy_audit.jsonl`
- `docs/reports/governance/release_policy_latest.json`
- `docs/reports/governance/release_policy_latest.md`

## Rollback / mitigation

1. Add missing policy rows to release audit stream.
2. Ensure all gate events are enforced and override audit trail is complete.
3. Re-run `make release-policy-as-code-gate`.
4. Re-run CI/deploy gates before release.
