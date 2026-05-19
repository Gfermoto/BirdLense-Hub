#!/usr/bin/env python3
"""Long-run production monitor: YOLO night metrics + behavior flying harvest (#nightly)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_duration(s: str) -> float:
    s = str(s).strip().lower()
    if s.endswith("h"):
        return float(s[:-1]) * 3600.0
    if s.endswith("m"):
        return float(s[:-1]) * 60.0
    return float(s)


def _parse_sessions(log_text: str) -> list[dict]:
    out: list[dict] = []
    for line in log_text.splitlines():
        if "recording_session_summary" not in line:
            continue
        i = line.find("{")
        if i < 0:
            continue
        try:
            out.append(json.loads(line[i:]))
        except json.JSONDecodeError:
            continue
    return out


def _summarize_sessions(sessions: list[dict]) -> dict[str, Any]:
    if not sessions:
        return {"sessions": 0}
    yolo_ran = sum(int(s.get("yolo_frames_ran") or 0) for s in sessions)
    yolo_tr = sum(int(s.get("yolo_frames_with_tracks") or 0) for s in sessions)
    raw_boxes = sum(int(s.get("yolo_raw_boxes_total") or 0) for s in sessions)
    with_tr = sum(1 for s in sessions if int(s.get("yolo_frames_with_tracks") or 0) > 0)
    with_raw = sum(1 for s in sessions if int(s.get("yolo_raw_boxes_total") or 0) > 0)
    blind_conf = sum(1 for s in sessions if s.get("yolo_blind_confirmed"))
    blind_susp = sum(1 for s in sessions if s.get("yolo_blind_suspected"))
    low_light = sum(int(s.get("low_light_blocked_frames") or 0) for s in sessions)
    return {
        "sessions": len(sessions),
        "yolo_frames_ran": yolo_ran,
        "yolo_frames_with_tracks": yolo_tr,
        "yolo_raw_boxes_total": raw_boxes,
        "sessions_with_tracks": with_tr,
        "sessions_with_raw_boxes": with_raw,
        "yolo_blind_confirmed": blind_conf,
        "yolo_blind_suspected": blind_susp,
        "low_light_blocked_frames": low_light,
        "geometry_coverage_pct": round(100.0 * with_raw / len(sessions), 2) if sessions else 0.0,
        "track_session_pct": round(100.0 * with_tr / len(sessions), 2) if sessions else 0.0,
    }


def _docker_logs_since(since: str, *, container: str = "birdlense") -> str:
    try:
        r = subprocess.run(
            ["docker", "logs", container, "--since", since],
            capture_output=True,
            text=True,
            timeout=180,
            stderr=subprocess.STDOUT,
        )
        return r.stdout or ""
    except Exception as exc:
        return f"error: {exc}"


def _mem_snapshot() -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["docker", "stats", "birdlense", "--no-stream", "--format", "{{.MemUsage}}|{{.MemPerc}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        parts = (r.stdout or "").strip().split("|")
        return {"mem_usage": parts[0] if parts else None, "mem_perc": parts[1] if len(parts) > 1 else None}
    except Exception as exc:
        return {"error": str(exc)}


def _disk_snapshot(path: str = "/") -> dict[str, Any]:
    try:
        r = subprocess.run(["df", "-h", path], capture_output=True, text=True, timeout=15)
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        return {"df": lines[-1] if lines else None}
    except Exception as exc:
        return {"error": str(exc)}


def _db_behavior_stats(db_path: Path, since_iso: str) -> dict[str, Any]:
    if not db_path.is_file():
        return {"error": "db missing"}
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    n_videos = con.execute(
        "SELECT COUNT(*) FROM video WHERE deleted_at IS NULL AND created_at >= ?",
        (since_iso,),
    ).fetchone()[0]
    disc = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL AND created_at >= ?
          AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL
          AND LOWER(behavior_label) != LOWER(behavior_shadow_label)
        """,
        (since_iso,),
    ).fetchone()[0]
    with_both = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL AND created_at >= ?
          AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL
        """,
        (since_iso,),
    ).fetchone()[0]
    flying_shadow = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL AND created_at >= ?
          AND LOWER(behavior_shadow_label) = 'flying'
        """,
        (since_iso,),
    ).fetchone()[0]
    flying_meta = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL AND created_at >= ?
          AND LOWER(behavior_label) = 'flying'
        """,
        (since_iso,),
    ).fetchone()[0]
    al_pending = con.execute(
        "SELECT COUNT(*) FROM active_learning_case WHERE status='pending'"
    ).fetchone()[0]
    al_approved = con.execute(
        "SELECT COUNT(*) FROM active_learning_case WHERE status='approved'"
    ).fetchone()[0]
    con.close()
    disc_rate = round(disc / with_both, 4) if with_both else None
    return {
        "videos_since_start": int(n_videos),
        "canary_pairs": int(with_both),
        "discrepancies": int(disc),
        "discrepancy_rate": disc_rate,
        "flying_meta": int(flying_meta),
        "flying_shadow": int(flying_shadow),
        "al_pending": int(al_pending),
        "al_approved": int(al_approved),
    }


def _baseline_snapshot(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {}
    con = sqlite3.connect(str(db_path))
    total_v = con.execute("SELECT COUNT(*) FROM video WHERE deleted_at IS NULL").fetchone()[0]
    disc = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL
          AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL
          AND LOWER(behavior_label) != LOWER(behavior_shadow_label)
        """
    ).fetchone()[0]
    both = con.execute(
        """
        SELECT COUNT(*) FROM video
        WHERE deleted_at IS NULL
          AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL
        """
    ).fetchone()[0]
    con.close()
    return {
        "total_videos": int(total_v),
        "historical_discrepancy_rate": round(disc / both, 4) if both else None,
        "canary_pairs_total": int(both),
    }


def _run_harvest(
    *,
    db_path: Path,
    crops_dir: Path,
    since_iso: str,
    repo_root: Path,
    manifest_path: Path,
    docker_container: str | None = None,
) -> dict[str, Any]:
    if docker_container:
        db_in = "/app/data/db/birdlense.db"
        crops_in = "/app/data/nightly_marathon/crops"
        manifest_in = "/app/data/nightly_marathon/harvest_manifest.jsonl"
        cmd = [
            "docker",
            "exec",
            docker_container,
            "python3",
            "/app/scripts/ml_behavior_harvest_nightly.py",
            "--db",
            db_in,
            "--crops-dir",
            crops_in,
            "--since",
            since_iso,
            "--repo-root",
            "/app",
            "--manifest-append",
            manifest_in,
            "--min-priority",
            "65",
            "--limit",
            "80",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return {"error": (r.stderr or r.stdout or "harvest failed")[:500]}
        line = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "{}"
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"error": "bad harvest json", "raw": line[:300]}

    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from ml_behavior_harvest_nightly import harvest_since

    return harvest_since(
        db_path=db_path,
        crops_root=crops_dir,
        repo_root=repo_root,
        since_iso=since_iso,
        min_priority=65,
        limit=80,
        manifest_append=manifest_path,
    )


def _write_report(
    *,
    out_path: Path,
    baseline: dict[str, Any],
    samples: list[dict[str, Any]],
    harvest_total: dict[str, Any],
    started_at: str,
    ended_at: str,
) -> None:
    if not samples:
        agg = {}
    else:
        sess = [s.get("yolo") or {} for s in samples]
        total_sessions = sum(int(x.get("sessions") or 0) for x in sess)
        total_disc = [s.get("behavior") or {} for s in samples]
        last_beh = total_disc[-1] if total_disc else {}
        agg = {
            "probe_count": len(samples),
            "yolo_sessions_total": total_sessions,
            "last_discrepancy_rate": last_beh.get("discrepancy_rate"),
            "harvest": harvest_total,
        }

    lines = [
        f"# Nightly Marathon Report — {started_at[:10]}",
        "",
        f"- **Started (UTC):** {started_at}",
        f"- **Ended (UTC):** {ended_at}",
        "",
        "## Baseline (pre-flight)",
        "",
        "```json",
        json.dumps(baseline, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Aggregated",
        "",
        "```json",
        json.dumps(agg, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Harvest (flying + discrepancy crops)",
        "",
        "```json",
        json.dumps(harvest_total, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Verdict",
        "",
    ]
    flying_saved = int((harvest_total.get("by_label") or {}).get("flying", 0))
    disc_rate = agg.get("last_discrepancy_rate")
    if flying_saved >= 10 and disc_rate is not None and disc_rate < 0.20:
        lines.append("- **Auto-ready:** discrepancy <20% and ≥10 flying crops — consider `user-config-behavior-auto.partial.yaml`.")
    elif flying_saved >= 10:
        lines.append("- **Retrain v2.1:** enough flying crops; run `ml_behavior_train_video` on merged manifest.")
    else:
        lines.append(f"- **Need more flying data:** only {flying_saved} flying crops harvested; extend observation or lower triggers.")
    if disc_rate is not None:
        lines.append(f"- **Nightly discrepancy rate:** {disc_rate:.1%} (target <20%).")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", default="8h")
    ap.add_argument("--interval", default="30m", help="Probe interval")
    ap.add_argument("--output", required=True, help="JSON metrics output")
    ap.add_argument("--report", default="", help="Markdown report path")
    ap.add_argument("--db", default="app/data/db/birdlense.db")
    ap.add_argument("--container", default="birdlense")
    ap.add_argument("--focus-class", default="flying")
    ap.add_argument("--crops-dir", default="app/data/datasets/nightly_marathon/crops")
    ap.add_argument("--repo-root", default="/app")
    ap.add_argument("--harvest-every", type=int, default=2, help="Harvest every N probes")
    ap.add_argument(
        "--harvest-docker",
        default=os.environ.get("HARVEST_DOCKER_CONTAINER", ""),
        help="Run crop harvest inside this container (needs OpenCV)",
    )
    args = ap.parse_args()

    duration_s = _parse_duration(args.duration)
    interval_s = _parse_duration(args.interval)
    started_at = _utc_now()
    start_dt = datetime.now(timezone.utc)
    end_dt = start_dt + timedelta(seconds=duration_s)
    since_docker = f"{int(interval_s)}s"
    last_probe_at: datetime | None = None

    db_path = Path(args.db).expanduser()
    if not db_path.is_absolute():
        db_path = (REPO / db_path).resolve()
    crops_dir = Path(args.crops_dir).expanduser()
    if not crops_dir.is_absolute():
        crops_dir = (REPO / crops_dir).resolve()
    manifest_path = crops_dir.parent / "harvest_manifest.jsonl"
    out_path = Path(args.output).expanduser()
    if not out_path.is_absolute():
        out_path = (REPO / out_path).resolve()
    report_path = Path(args.report).expanduser() if args.report else out_path.with_suffix(".md")
    if not report_path.is_absolute():
        report_path = (REPO / report_path).resolve()

    baseline = {
        "started_at": started_at,
        "duration_s": duration_s,
        "interval_s": interval_s,
        "focus_class": args.focus_class,
        "disk": _disk_snapshot(),
        "mem": _mem_snapshot(),
        "db": _baseline_snapshot(db_path),
    }

    state: dict[str, Any] = {
        "schema": "nightly_marathon_metrics@v1",
        "started_at": started_at,
        "planned_end_at": end_dt.isoformat(),
        "baseline": baseline,
        "samples": [],
    }
    harvest_total: dict[str, Any] = {"saved": 0, "by_reason": {}, "by_label": {}}
    probe_idx = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print(json.dumps({"event": "marathon_started", "started_at": started_at, "end_at": end_dt.isoformat()}, ensure_ascii=False), flush=True)

    while datetime.now(timezone.utc) < end_dt:
        probe_idx += 1
        now = _utc_now()
        now_dt = datetime.now(timezone.utc)
        if last_probe_at is None:
            log_since = since_docker
        else:
            gap_s = max(1, int((now_dt - last_probe_at).total_seconds()))
            log_since = f"{gap_s}s"
        last_probe_at = now_dt
        log_text = _docker_logs_since(log_since, container=str(args.container))
        sessions = _parse_sessions(log_text)
        if not sessions and "error:" not in (log_text[:80] if log_text else ""):
            yolo = {"sessions": 0, "note": f"No recording_session_summary in last {log_since}"}
        else:
            yolo = _summarize_sessions(sessions)
        behavior = _db_behavior_stats(db_path, started_at)

        harvest_rep: dict[str, Any] | None = None
        if probe_idx % max(1, int(args.harvest_every)) == 0:
            try:
                harvest_rep = _run_harvest(
                    db_path=db_path,
                    crops_dir=crops_dir,
                    since_iso=started_at,
                    repo_root=Path(args.repo_root),
                    manifest_path=manifest_path,
                    docker_container=str(args.harvest_docker).strip() or None,
                )
                harvest_total["saved"] = int(harvest_total.get("saved") or 0) + int(harvest_rep.get("saved") or 0)
                for k, v in (harvest_rep.get("by_reason") or {}).items():
                    harvest_total.setdefault("by_reason", {})[k] = harvest_total["by_reason"].get(k, 0) + v
                for k, v in (harvest_rep.get("by_label") or {}).items():
                    harvest_total.setdefault("by_label", {})[k] = harvest_total["by_label"].get(k, 0) + v
            except Exception as exc:
                harvest_rep = {"error": str(exc)}

        sample = {
            "at": now,
            "probe": probe_idx,
            "yolo": yolo,
            "behavior": behavior,
            "mem": _mem_snapshot(),
            "disk": _disk_snapshot(str(crops_dir.parent) if crops_dir.parent.exists() else "/"),
            "log_hints": {
                "canary_discrepancy_logs": log_text.count("behavior canary discrepancy"),
                "blind_confirmed_logs": log_text.count("yolo_blind_confirmed"),
                "self_healing": log_text.count("yolo_blind_recovered"),
            },
            "harvest": harvest_rep,
        }
        state["samples"].append(sample)
        state["harvest_total"] = harvest_total
        out_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        print(
            json.dumps(
                {
                    "event": "probe",
                    "probe": probe_idx,
                    "sessions": yolo.get("sessions"),
                    "geometry_pct": yolo.get("geometry_coverage_pct"),
                    "disc_rate": behavior.get("discrepancy_rate"),
                    "harvest_saved": harvest_rep.get("saved") if harvest_rep else 0,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

        sleep_s = min(interval_s, max(1.0, (end_dt - datetime.now(timezone.utc)).total_seconds()))
        if sleep_s > 0:
            time.sleep(sleep_s)

    ended_at = _utc_now()
    state["ended_at"] = ended_at
    state["harvest_total"] = harvest_total
    out_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _write_report(
        out_path=report_path,
        baseline=baseline,
        samples=state["samples"],
        harvest_total=harvest_total,
        started_at=started_at,
        ended_at=ended_at,
    )
    print(json.dumps({"event": "marathon_finished", "ended_at": ended_at, "report": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
