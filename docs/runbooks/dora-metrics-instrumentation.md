# DORA Metrics Instrumentation

## Goal

`SOTA-5-01`: automatically generate DORA snapshot for delivery governance.

Tracked metrics:

- deployment frequency
- lead time for changes
- change failure rate
- time to restore service

## Commands

```bash
make dora-metrics
```

Manual:

```bash
python3 scripts/report_dora_metrics.py --window-days 28
```

## Data sources

- deploy events log: `docs/reports/dora/deploy_events.jsonl`
- incident log: `docs/reports/dora/incidents.jsonl`
- fallback (if no deploy events): git commit activity in rolling window

## Deploy integration

`scripts/public/deploy.sh` refreshes DORA snapshot after successful deploy:

1. append deploy event (`success`)
2. regenerate `dora_metrics_latest.json/.md`

## Artifacts

- `docs/reports/dora/dora_metrics_latest.json`
- `docs/reports/dora/dora_metrics_latest.md`
- `docs/reports/dora/deploy_events.jsonl`

## Rollback / mitigation

1. If snapshot generation fails, keep current release and inspect script output.
2. Verify git availability and write access to `docs/reports/dora/`.
3. Re-run `make dora-metrics`.
4. If deploy event append fails, add entry manually to `deploy_events.jsonl` and rerun.
