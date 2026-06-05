# Quality Baseline — 2026-05-26 (MSK 07:10)

Source run:
- window: `2026-05-25 21:26` -> `2026-05-26 07:10` (MSK)
- ticks: `57`
- log: `tmp/overnight_pipeline/pipeline_msk0710_20260526.jsonl`

## Baseline snapshot

- status chain (`processor/video/web`): `57/57 ok`
- runtime SLI: `56/57 ok`, single latency spike in tick 2
- active trigger: `opencv` across run
- detector/tracks during activity: present (`yolo_accepted_boxes_total > 0`)
- classifier output: present (`Bird`, `Unknown`, `Eurasian Magpie`, ...)
- behavior shadow: present in active windows, idle at night
- ReID table size: `534`, new rows in 24h: `0`
- go2rtc native MJPEG checks: `11/11 ok`

## Stop-the-line gates for quality patches

Any condition below blocks deploy:

1. `status.processor != ok` OR `status.video != ok` OR `status.web != ok`
2. `readiness.ready == false`
3. species coverage drift:
   - `allowlist_total < 526`, or
   - `species_matched < 520`
4. trigger-detector audit dominant miss reason in `{detector_empty, detector_blind, ingest_failed}` for any production camera
5. runtime SLI hard fail:
   - heartbeat stale, or
   - heartbeat age above configured max
6. optional strict quality gate (`REQUIRE_STRICT_QUALITY_READY=1`) fails

Soft warnings (do not block by default):
- `parity_hotspot_count_24h > 0` (can be elevated to blocking with `FAIL_ON_PARITY_HOTSPOT=1`)
- ReID no-growth in low-activity windows

## Runbook command

```bash
make verify
make verify-runtime-sli
make quality-gate
```

For strict mode:

```bash
REQUIRE_STRICT_QUALITY_READY=1 FAIL_ON_PARITY_HOTSPOT=1 make quality-gate
```
