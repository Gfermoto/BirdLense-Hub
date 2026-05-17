#!/usr/bin/env python3
"""6h autonomous observe + safe tune loop for stable YOLO boxes/tracks on deploy target."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "tmp" / "autonomous-tune-6h"

PROFILES: dict[str, dict] = {
    "openvino_gpu_a": {
        "processor.inference_backend": "openvino",
        "processor.inference_device": "intel:gpu",
        "processor.models.binary_openvino": "models/detection/weights/best_openvino_model",
        "processor.min_confidence_binary": 0.18,
        "processor.min_confidence_binary_bird": 0.18,
        "processor.binary_imgsz": 640,
        "processor.inference_lores_px": 640,
        "processor.auto_unstick_no_track_frames": 60,
        "processor.classifier_use_source_frame": True,
        "detection.track_fragment_merge_enabled": True,
    },
    "openvino_gpu_b": {
        "processor.inference_backend": "openvino",
        "processor.inference_device": "intel:gpu",
        "processor.models.binary_openvino": "models/detection/weights/best_openvino_model",
        "processor.min_confidence_binary": 0.16,
        "processor.min_confidence_binary_bird": 0.16,
        "processor.openvino_binary_track_ultralytics_conf": 0.028,
        "processor.binary_track_iou": 0.65,
        "processor.min_box_size_px": 28,
        "processor.auto_unstick_no_track_frames": 90,
        "processor.classifier_use_source_frame": True,
        "detection.track_fragment_merge_enabled": True,
    },
    "torch_cpu_soft": {
        "processor.inference_backend": "torch",
        "processor.inference_device": "cpu",
        "processor.min_confidence_binary": 0.16,
        "processor.min_confidence_binary_bird": 0.16,
        "processor.binary_track_iou": 0.65,
        "processor.min_box_size_px": 28,
        "processor.auto_unstick_no_track_frames": 60,
        "processor.classifier_use_source_frame": True,
        "detection.track_fragment_merge_enabled": True,
    },
    "openvino_gpu_c": {
        "processor.inference_backend": "openvino",
        "processor.inference_device": "intel:gpu",
        "processor.models.binary_openvino": "models/detection/weights/best_openvino_model",
        "processor.min_confidence_binary": 0.14,
        "processor.min_confidence_binary_bird": 0.14,
        "processor.openvino_binary_bird_score_scale": 9.5,
        "processor.openvino_binary_track_ultralytics_conf": 0.025,
        "processor.binary_track_iou": 0.62,
        "processor.min_box_size_px": 24,
        "processor.auto_unstick_no_track_frames": 120,
        "processor.classifier_use_source_frame": True,
        "detection.track_fragment_merge_enabled": True,
        "detection.merge_window_seconds": 15,
    },
}

PHASE_PLAN = [
    ("openvino_gpu_a", 5400),
    ("openvino_gpu_b", 5400),
    ("openvino_gpu_c", 5400),
    ("torch_cpu_soft", 5400),
]


def _log(msg: str, log_path: Path) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    line = f"{ts} {msg}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def _ssh(cmd: str, *, port: str, host: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-p", port, host, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _metrics_from_logs(since: str = "45m") -> dict:
    r = subprocess.run(
        ["ssh", "-p", os.environ["DEPLOY_SSH_PORT"], os.environ["DEPLOY_HOST"],
         f"docker logs birdlense --since {since} 2>&1"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = r.stdout + r.stderr
    stats: list[dict] = []
    for line in text.splitlines():
        if "recording_session_summary" not in line:
            continue
        m = re.search(r"\{.*\}", line)
        if not m:
            continue
        try:
            stats.append(json.loads(m.group()))
        except json.JSONDecodeError:
            continue
    n = len(stats)
    if n == 0:
        return {"sessions": 0}
    frames_ran = sum(int(s.get("yolo_frames_ran") or 0) for s in stats)
    frames_tracks = sum(int(s.get("yolo_frames_with_tracks") or 0) for s in stats)
    sess_with_tracks = sum(1 for s in stats if int(s.get("yolo_frames_with_tracks") or 0) > 0)
    bt_rows = sum(int(s.get("bytetrack_rows") or 0) for s in stats)
    persisted = sum(int(s.get("post_fusion_persisted") or 0) for s in stats)
    no_track_warns = text.count("no track ids after retry")
    slow_frames = text.count("Slow frame processing")
    return {
        "sessions": n,
        "sessions_with_track_frames_pct": round(100.0 * sess_with_tracks / n, 2),
        "track_frame_pct": round(100.0 * frames_tracks / max(1, frames_ran), 2),
        "bytetrack_rows_total": bt_rows,
        "post_fusion_persisted_total": persisted,
        "no_track_id_warnings": no_track_warns,
        "slow_frame_warnings": slow_frames,
    }


def _apply_profile(profile: dict, *, rdir: str, port: str, host: str, log_path: Path) -> None:
    patch_b64 = __import__("base64").b64encode(json.dumps(profile).encode()).decode()
    py = f"""
import base64, json, shutil, yaml
from datetime import datetime, timezone
from pathlib import Path
p = Path('{rdir}/app/app_config/user_config.yaml')
bak = p.with_suffix('.yaml.bak.autotune_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
shutil.copy2(p, bak)
cfg = yaml.safe_load(p.read_text(encoding='utf-8')) or {{}}
patch = json.loads(base64.b64decode('{patch_b64}').decode())
for dotted, val in patch.items():
    parts = dotted.split('.')
    cur = cfg
    for k in parts[:-1]:
        cur = cur.setdefault(k, {{}})
    cur[parts[-1]] = val
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding='utf-8')
print('applied', len(patch), 'keys backup', bak)
"""
    r = _ssh(f"python3 - <<'PY'\n{py}\nPY", port=port, host=host)
    _log(f"apply_profile rc={r.returncode} out={(r.stdout or '').strip()} err={(r.stderr or '')[:200]}", log_path)
    env_patch = (
        f"grep -q '^BIRDLENSE_INFERENCE_BACKEND=' {rdir}/app/.env && "
        f"sed -i 's/^BIRDLENSE_INFERENCE_BACKEND=.*/BIRDLENSE_INFERENCE_BACKEND={profile.get('processor.inference_backend', 'openvino')}/' {rdir}/app/.env || "
        f"echo 'BIRDLENSE_INFERENCE_BACKEND={profile.get('processor.inference_backend', 'openvino')}' >> {rdir}/app/.env; "
        f"grep -q '^BIRDLENSE_INFERENCE_DEVICE=' {rdir}/app/.env && "
        f"sed -i 's/^BIRDLENSE_INFERENCE_DEVICE=.*/BIRDLENSE_INFERENCE_DEVICE={profile.get('processor.inference_device', 'intel:gpu')}/' {rdir}/app/.env || "
        f"echo 'BIRDLENSE_INFERENCE_DEVICE={profile.get('processor.inference_device', 'intel:gpu')}' >> {rdir}/app/.env"
    )
    if "inference_backend" in str(profile) or "inference_device" in str(profile):
        backend = profile.get("processor.inference_backend", "openvino")
        device = profile.get("processor.inference_device", "intel:gpu")
        dedupe = (
            f"grep -v '^BIRDLENSE_INFERENCE_BACKEND=' {rdir}/app/.env | "
            f"grep -v '^BIRDLENSE_INFERENCE_DEVICE=' > {rdir}/app/.env.tmp && "
            f"mv {rdir}/app/.env.tmp {rdir}/app/.env && "
            f"echo 'BIRDLENSE_INFERENCE_BACKEND={backend}' >> {rdir}/app/.env && "
            f"echo 'BIRDLENSE_INFERENCE_DEVICE={device}' >> {rdir}/app/.env"
        )
        _ssh(dedupe, port=port, host=host, timeout=30)
    _ssh(f"touch {rdir}/app/data/restart_processor.flag", port=port, host=host)
    _ssh(f"cd {rdir}/app && docker compose restart birdlense", port=port, host=host, timeout=180)
    time.sleep(45)


def _health(base: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        req = urllib.request.Request(base.rstrip("/") + "/api/ui/status", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-sec", type=int, default=21600)
    ap.add_argument("--probe-interval-sec", type=int, default=600)
    args = ap.parse_args()

    base = os.environ.get("DEPLOY_URL", "").rstrip("/")
    token = os.environ.get("MCP_TOKEN", "")
    host = os.environ.get("DEPLOY_HOST", "")
    port = os.environ.get("DEPLOY_SSH_PORT", "22")
    rdir = os.environ.get("DEPLOY_REMOTE_DIR", "/root/BirdLense")

    log_path = OUT_DIR / "autotune.log"
    summary_path = OUT_DIR / "summary.jsonl"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    _log("START 6h autonomous track tune", log_path)
    baseline = _metrics_from_logs("2h")
    _log(f"baseline_2h {json.dumps(baseline)}", log_path)
    with summary_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"phase": "baseline", "metrics": baseline}, ensure_ascii=False) + "\n")

    end_ts = time.time() + args.duration_sec
    phase_idx = 0
    phase_started = time.time()
    best = {"score": -1.0, "profile": None, "metrics": None}

    profile_name, phase_duration = PHASE_PLAN[0]
    _log(f"PHASE 0 apply {profile_name}", log_path)
    _apply_profile(PROFILES[profile_name], rdir=rdir, port=port, host=host, log_path=log_path)
    phase_started = time.time()

    while time.time() < end_ts:
        st = _health(base, token)
        m = _metrics_from_logs(f"{max(10, args.probe_interval_sec // 60)}m")
        score = (
            float(m.get("track_frame_pct") or 0) * 2.0
            + float(m.get("sessions_with_track_frames_pct") or 0)
            + min(50.0, float(m.get("bytetrack_rows_total") or 0))
            - float(m.get("no_track_id_warnings") or 0) * 0.5
        )
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phase": profile_name,
            "status": st,
            "metrics": m,
            "score": score,
        }
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _log(f"probe phase={profile_name} score={score:.1f} metrics={json.dumps(m)}", log_path)
        if score > best["score"]:
            best = {"score": score, "profile": profile_name, "metrics": m}

        if time.time() - phase_started >= phase_duration and phase_idx + 1 < len(PHASE_PLAN):
            phase_idx += 1
            profile_name, phase_duration = PHASE_PLAN[phase_idx]
            _log(f"PHASE {phase_idx} apply {profile_name}", log_path)
            _apply_profile(PROFILES[profile_name], rdir=rdir, port=port, host=host, log_path=log_path)
            phase_started = time.time()

        time.sleep(args.probe_interval_sec)

    # Re-apply best profile
    if best["profile"]:
        _log(f"FINAL re-apply best={best['profile']} score={best['score']}", log_path)
        _apply_profile(PROFILES[best["profile"]], rdir=rdir, port=port, host=host, log_path=log_path)

    final_m = _metrics_from_logs("30m")
    _log(f"DONE best={json.dumps(best)} final_30m={json.dumps(final_m)}", log_path)
    with (OUT_DIR / "best_profile.json").open("w", encoding="utf-8") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
