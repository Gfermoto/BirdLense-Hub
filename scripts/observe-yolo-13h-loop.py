#!/usr/bin/env python3
"""13h YOLO visibility watch: periodic probes, deduped session summaries, final report."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


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


def _session_key(s: dict) -> str:
    return "|".join(
        [
            str(s.get("triggered_camera") or ""),
            str(s.get("duration_s") or ""),
            str(s.get("yolo_frames_ran") or ""),
            str(s.get("yolo_raw_boxes_total") or ""),
            str(s.get("post_fusion_persisted") or ""),
        ]
    )


def _summarize(sessions: list[dict]) -> dict:
    if not sessions:
        return {"sessions": 0}
    yolo_ran = sum(int(s.get("yolo_frames_ran") or 0) for s in sessions)
    yolo_tr = sum(int(s.get("yolo_frames_with_tracks") or 0) for s in sessions)
    raw_frames = sum(int(s.get("yolo_frames_with_raw_boxes") or 0) for s in sessions)
    raw_boxes = sum(int(s.get("yolo_raw_boxes_total") or 0) for s in sessions)
    with_tr = sum(1 for s in sessions if int(s.get("yolo_frames_with_tracks") or 0) > 0)
    with_raw = sum(1 for s in sessions if int(s.get("yolo_frames_with_raw_boxes") or 0) > 0)
    frigate_ext = sum(int(s.get("session_extended_by_frigate_only") or 0) for s in sessions)
    return {
        "sessions": len(sessions),
        "yolo_frames_ran": yolo_ran,
        "yolo_frames_with_tracks": yolo_tr,
        "yolo_frames_with_raw_boxes": raw_frames,
        "yolo_raw_boxes_total": raw_boxes,
        "sessions_with_tracks": with_tr,
        "sessions_with_raw_boxes": with_raw,
        "sessions_frigate_extended_only_frames": frigate_ext,
        "track_rate_pct": round(100.0 * yolo_tr / yolo_ran, 2) if yolo_ran else None,
        "raw_frame_rate_pct": round(100.0 * raw_frames / yolo_ran, 2) if yolo_ran else None,
        "pct_sessions_with_raw": round(100.0 * with_raw / len(sessions), 2),
        "pct_sessions_with_tracks": round(100.0 * with_tr / len(sessions), 2),
    }


def _docker_logs(since: str, *, container: str) -> str:
    r = subprocess.run(
        ["docker", "logs", container, "--since", since, "2>&1"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return (r.stdout or "") + (r.stderr or "")


def _db_providers_since(db_path: Path, started_at: str) -> list[dict]:
    if not db_path.is_file():
        return []
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT COALESCE(vs.detection_provider, '?') AS p, COUNT(*) AS n
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        WHERE v.created_at >= ?
        GROUP BY p ORDER BY n DESC
        """,
        (started_at,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _db_videos_since(db_path: Path, started_at: str) -> int:
    if not db_path.is_file():
        return 0
    con = sqlite3.connect(str(db_path))
    n = con.execute(
        "SELECT COUNT(*) FROM video WHERE created_at >= ?",
        (started_at,),
    ).fetchone()[0]
    con.close()
    return int(n)


def _log_warnings(log_text: str) -> dict:
    return {
        "no_track_id_warnings": log_text.count("no track ids after retry"),
        "predict_fallback_hits": log_text.count("Track->predict fallback recovered"),
        "slow_frame_warnings": log_text.count("Slow frame processing"),
        "processor_api_400": log_text.count("api/processor/videos: 400"),
    }


def _recommendations(
    agg: dict,
    providers: list[dict],
    warnings: dict,
    *,
    videos_n: int,
    container_uptime_note: str,
) -> list[str]:
    rec: list[str] = []
    n = int(agg.get("sessions") or 0)
    if n == 0:
        rec.append(
            "За окно нет recording_session_summary: проверить motion (OpenCV/Frigate BirdBox), "
            "не пересоздавали ли контейнер (логи обнуляются), min_seconds_between_recordings."
        )
        if videos_n == 0:
            rec.append("В БД нет новых video за окно — триггеров записи не было.")
        return rec

    raw_pct = float(agg.get("pct_sessions_with_raw") or 0)
    tr_pct = float(agg.get("pct_sessions_with_tracks") or 0)
    raw_total = int(agg.get("yolo_raw_boxes_total") or 0)

    if raw_total == 0:
        rec.append(
            "YOLO крутился (yolo_frames_ran>0?), но yolo_raw_boxes_total=0: проверить detect RTSP 704×576, "
            "letterbox 640, OpenVINO GPU; offline compare_yolo_detect_rtsp.py на площадке."
        )
    elif raw_pct < 30:
        rec.append(
            f"Сырые боксы только в {raw_pct}% сессий — смягчить openvino_binary_track_ultralytics_conf / "
            "unstick / track_to_predict_fallback; убедиться что generic_bird_min_detector_conf ≤ 0.12."
        )

    if raw_total > 0 and tr_pct < 25:
        rec.append(
            f"Треки в {tr_pct}% сессий при наличии raw — проверить bytetrack_birdlense_unstick.yaml, "
            "iou_id_fallback_live; ByteTrack track_high_thresh vs track(conf)."
        )

    prov = {r["p"]: int(r["n"]) for r in providers}
    yolo_db = prov.get("yolo", 0)
    frigate_db = prov.get("frigate", 0)
    total_db = sum(prov.values()) or 1
    if frigate_db > yolo_db * 2 and frigate_db > 3:
        rec.append(
            f"В БД за окно frigate ({frigate_db}) >> yolo ({yolo_db}): decision/fusion — "
            "generic_bird 0.10, min_confidence_to_process 0.20, yolo_weak_track_salvage; "
            "не поднимать frigate_standalone_min_score без нужды."
        )
    if yolo_db >= 3 and tr_pct >= 40:
        rec.append("Тренд OK: YOLO в БД и треки в логах — держать текущие пороги, наблюдать ещё сутки.")

    if warnings.get("slow_frame_warnings", 0) > n * 2:
        rec.append(
            "Много Slow frame processing: при 7 FPS detect — убедиться intel:gpu для binary+classifier; "
            "снизить max_classifications_per_frame если CPU перегружен ReID."
        )
    if warnings.get("processor_api_400", 0) > 0:
        rec.append(
            "Ошибки POST /api/processor/videos 400 — разобрать дубликат payload / finalize; "
            "может мешать записи в БД."
        )
    if warnings.get("predict_fallback_hits", 0) > n * 3:
        rec.append(
            "Частый track→predict fallback: ByteTrack не даёт id — unstick уже включён; "
            "при необходимости снизить track_high_thresh в unstick YAML."
        )
    if container_uptime_note:
        rec.append(container_uptime_note)
    if not rec:
        rec.append("Аномалий по порогам не видно; продолжить мониторинг product_metrics.")
    return rec


def _write_report(
    out_dir: Path,
    *,
    started_at: str,
    ended_at: str,
    sessions: list[dict],
    samples: list[dict],
    providers: list[dict],
    videos_n: int,
    warnings: dict,
    meta: dict,
) -> None:
    agg = _summarize(sessions)
    recs = _recommendations(
        agg,
        providers,
        warnings,
        videos_n=videos_n,
        container_uptime_note=str(meta.get("container_uptime_note") or ""),
    )
    report = {
        "started_at": started_at,
        "ended_at": ended_at,
        "meta": meta,
        "sessions_aggregate": agg,
        "warnings": warnings,
        "providers_since_start": providers,
        "videos_since_start": videos_n,
        "recommendations": recs,
        "last_sessions": sessions[-8:],
        "probe_count": len(samples),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# YOLO observe 13h — {ended_at}",
        "",
        "## Сводка сессий (docker logs, dedup)",
        "",
        "```json",
        json.dumps(agg, ensure_ascii=False, indent=2),
        "```",
        "",
        "## БД с момента старта",
        "",
        f"- videos: **{videos_n}**",
        f"- providers: `{json.dumps(providers, ensure_ascii=False)}`",
        "",
        "## Сигналы в логах",
        "",
        "```json",
        json.dumps(warnings, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Рекомендации",
        "",
    ]
    for i, r in enumerate(recs, 1):
        lines.append(f"{i}. {r}")
    lines.append("")
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_loop(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = REPO / out_dir
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = REPO / db_path

    started_at = datetime.now(timezone.utc)
    started_sql = started_at.strftime("%Y-%m-%d %H:%M:%S")
    started_iso = started_at.isoformat()
    log_path = out_dir / "observe-13h.log"
    samples_path = out_dir / "samples.jsonl"
    meta_path = out_dir / "meta.json"

    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "started_at": started_iso,
        "duration_hours": args.duration_hours,
        "interval_sec": args.interval_sec,
        "container": args.container,
        "pid": None,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def log(msg: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts} {msg}\n"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="")

    log(f"START duration={args.duration_hours}h interval={args.interval_sec}s")

    seen: set[str] = set()
    all_sessions: list[dict] = []
    samples: list[dict] = []
    end_ts = time.time() + args.duration_hours * 3600
    probe_since = f"{max(5, args.interval_sec // 60 + 5)}m"
    container_restarts = 0
    last_uptime = ""

    while time.time() < end_ts:
        # container uptime hint
        try:
            r = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.StartedAt}}",
                    args.container,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            uptime = (r.stdout or "").strip()
            if last_uptime and uptime != last_uptime:
                container_restarts += 1
                log(f"WARN container restarted new_start={uptime}")
            last_uptime = uptime
        except Exception:
            pass

        log_text = _docker_logs(probe_since, container=args.container)
        batch = _parse_sessions(log_text)
        new_n = 0
        for s in batch:
            k = _session_key(s)
            if k in seen:
                continue
            seen.add(k)
            all_sessions.append(s)
            new_n += 1

        snap = _summarize(all_sessions)
        prov = _db_providers_since(db_path, started_sql)
        vids = _db_videos_since(db_path, started_sql)
        warn = _log_warnings(log_text)
        sample = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "new_sessions_this_probe": new_n,
            "aggregate": snap,
            "providers_since_start": prov,
            "videos_since_start": vids,
            "warnings_delta": warn,
        }
        samples.append(sample)
        with samples_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        log(
            f"probe sessions={snap.get('sessions')} new={new_n} "
            f"raw_boxes={snap.get('yolo_raw_boxes_total')} videos={vids}"
        )

        remaining = max(0.0, end_ts - time.time())
        if remaining <= 0:
            break
        time.sleep(min(float(args.interval_sec), remaining))

    ended_iso = datetime.now(timezone.utc).isoformat()
    full_log = _docker_logs(f"{int(args.duration_hours)}h", container=args.container)
    for s in _parse_sessions(full_log):
        k = _session_key(s)
        if k not in seen:
            seen.add(k)
            all_sessions.append(s)

    uptime_note = ""
    if container_restarts > 0:
        uptime_note = (
            f"За окно зафиксировано перезапусков контейнера: {container_restarts} — "
            "часть сессий могла выпасть из docker logs."
        )

    meta["ended_at"] = ended_iso
    meta["container_uptime_note"] = uptime_note
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    providers = _db_providers_since(db_path, started_sql)
    videos_n = _db_videos_since(db_path, started_sql)
    warnings = _log_warnings(full_log)
    _write_report(
        out_dir,
        started_at=started_iso,
        ended_at=ended_iso,
        sessions=all_sessions,
        samples=samples,
        providers=providers,
        videos_n=videos_n,
        warnings=warnings,
        meta=meta,
    )
    log(f"DONE report -> {out_dir / 'REPORT.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration-hours", type=float, default=13.0)
    ap.add_argument("--interval-sec", type=int, default=1800, help="probe every 30 min")
    ap.add_argument("--out-dir", default="tmp/observe-13h")
    ap.add_argument("--db", default="app/data/db/birdlense.db")
    ap.add_argument("--container", default="birdlense")
    args = ap.parse_args()
    return run_loop(args)


if __name__ == "__main__":
    sys.exit(main())
