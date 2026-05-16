# Hub Reliability and Quality Plan (Frigate-parity target)

Goal: make BirdLense Hub **not worse than Frigate** on the same cameras/site by improving event capture reliability, traceability, and operator trust.

This is a working plan for investigation and delivery. It does **not** replace release gates or incident runbooks.

Investigation standard and reason-code taxonomy: [hub-incident-protocol](./hub-incident-protocol.md).

---

## 1) Quality target and guardrails

### Product target

- Hub should keep up with Frigate on meaningful events (same camera/time), while preserving Hub-specific quality filters.
- We do **not** mirror Frigate blindly; we keep Hub data integrity (valid video file, consistent DB state, explainable decisions).

### Guardrails

- Avoid regressions in CPU load and sustained latency.
- Keep false-positive growth bounded when improving recall.
- Every missed event investigation must end with a classified root cause.

---

## 2) Problem classes to investigate

Use these root-cause buckets for every incident:

1. **Recording artifact failure**
   - broken/missing MP4 (`moov atom`, empty/missing file), ffmpeg/VA-API failures.
2. **Trigger/cooldown suppression**
   - event dropped by `min_seconds_between_recordings`, queueing/requeue effects.
3. **Detection/fusion no-persist outcome**
   - no YOLO tracks, Frigate fallback path rejected, thresholds too strict.
4. **Config drift / environment drift**
   - runtime config differs from expected (`user_config`, `.env`, backend/device mismatch).
5. **Operational disruption**
   - restarts/deploy overlap with active sessions, broker/network issues.

---

## 3) Workstreams (prioritized)

## W1 — Incident visibility (highest priority)

Outcome: operator can see why Hub missed an event without reading raw container logs.

- Add explicit machine-readable reason codes for “Frigate seen, Hub not persisted”.
- Persist reason snapshots to activity/audit records.
- Expose counters and recent samples via system API/UI card.

Success criteria:

- For each missed event, operator can map it to one reason code in < 2 minutes.

## W2 — Recording robustness without CPU regression

Outcome: stable recording artifacts with minimal performance impact.

- Keep split control between capture path and recording encode path.
- Track recording failures as first-class metrics and alert signals.
- Validate “playable file” reliability under production-like load.

Success criteria:

- Zero “detection persisted but file missing/broken” incidents for 7 consecutive days.

## W3 — Frigate/Hub parity diagnostics

Outcome: objective parity tracking instead of anecdotal checks.

- Build daily parity report for time-windowed Frigate-vs-Hub event matching.
- Track parity KPIs by camera and period (day/night).
- Add top mismatch reasons from W1 in the same report.

Success criteria:

- Stable trend line; mismatch rate and top causes visible day-over-day.

## W4 — Config safety and reproducibility

Outcome: fewer “unknown state” incidents after tuning/deploy.

- Introduce config presets for common goals (stability / recall / balanced).
- Add preflight checks for risky combinations.
- Keep runtime status endpoint aligned with effective config.

Success criteria:

- No incidents caused by unnoticed config drift during two release cycles.

---

## 4) Investigation protocol (for each incident)

Input from operator:

- camera id, local timestamp (MSK), Frigate evidence reference (event/clip id).

Mandatory evidence collection:

1. Hub processor logs in ±2 min window.
2. recording directory/file presence and file health.
3. DB rows around the window (video + detections + activity trace).
4. effective runtime config snapshot (`ml-runtime`, readiness, relevant keys).

Output template:

- `incident_id`
- `camera`, `time_local`, `time_utc`
- `root_cause_bucket` (from section 2)
- `root_cause_detail`
- `user_impact`
- `fix_type` (config / code / ops)
- `follow_up_issue`

---

## 5) KPIs (weekly review)

- **Parity mismatch rate**: Frigate event with no persisted Hub event in matching window.
- **Artifact integrity rate**: persisted Hub detections with playable MP4.
- **Unexplained miss rate**: misses without classified root cause.
- **Recovery lead time**: median time from report to classified root cause.
- **Performance guardrails**: p95 latency / error rate / CPU budget (from runtime gates).

---

## 6) Execution milestones

### Milestone A (1 week)

- Finalize reason-code taxonomy.
- Add structured incident template and investigation checklist.
- Start weekly KPI log.

### Milestone B (2–3 weeks)

- Deliver W1 visibility in API + operator-facing diagnostics.
- Integrate basic parity report generation.

### Milestone C (3–5 weeks)

- Harden recording robustness checks and alerting.
- Add config safety checks and preset documentation.

### Milestone D (ongoing)

- Tune thresholds/fusion based on parity evidence.
- Keep mismatch-rate trend within agreed target.

---

## 7) Definition of done for this plan

This plan is considered established when:

- It is linked from contributor docs.
- Each new missed-event report follows section 4 protocol.
- Weekly KPI review is running with historical trend.

