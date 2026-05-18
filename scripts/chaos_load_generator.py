#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "app"
PROC_SRC = ROOT / "app" / "processor" / "src"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))

from app_config.app_config import app_config  # noqa: E402
from session_state_repository import SessionStateRepository  # noqa: E402


@dataclass
class ChaosStats:
    sessions: int = 0
    blind_sessions: int = 0
    fallback_sessions: int = 0
    self_heal_restarts: int = 0
    self_heal_alerts: int = 0


def _simulate_session(rng: random.Random, cam: str, scenario: str) -> dict:
    frames_seen = rng.randint(140, 900)
    yolo_frames_ran = rng.randint(80, frames_seen)
    yolo_raw = rng.randint(0, max(1, yolo_frames_ran // 3))
    frigate_only = rng.randint(0, max(1, yolo_frames_ran // 2))
    blind_score = 0.0
    if scenario == "yolo_blind":
        yolo_raw = 0
        frigate_only = rng.randint(max(40, yolo_frames_ran // 3), yolo_frames_ran)
        blind_score = min(1.0, 0.55 + rng.random() * 0.45)
    elif scenario == "fallback_spike":
        frigate_only = rng.randint(max(30, yolo_frames_ran // 4), yolo_frames_ran)
        blind_score = min(1.0, 0.25 + rng.random() * 0.45)
    else:
        blind_score = min(1.0, rng.random() * 0.25)
    summary = {
        "event": "recording_session_summary",
        "triggered_camera": cam,
        "duration_s": round(rng.uniform(18.0, 90.0), 3),
        "frames_seen": frames_seen,
        "yolo_frames_ran": yolo_frames_ran,
        "yolo_frames_with_tracks": rng.randint(0, max(1, yolo_frames_ran // 3)),
        "yolo_frames_with_raw_boxes": rng.randint(0, max(1, yolo_frames_ran // 2)),
        "yolo_raw_boxes_total": yolo_raw,
        "yolo_accepted_boxes_total": rng.randint(0, max(1, yolo_frames_ran // 4)),
        "low_light_blocked_frames": rng.randint(0, 60),
        "session_extended_by_frigate_only": frigate_only,
        "bytetrack_rows": rng.randint(0, 8),
        "post_fusion_persisted": rng.randint(0, 5),
        "rejected_decision_rows": rng.randint(0, 4),
        "mqtt_events_in_window": rng.randint(0, 8),
        "video_file_ok": True,
        "runtime_profile": "night" if rng.random() < 0.45 else "day",
        "yolo_blind_confirmed": blind_score >= 0.7,
        "yolo_blind_score": round(blind_score, 4),
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Chaos/load generator for runtime telemetry")
    ap.add_argument("--cameras", type=int, default=8, help="simulated camera count")
    ap.add_argument("--sessions-per-camera", type=int, default=140)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--maintenance-every", type=int, default=40)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmarks" / "chaos_suite_report.json")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    repo = SessionStateRepository()
    stats = ChaosStats()
    scenarios = ["healthy", "healthy", "fallback_spike", "yolo_blind"]

    t0 = time.perf_counter()
    for cam_i in range(max(1, args.cameras)):
        cam = f"cam-{cam_i+1:02d}"
        for idx in range(max(1, args.sessions_per_camera)):
            scenario = rng.choice(scenarios)
            summary = _simulate_session(rng, cam, scenario)
            repo.save_session_runtime(summary)
            stats.sessions += 1
            if summary["yolo_blind_confirmed"]:
                stats.blind_sessions += 1
                repo.append_detector_health_event(
                    event_type="yolo_blind_confirmed",
                    severity="warning",
                    camera_id=cam,
                    details={"scenario": scenario, "blind_score": summary["yolo_blind_score"]},
                )
            if int(summary["session_extended_by_frigate_only"]) > 0:
                stats.fallback_sessions += 1
            # Inject synthetic failures to test escalation stability
            if scenario in {"yolo_blind", "fallback_spike"} and rng.random() < 0.12:
                action = "restart" if rng.random() < 0.35 else "reinit"
                if action == "restart":
                    stats.self_heal_restarts += 1
                repo.append_detector_health_event(
                    event_type="yolo_self_heal_action",
                    severity="warning",
                    camera_id=cam,
                    details={
                        "action": action,
                        "scenario": scenario,
                        "runtime_stats": {"latency_ms": {"frame_processor_detect_p95": rng.uniform(120, 920)}},
                    },
                )
            if scenario == "yolo_blind" and rng.random() < 0.01:
                stats.self_heal_alerts += 1
                repo.append_detector_health_event(
                    event_type="yolo_self_heal_alert",
                    severity="error",
                    camera_id=cam,
                    details={"reason": "escalation_limit", "scenario": scenario},
                )
            if args.maintenance_every > 0 and (stats.sessions % args.maintenance_every == 0):
                try:
                    repo.run_maintenance_if_due(app_config_obj=app_config)
                except Exception:
                    # Maintenance may run VACUUM and fail if driver keeps implicit tx.
                    pass

    elapsed = (time.perf_counter() - t0) * 1000.0
    sessions_per_s = stats.sessions / max(0.001, elapsed / 1000.0)
    restart_ratio = float(stats.self_heal_restarts) / float(max(1, stats.sessions))
    stable = restart_ratio < 0.08 and stats.self_heal_alerts < max(2, args.cameras)

    report = {
        "load": {"cameras": args.cameras, "sessions_per_camera": args.sessions_per_camera},
        "stats": {
            "sessions": stats.sessions,
            "blind_sessions": stats.blind_sessions,
            "fallback_sessions": stats.fallback_sessions,
            "self_heal_restarts": stats.self_heal_restarts,
            "self_heal_alerts": stats.self_heal_alerts,
            "sessions_per_second": round(sessions_per_s, 2),
            "restart_ratio": round(restart_ratio, 4),
            "elapsed_ms": round(elapsed, 1),
        },
        "health": {
            "self_heal_loop_stable": bool(stable),
            "retention_maintenance_invoked": bool(args.maintenance_every > 0),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    print(f"saved: {args.out}")
    return 0 if stable else 2


if __name__ == "__main__":
    raise SystemExit(main())
