# Runtime SLO Stability Runbook

S8 runtime guardrails for latency/FPS/stability and graceful recovery.

## Inputs

- API: `GET /api/ui/system/domain-health`
- Script: `scripts/check-runtime-sli.sh`
- Script: `scripts/perf_gate_runtime.py`
- Script: `scripts/verify_runtime_slo_dashboard.py`

## SLO Targets (v1)

- sustained process FPS: `>= 7.0`
- skipped ratio: `<= 0.05`
- pipeline latency p95: `<= 2500 ms`
- per-camera warn count: `0` in green state

## Quick Triage

```bash
curl -s -H "X-Birdlense-Api-Key: $BIRDLENSE_UI_API_KEY" \
  "$BASE_URL/api/ui/system/domain-health" | jq '.slo_dashboard,.alerting_rules'
./scripts/check-runtime-sli.sh --base-url "$BASE_URL"
python3 scripts/perf_gate_runtime.py --base-url "$BASE_URL" --out /tmp/runtime_perf_gate.json
python3 scripts/verify_runtime_slo_dashboard.py --report /tmp/domain_health.json
```

## Recovery Playbook

### sustained-fps-floor

1. Check `runtime_slo_per_camera_24h` for `status=warn`.
2. Inspect backend flapping (`video_encoding_transitions_24h`, `capture_backend_counts_24h`).
3. Switch camera profile to throughput mode and reduce workload (higher dedup window, lower model load).

### skipped-ratio

1. Open backpressure snapshot: `GET /api/ui/system/diagnostics/backpressure`.
2. If queue depth grows: reduce concurrent heavy jobs and enforce finalize queue drain.
3. Check MQTT publish queue caps (`mqtt.publish_queue_max`) and reconnect jitter.

### pipeline-latency-p95

1. Run `scripts/perf_gate_runtime.py` and compare p95/p99 with last green run.
2. Confirm processor heartbeat and HTTP slow ratio via `check-runtime-sli.sh`.
3. Temporarily switch to latency profile for affected cameras and re-check.

### reconnect-resilience

1. Review detector health events (`reconnect` event types).
2. Verify network stability and camera stream source health.
3. Tune reconnect window (`reconnect_min_delay`, `reconnect_max_delay`, jitter).

### backpressure-control

1. Audit classification/finalize queue depths and drop counters.
2. Reduce ingress rate and disable non-critical heavy tasks.
3. Restart stack only after queue pressure is reduced and heartbeat stable.
