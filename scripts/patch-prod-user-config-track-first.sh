#!/usr/bin/env bash
# Patch prod user_config for track-first (deploy does not rsync user_config).
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

co = det.setdefault("camera_overrides", {})
for cam in ("BirdBox", "Forest"):
    row = co.setdefault(cam, {})
    row.setdefault("min_confidence_binary", 0.12)
    row.setdefault("min_confidence_binary_bird", 0.12)
    row.setdefault("min_confidence_to_process", 0.12)
    row.setdefault("min_track_duration", 0.5)

forest = co["Forest"]
forest["track_static_reject_max_center_dispersion_norm"] = 0.12
forest["track_static_reject_max_relative_center_dispersion"] = 0.22
forest["track_static_reject_min_duration_sec"] = 3.5

path.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("patched", path)
print("triggers", proc.get("detect_scheduler_triggers"))
print("strip_review", det.get("strip_review_only_overlay_frames"))
PY
echo "Restart processor to apply (Settings → restart processor, or):"
echo "  docker exec birdlense touch /app/data/processor_restart.flag"
