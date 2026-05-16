# Hub incident protocol (Frigate parity)

Use this protocol for incidents where Frigate observed an event but Hub did not persist expected output.

Scope: incident classification, evidence collection, and standardized investigation output.

Related:

- reliability plan: [hub-reliability-and-quality-plan](./hub-reliability-and-quality-plan.md)
- operator runbook: [user/runbooks](../user/runbooks.md)

---

## 1) Root-cause taxonomy (reason codes)

Assign exactly one **primary** reason code per incident.

| Code | Bucket | Meaning | Typical evidence |
|---|---|---|---|
| `REC_FILE_MISSING` | recording artifact failure | expected recording file absent after finalize | recording dir exists, `video.mp4` missing |
| `REC_FILE_UNPLAYABLE` | recording artifact failure | file exists but not playable/invalid container (`moov`, truncated) | ffmpeg/decoder errors, finalize video gate fail |
| `REC_ENCODER_FAIL` | recording artifact failure | recording encoder path failed during session (VA-API/ffmpeg) | `VA-API recording failed`, non-zero ffmpeg exit |
| `TRG_COOLDOWN_SUPPRESS` | trigger/cooldown suppression | trigger suppressed by cooldown/requeue policy | `min_seconds_between_recordings`, skip/requeue logs |
| `TRG_QUEUE_DROP` | trigger/cooldown suppression | trigger/event dropped by queue/backpressure | queue-drop counters, saturation logs |
| `FUSION_NO_ACCEPTED` | detection/fusion no-persist | processing ran but no accepted/persisted detection remained | `post_fusion_persisted=0`, decision trace rejects |
| `FUSION_NO_YOLO_NO_FALLBACK` | detection/fusion no-persist | no YOLO tracks and Frigate fallback path did not persist | 0 yolo tracks + frigate events + empty persisted set |
| `CFG_DRIFT` | config drift/environment drift | effective runtime config differs from intended policy | `ml-runtime` mismatch vs expected config |
| `ENV_DRIFT` | config drift/environment drift | runtime env/runtime dependencies differ (devices/driver/tokens/mounts) | readiness/config-audit/env checks mismatch |
| `OPS_RESTART_WINDOW` | operational disruption | deploy/restart overlapped active event window | container restart in event interval |
| `OPS_UPSTREAM_GAP` | operational disruption | upstream connectivity/input gap (broker/camera/network) | mqtt disconnects, stream reconnect gaps |
| `UNKNOWN` | fallback | evidence is insufficient or conflicting | unresolved after mandatory evidence checklist |

Rules:

- Use one primary code; optional `secondary_codes` can be listed in notes.
- `UNKNOWN` is allowed only when mandatory evidence is incomplete or contradictory.

---

## 2) Mandatory evidence checklist

For each incident, collect:

1. **Operator input**
   - camera id
   - local timestamp (MSK)
   - Frigate event/clip reference

2. **Hub logs** (window `T-2m .. T+2m`)
   - processor/finalize lines
   - trigger lines
   - recording/ffmpeg lines

3. **Recording artifact state**
   - recording folder path
   - file presence/size
   - quick playable check result

4. **Data layer**
   - `video` rows around window
   - detection rows around window
   - decision/activity trace rows around window

5. **Effective runtime config**
   - `/api/ui/system/ml-runtime`
   - `/api/ui/readiness`
   - relevant config keys linked to the reason code

---

## 3) Incident report template

Use this schema in issue comments or incident docs:

```yaml
incident_id: "<date>-<camera>-<short-id>"
camera: "Forest"
time_local_msk: "2026-05-15T15:38:00+03:00"
time_utc: "2026-05-15T12:38:00Z"
frigate_reference:
  event_id: "<id>"
  clip: "<url-or-path>"
hub_evidence:
  logs_window_utc: "2026-05-15T12:36:00Z..2026-05-15T12:40:00Z"
  recording_path: "data/recordings/YYYY/MM/DD/HHMMSS/video.mp4"
  recording_file_state: "missing|unplayable|ok"
  db_video_rows: "<summary>"
  db_detection_rows: "<summary>"
  runtime_snapshot:
    encoding: "intel"
    record_with_vaapi: false
    capture_backend: "ffmpeg_vaapi"
root_cause:
  primary_code: "REC_FILE_UNPLAYABLE"
  secondary_codes: []
  detail: "<one paragraph>"
impact:
  user_visible: "<what operator saw>"
  data_impact: "<lost/misaligned entities>"
resolution:
  fix_type: "config|code|ops"
  action_taken: "<what changed>"
  follow_up_issue: "#NNN"
```

---

## 4) Triage outcome mapping

- `REC_*` → recording robustness stream (`area:processor` + `area:infra`).
- `TRG_*` → trigger/cooldown/backpressure stream (`area:processor`).
- `FUSION_*` → fusion/threshold stream (`area:processor`).
- `CFG_DRIFT`, `ENV_DRIFT` → config safety/runtime reproducibility stream (`area:web` + `area:processor` + `area:infra`).
- `OPS_*` → deploy/runtime operations stream (`area:infra`).
- `UNKNOWN` → immediate evidence gap task before any threshold/model tuning.

---

## 5) Definition of ready for closure

Incident is ready to close when:

- mandatory evidence checklist is complete;
- one primary reason code is assigned;
- corrective action (or explicit no-action rationale) is documented;
- follow-up issue is linked if work remains.

