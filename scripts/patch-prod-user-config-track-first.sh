#!/usr/bin/env bash
# Patch prod user_config for classification-first / binary_track_first (deploy does not rsync user_config).
# Prefer schema v4 migration on web startup; this script is for immediate prod reconcile.
# Run on VPS: bash scripts/patch-prod-user-config-track-first.sh
set -euo pipefail
HOST_CFG="${1:-/root/BirdLense/app/app_config/user_config.yaml}"
CONTAINER_CFG="/app/app_config/user_config.yaml"
cp -a "$HOST_CFG" "${HOST_CFG}.bak.classification-first-$(date +%Y%m%d%H%M%S)"
docker exec birdlense python3 - "$CONTAINER_CFG" <<'PY'
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

proc = cfg.setdefault("processor", {})
triggers = list(proc.get("detect_scheduler_triggers") or ["frigate", "motion_sensor", "scales"])
if "opencv" not in triggers:
    proc["detect_scheduler_triggers"] = ["opencv", *triggers]

det = cfg.setdefault("detection", {})
det["strip_review_only_overlay_frames"] = False
det["track_first_gate_enabled"] = True
det.setdefault("persist_mode", "binary_track_first")
det["weighted_arbiter_enabled"] = False
det["hypothesis_arbitration_enabled"] = False
det["yolo_weak_track_salvage_enabled"] = False

proc["bird_skip_classifier_max_area_frac"] = 0
proc["classifier_best_guess_enabled"] = True
proc["classifier_best_guess_min_events"] = 1
proc["birder_eu_min_confidence"] = 0.15

roles = proc.setdefault("camera_tuning_by_role", {})
far = roles.setdefault("feeder_far", {})
if isinstance(far, dict):
    far["track_static_reject_enabled"] = False
    far["min_confidence_binary_bird"] = 0.08

if proc.pop("camera_overrides", None) is not None:
    print("removed processor.camera_overrides (use video.cameras[].tuning_role)")

video = cfg.setdefault("video", {})
cameras = video.get("cameras")
role_by_id = {"BirdBox": "feeder_close", "Forest": "feeder_far"}
if isinstance(cameras, list):
    for row in cameras:
        if not isinstance(row, dict):
            continue
        cam_id = str(row.get("id") or "").strip()
        if cam_id in role_by_id and not str(row.get("tuning_role") or "").strip():
            row["tuning_role"] = role_by_id[cam_id]

meta = cfg.setdefault("_meta", {})
meta["schema_version"] = 4

path.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("patched", path)
print("birder_min", proc.get("birder_eu_min_confidence"))
print("best_guess_events", proc.get("classifier_best_guess_min_events"))
print("feeder_far_static_off", (roles.get("feeder_far") or {}).get("track_static_reject_enabled"))
print("schema_version", meta.get("schema_version"))
PY
echo "Restart processor to apply (Settings → restart processor, or):"
echo "  docker exec birdlense touch /app/data/processor_restart.flag"
