# Review Board Governance Gate

## Goal

`SOTA-9-01`: enforce monthly review-board cadence for reliability/security/ML risks.

## Contract

Gate verifies:

- review sessions cover required domains (`reliability`, `security`, `ml`)
- total board sessions meet minimum baseline
- cadence adherence ratio meets policy threshold
- no untriaged `P0/P1` finding exists without owner+decision

## Commands

```bash
make review-board-governance-gate
```

Manual:

```bash
python3 scripts/verify_review_board_governance.py \
  --contract docs/reports/governance/review_board_contract.json \
  --sessions docs/reports/governance/review_board_sessions.jsonl
```

## Integrations

- CI docs job: `Review board governance gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.66`.

## Artifacts

- `docs/reports/governance/review_board_contract.json`
- `docs/reports/governance/review_board_sessions.jsonl`
- `docs/reports/governance/review_board_latest.json`
- `docs/reports/governance/review_board_latest.md`

## Rollback / mitigation

1. Add missing sessions for uncovered domains.
2. Ensure all `P0/P1` findings have owner and explicit decision.
3. Re-run `make review-board-governance-gate`.
4. Re-run CI/deploy gates before release.
