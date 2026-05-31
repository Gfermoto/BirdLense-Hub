# Event Burst & Reconnect Gate

## Goal

`SOTA-6-02`: enforce burst/reconnect resilience contract for integrations.

## Contract

Gate verifies:

- all required stress scenarios exist in history
- minimum history depth is met
- weighted pass-rate meets threshold
- weighted event-loss rate stays within SLA
- reconnect recovery p95 stays within threshold

## Commands

```bash
make event-burst-reconnect-gate
```

Manual:

```bash
python3 scripts/verify_event_burst_reconnect.py \
  --contract docs/reports/integrations/event_burst_reconnect_contract.json \
  --history docs/reports/integrations/event_burst_reconnect_history.jsonl
```

## Integrations

- CI docs job: `Event burst reconnect gate`.
- Deploy preflight: `scripts/public/deploy.sh` step `0.62`.

## Artifacts

- `docs/reports/integrations/event_burst_reconnect_contract.json`
- `docs/reports/integrations/event_burst_reconnect_history.jsonl`
- `docs/reports/integrations/event_burst_reconnect_latest.json`
- `docs/reports/integrations/event_burst_reconnect_latest.md`

## Rollback / mitigation

1. Add missing scenario rows to `event_burst_reconnect_history.jsonl`.
2. Reduce event loss and reconnect p95 in runtime settings.
3. Re-run `make event-burst-reconnect-gate`.
4. Re-run CI/deploy gates before release.
