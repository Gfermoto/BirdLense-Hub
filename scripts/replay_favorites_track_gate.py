#!/usr/bin/env python3
"""Track-density replay for favorite mp4 on VPS (#591/#599).

Uses deep_pipeline_today_runner (track regen path) — validates yolo/track
substrate without requiring live birds or full persist tail.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Reuse VPS helpers from deep_pipeline_today_vps
sys.path.insert(0, str(REPO / "scripts"))
from deep_pipeline_today_vps import (  # noqa: E402
    _env,
    _run_remote_runner_batched,
    _ssh,
)


def _load_deploy_local() -> None:
    local = REPO / "scripts" / "deploy.local.sh"
    if not local.is_file():
        return
    res = subprocess.run(
        ["bash", "-lc", f"source {local} && env"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return
    for line in res.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key and key not in os.environ:
            os.environ[key] = val


def _load_favorite_paths(*, host: str, port: str, remote_db: str) -> list[str]:
    sql_py = (
        "python3 - <<'PY'\n"
        "import sqlite3, json\n"
        f"con=sqlite3.connect({remote_db!r})\n"
        "rows=con.execute(\n"
        "  \"SELECT video_path FROM video WHERE deleted_at IS NULL AND favorite=1 ORDER BY id\"\n"
        ").fetchall()\n"
        "print(json.dumps([r[0] for r in rows if r[0]], ensure_ascii=False))\n"
        "PY"
    )
    res = _ssh(host, port, sql_py, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    paths = json.loads((res.stdout or "").strip() or "[]")
    out: list[str] = []
    for p in paths:
        p = str(p).strip().replace("\\", "/")
        if p.startswith("data/"):
            out.append(f"/app/{p}")
        elif p.startswith("/app/"):
            out.append(p)
        else:
            out.append(f"/app/data/recordings/{p.split('recordings/', 1)[-1]}")
    return out


def main() -> int:
    _load_deploy_local()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=_env("DEPLOY_HOST", "birdlense"))
    ap.add_argument("--port", default=_env("DEPLOY_SSH_PORT", "22"))
    ap.add_argument("--container", default=_env("REPLAY_CONTAINER", "birdlense"))
    ap.add_argument("--remote-dir", default=_env("DEPLOY_REMOTE_DIR", "/root/BirdLense"))
    ap.add_argument("--remote-db", default=_env("REPLAY_REMOTE_DB", "/root/BirdLense/app/data/db/birdlense.db"))
    ap.add_argument("--frame-step", type=int, default=4)
    ap.add_argument("--max-runtime-sec", type=int, default=600)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--min-fused-tracks", type=int, default=1, help="SLO: min fused tracks per clip")
    ap.add_argument("--json-out", default=str(REPO / ".artifacts/replay-favorites/track_gate_latest.json"))
    args = ap.parse_args()

    host = args.host
    if host not in ("localhost", "127.0.0.1") and _env("BIRDLENSE_ALLOW_REMOTE_MUTATION") != "1":
        print("Set BIRDLENSE_ALLOW_REMOTE_MUTATION=1 for remote runs", file=sys.stderr)
        return 2

    videos = _load_favorite_paths(host=host, port=args.port, remote_db=args.remote_db)
    if not videos:
        print(json.dumps({"error": "no_favorites"}))
        return 1

    runner_report = _run_remote_runner_batched(
        host=host,
        port=args.port,
        container=args.container,
        remote_dir=args.remote_dir,
        videos=videos,
        frame_step=args.frame_step,
        max_runtime_sec=args.max_runtime_sec,
        timeout=max(3600, args.max_runtime_sec * len(videos)),
        batch_size=args.batch_size,
        inference_backend=_env("BIRDLENSE_INFERENCE_BACKEND", "auto"),
        inference_device=_env("BIRDLENSE_INFERENCE_DEVICE", "cpu"),
        classifier_backend=_env("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", "auto"),
        classifier_device=_env("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", "cpu"),
    )

    per = runner_report.get("videos") or []
    passed = 0
    failed = 0
    rows: list[dict] = []
    for v in per:
        fused = int(v.get("fused_track_count") or 0)
        ok = fused >= args.min_fused_tracks and not v.get("error")
        if ok:
            passed += 1
        else:
            failed += 1
        rows.append({**v, "slo_ok": ok})

    report = {
        "report_format": "replay_favorites_track_gate@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "videos_total": len(videos),
        "videos_passed": passed,
        "videos_failed": failed,
        "min_fused_tracks": args.min_fused_tracks,
        "runner": runner_report,
        "videos": rows,
    }
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": failed == 0, "passed": passed, "failed": failed, "out": str(out)}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
