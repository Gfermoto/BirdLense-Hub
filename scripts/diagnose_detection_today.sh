#!/usr/bin/env bash
# Быстрый аудит пропусков за сегодня из логов контейнера birdlense.
# Usage: ./scripts/diagnose_detection_today.sh [hours_back]
set -euo pipefail
HOURS="${1:-12}"
docker logs birdlense --since "${HOURS}h" 2>&1 | python3 - <<'PY'
import json, sys
from collections import Counter, defaultdict

by_cam = defaultdict(lambda: {
    "sessions": 0, "empty": 0, "persisted": 0,
    "yolo_tracks_sum": 0, "rejected_sum": 0, "mqtt_sum": 0,
})
reasons = Counter()
frigate_reject = Counter()
for line in sys.stdin:
    if "recording_session_summary" in line:
        i = line.find("{")
        if i < 0:
            continue
        try:
            d = json.loads(line[i:])
        except json.JSONDecodeError:
            continue
        cam = d.get("triggered_camera") or "?"
        s = by_cam[cam]
        s["sessions"] += 1
        p = int(d.get("post_fusion_persisted") or 0)
        s["persisted"] += p
        if p == 0:
            s["empty"] += 1
        s["yolo_tracks_sum"] += int(d.get("yolo_frames_with_tracks") or 0)
        s["rejected_sum"] += int(d.get("rejected_decision_rows") or 0)
        s["mqtt_sum"] += int(d.get("mqtt_events_in_window") or 0)
        tg = d.get("trigger_graph") or {}
        for k, v in (tg.get("decision_reason_counts") or {}).items():
            reasons[f"{cam}:{k}"] += int(v)
    if "Frigate trigger rejected" in line and "camera=" in line:
        cam = ""
        if "camera=" in line:
            cam = line.split("camera=", 1)[1].split()[0]
        reason = "unknown"
        if "reason=" in line:
            reason = line.split("reason=", 1)[1].split()[0]
        frigate_reject[f"{cam}:{reason}"] += 1

print("=== Sessions (last window) ===")
for cam in sorted(by_cam):
    s = by_cam[cam]
    n = s["sessions"] or 1
    print(
        f"{cam}: sessions={s['sessions']} empty={s['empty']} "
        f"({100*s['empty']//n}%) persisted_total={s['persisted']} "
        f"avg_yolo_tracks={s['yolo_tracks_sum']/n:.0f} avg_rejected={s['rejected_sum']/n:.1f} "
        f"avg_mqtt={s['mqtt_sum']/n:.1f}"
    )
print("\n=== Top YOLO reject reasons ===")
for k, v in reasons.most_common(12):
    print(f"  {v:4d}  {k}")
print("\n=== Top Frigate reject (camera:reason) ===")
for k, v in frigate_reject.most_common(10):
    print(f"  {v:4d}  {k}")
PY
