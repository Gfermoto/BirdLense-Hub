#!/usr/bin/env python3
"""Overnight pipeline watch: trigger, detector, classifier, ReID, behavior (VPS).

Writes JSONL + markdown summary under tmp/overnight_pipeline/.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _http_json(url: str, headers: dict[str, str], timeout: int = 45) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ssh_script(host: str, port: str, body: str, timeout: int = 90) -> tuple[int, str]:
    r = subprocess.run(
        ["ssh", "-p", port, host, body],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out.strip()


def _parse_end_msk(end_msk: str | None, duration_sec: int) -> float:
    if end_msk:
        hh, mm = (int(x) for x in end_msk.split(":"))
        now = datetime.now(MSK)
        end = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if end <= now:
            from datetime import timedelta

            end = end + timedelta(days=1)
        return end.timestamp()
    return time.time() + duration_sec


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch BirdLense pipeline until MSK deadline")
    ap.add_argument("--end-msk", default="07:10", help="Stop at this MSK clock time (default 07:10)")
    ap.add_argument("--interval-sec", type=int, default=600, help="Probe every N seconds (default 10m)")
    ap.add_argument("--audit-every", type=int, default=3, help="Full trigger-detector audit every N ticks")
    ap.add_argument("--out-dir", default="tmp/overnight_pipeline")
    ap.add_argument("--label", default="msk0710")
    args = ap.parse_args()

    base = _env("DEPLOY_URL", "http://185.218.111.196:8085").rstrip("/")
    token = _env("MCP_TOKEN")
    host = _env("DEPLOY_HOST", "root@185.218.111.196")
    port = _env("DEPLOY_SSH_PORT", "2222")
    rdir = _env("DEPLOY_REMOTE_DIR", "/root/BirdLense")
    repo = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    tag = args.label
    out = out_dir / f"pipeline_{tag}.jsonl"
    summary = out_dir / f"pipeline_{tag}_summary.md"
    end_ts = _parse_end_msk(args.end_msk, 0)

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def api(path: str) -> dict:
        return _http_json(base + path, headers)

    db_probe_py = (
        "python3 - <<'PY2'\n"
        "import sqlite3, json\n"
        f"con=sqlite3.connect('{rdir}/app/data/db/birdlense.db')\n"
        "con.row_factory=sqlite3.Row\n"
        "out={}\n"
        "out['videos_3h']=con.execute(\"SELECT COUNT(*) c FROM video WHERE created_at>=datetime('now','-3 hours')\").fetchone()['c']\n"
        "out['decision_trace_3h']=con.execute(\"SELECT COUNT(*) c FROM activity_log WHERE type='decision_trace' AND created_at>=datetime('now','-3 hours')\").fetchone()['c']\n"
        "out['behavior_shadow_3h']=con.execute(\"SELECT COUNT(*) c FROM activity_log WHERE type='behavior_shadow_prediction' AND created_at>=datetime('now','-3 hours')\").fetchone()['c']\n"
        "out['opencv_live_3h']=con.execute(\"SELECT COUNT(*) c FROM activity_log WHERE type='opencv_live' AND created_at>=datetime('now','-3 hours')\").fetchone()['c']\n"
        "row=con.execute(\"SELECT data, created_at FROM activity_log WHERE type='decision_trace' ORDER BY created_at DESC LIMIT 1\").fetchone()\n"
        "if row:\n"
        "  d=json.loads(row['data'])\n"
        "  rc=d.get('recording_context') or {}\n"
        "  rt=rc.get('runtime_signals') or {}\n"
        "  out['last_trace']={'at':row['created_at'],'trigger':rc.get('triggered_by'),'yolo_raw':rt.get('yolo_raw_boxes_total'),'yolo_accepted':rt.get('yolo_accepted_boxes_total'),'yolo_tracks':rt.get('yolo_frames_with_tracks'),'blind':rt.get('yolo_blind_phase')}\n"
        "sp=con.execute(\"SELECT s.name, COUNT(*) n FROM video_species vs JOIN species s ON s.id=vs.species_id JOIN video v ON v.id=vs.video_id WHERE v.created_at>=datetime('now','-3 hours') GROUP BY s.name ORDER BY n DESC LIMIT 5\").fetchall()\n"
        "out['species_3h']=[{'name':r['name'],'n':r['n']} for r in sp]\n"
        "try:\n"
        "  out['reid_embeddings_total']=con.execute('SELECT COUNT(*) c FROM reid_embedding').fetchone()['c']\n"
        "  out['reid_embeddings_24h']=con.execute(\"SELECT COUNT(*) c FROM reid_embedding WHERE created_at>=datetime('now','-24 hours')\").fetchone()['c']\n"
        "except Exception as e:\n"
        "  out['reid_error']=str(e)\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
        "PY2\n"
    )

    def db_probe() -> dict:
        code, out = _ssh_script(host, port, db_probe_py)
        if code != 0:
            return {"error": out[:500]}
        try:
            return json.loads(out or "{}")
        except json.JSONDecodeError as e:
            return {"error": f"parse:{e}", "raw": out[:300]}

    def audit_probe() -> dict:
        cmd = (
            f"python3 {rdir}/scripts/trigger_detector_audit.py --days 1 "
            f"--cameras BirdBox,Forest --db-path {rdir}/app/data/db/birdlense.db"
        )
        code, out = _ssh_script(host, port, cmd, timeout=120)
        if code != 0:
            return {"error": out[-600:]}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"error": "not_json", "tail": out[-400:]}

    def go2rtc_mjpeg_probe() -> dict:
        code, out = _ssh_script(
            host,
            port,
            "curl -sI 'http://127.0.0.1:8085/go2rtc/api/stream.mjpeg?src=BirdBox' | head -8",
            timeout=20,
        )
        cl = "content-length: 0" in out.lower()
        return {"ok": code == 0 and not cl, "headers": out[:400], "empty_mjpeg": cl}

    def sli_probe() -> dict:
        env = os.environ.copy()
        env.setdefault("MAX_HTTP_OVER_1000MS_RATIO", "0.40")
        env.setdefault("MIN_HTTP_SAMPLE_COUNT", "25")
        env["BASE_URL"] = base
        if token:
            env["MCP_TOKEN"] = token
        r = subprocess.run(
            [str(repo / "scripts" / "check-runtime-sli.sh"), "--base-url", base],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            cwd=str(repo),
        )
        return {"ok": r.returncode == 0, "tail": (r.stdout + r.stderr).strip()[-400:]}

    end_human = datetime.fromtimestamp(end_ts, MSK).strftime("%Y-%m-%d %H:%M %Z")
    summary.write_text(
        f"# Pipeline watch `{tag}`\n\n"
        f"- **Until:** {end_human}\n"
        f"- **Interval:** {args.interval_sec}s\n"
        f"- **Base:** {base}\n\n",
        encoding="utf-8",
    )

    tick = 0
    while time.time() < end_ts:
        tick += 1
        ts = datetime.now(timezone.utc).isoformat()
        ts_msk = datetime.now(MSK).strftime("%Y-%m-%d %H:%M:%S")
        rec: dict = {"ts_utc": ts, "ts_msk": ts_msk, "tick": tick, "label": tag}
        alerts: list[str] = []

        try:
            rec["health"] = api("/api/ui/health")
        except Exception as e:
            rec["health_error"] = str(e)
            alerts.append("health_fail")

        try:
            st = api("/api/ui/status")
            rec["status"] = st
            if st.get("processor") != "ok":
                alerts.append("processor_not_ok")
            if st.get("video") != "ok":
                alerts.append("video_not_ok")
            triggers = st.get("active_triggers") or []
            if not triggers:
                alerts.append("no_active_triggers")
        except Exception as e:
            rec["status_error"] = str(e)
            alerts.append("status_fail")

        try:
            dh = api("/api/ui/system/domain-health")
            m = dh.get("metrics") or {}
            rec["domain_health"] = {
                "parity_mismatch_rate_24h": m.get("parity_mismatch_rate_24h"),
                "parity_hotspot_count_24h": m.get("parity_hotspot_count_24h"),
            }
            if (m.get("parity_hotspot_count_24h") or 0) > 0:
                alerts.append("parity_hotspot")
        except Exception as e:
            rec["domain_health_error"] = str(e)

        rec["sli"] = sli_probe()
        if not rec["sli"].get("ok"):
            alerts.append("sli_fail")

        rec["db"] = db_probe()
        db = rec["db"]
        if db.get("error"):
            alerts.append("db_probe_fail")
        else:
            lt = db.get("last_trace") or {}
            if not lt:
                alerts.append("no_decision_trace")
            elif (lt.get("yolo_accepted") or 0) <= 0 and (lt.get("yolo_tracks") or 0) <= 0:
                alerts.append("detector_empty_last")
            if (db.get("decision_trace_3h") or 0) == 0 and (db.get("videos_3h") or 0) > 0:
                alerts.append("traces_missing_with_videos")
            if (db.get("behavior_shadow_3h") or 0) == 0:
                alerts.append("behavior_shadow_idle_3h")

        if tick == 1 or tick % max(1, args.audit_every) == 0:
            rec["trigger_audit"] = audit_probe()
            ta = rec.get("trigger_audit") or {}
            if ta.get("error"):
                alerts.append("audit_fail")
            else:
                for cam, block in (ta.get("cameras") or ta.get("by_camera") or {}).items():
                    samples = (block.get("sample_sessions") or [])[:3]
                    ok_n = sum(1 for s in samples if s.get("verdict") == "ok")
                    rec.setdefault("audit_snapshot", {})[cam] = {
                        "dominant_miss": block.get("dominant_miss_reason"),
                        "ok_samples": ok_n,
                        "recent": samples,
                    }

        if tick == 1 or tick % 6 == 0:
            rec["go2rtc_mjpeg"] = go2rtc_mjpeg_probe()

        rec["alerts"] = alerts
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        lt = (db.get("last_trace") or {}) if isinstance(db, dict) else {}
        line = (
            f"- **{ts_msk}** tick={tick} processor={rec.get('status', {}).get('processor')} "
            f"triggers={rec.get('status', {}).get('active_triggers')} "
            f"videos_3h={db.get('videos_3h')} traces_3h={db.get('decision_trace_3h')} "
            f"behavior_3h={db.get('behavior_shadow_3h')} "
            f"last_yolo={lt.get('yolo_accepted')}/{lt.get('yolo_raw')} tracks={lt.get('yolo_tracks')} "
            f"alerts={','.join(alerts) if alerts else 'none'}\n"
        )
        with summary.open("a", encoding="utf-8") as f:
            f.write(line)

        remaining = int(end_ts - time.time())
        if remaining <= 0:
            break
        sleep_sec = min(args.interval_sec, remaining)
        time.sleep(sleep_sec)

    with summary.open("a", encoding="utf-8") as f:
        f.write(f"\n## Finished\n\nStopped at {datetime.now(MSK).strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
    print(f"Done. Log: {out}\nSummary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
