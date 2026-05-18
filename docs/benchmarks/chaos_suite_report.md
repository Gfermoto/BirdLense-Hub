# Chaos Engineering Suite Report

- Cameras simulated: **10**
- Sessions per camera: **120**
- Total sessions: **1200**
- Throughput: **2288.55 sessions/s** (synthetic DB ingest path)

## Stability Metrics

- Blind sessions: **199**
- Fallback sessions: **1197**
- Self-heal restarts: **27** (`restart_ratio=0.0225`)
- Self-heal alerts: **2**
- Retention maintenance invoked: **true**
- Self-heal loop stable: **true**

## Result

Synthetic load profile with mixed healthy/fallback/blind scenarios passed the loop-stability gate.  
JSON source: `docs/benchmarks/chaos_suite_report.json`.
