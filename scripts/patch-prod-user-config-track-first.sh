#!/usr/bin/env bash
# Patch prod user_config for track-first / persist_mode (deploy does not rsync user_config).
# Prefer schema v2 migration on web startup; this script is for immediate prod reconcile.
# Run on VPS: bash scripts/patch-prod-user-config-track-first.sh
set -euo pipefail
HOST_CFG="${1:-/root/BirdLense/app/app_config/user_config.yaml}"
CONTAINER_CFG="/app/app_config/user_config.yaml"
cp -a "$HOST_CFG" "${HOST_CFG}.bak.track-first-$(date +%Y%m%d%H%M%S)"
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
if int(meta.get("schema_version") or 0) < 2:
    meta["schema_version"] = 2

path.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("patched", path)
print("triggers", proc.get("detect_scheduler_triggers"))
print("persist_mode", det.get("persist_mode"))
print("strip_review", det.get("strip_review_only_overlay_frames"))
PY
echo "Restart processor to apply (Settings → restart processor, or):"
echo "  docker exec birdlense touch /app/data/processor_restart.flag"
