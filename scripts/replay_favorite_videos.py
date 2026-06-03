#!/usr/bin/env python3
"""Batch replay favorite mp4 on VPS via processor main.py (#599).

Fetches active favorite Video rows from prod DB, runs processor per clip,
collects recording_session_summary metrics from activity_log.

Requires: scripts/deploy.local.sh or DEPLOY_HOST, DEPLOY_URL, DEPLOY_SSH_PORT.
Remote mutation: BIRDLENSE_ALLOW_REMOTE_MUTATION=1
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _load_deploy_local() -> None:
    local = REPO / "scripts" / "deploy.local.sh"
    if not local.is_file():
        return
    res = subprocess.run(
        ["bash", "-lc", f"source {shlex.quote(str(local))} && env"],
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


def _ssh(host: str, port: str, cmd: str, *, timeout: int = 3600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-p", port, "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=60", host, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _json_from_stdout(stdout: str) -> Any:
    text = (stdout or "").strip()
    if not text:
        raise RuntimeError("empty stdout")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        idx = 0
        last: Any | None = None
        while idx < len(text):
            if text[idx] not in "{[":
                idx += 1
                continue
            try:
                obj, end = decoder.raw_decode(text, idx)
            except json.JSONDecodeError:
                idx += 1
                continue
            last = obj
            idx = max(end, idx + 1)
        if last is not None:
            return last
        raise


@dataclass
class FavoriteRow:
    video_id: int
    video_path: str


def _container_path(video_path: str) -> str:
    p = (video_path or "").strip().replace("\\", "/")
    if p.startswith("/app/"):
        return p
    if p.startswith("data/"):
        return f"/app/{p}"
    return f"/app/data/recordings/{p.split('recordings/', 1)[-1]}"


def _load_favorites(*, host: str, port: str, remote_db: str, video_ids: list[int], timeout: int) -> list[FavoriteRow]:
    id_filter = ""
    if video_ids:
        ids_sql = ",".join(str(int(i)) for i in video_ids)
        id_filter = f" AND v.id IN ({ids_sql})"
    sql_py = (
        "python3 - <<'PY'\n"
        "import sqlite3, json\n"
        f"con=sqlite3.connect({remote_db!r})\n"
        "con.row_factory=sqlite3.Row\n"
        "sql='''\n"
        "SELECT v.id AS video_id, v.video_path\n"
        "FROM video v\n"
        "WHERE v.deleted_at IS NULL AND v.favorite=1\n"
        f"  {id_filter.strip()}\n"
        "ORDER BY v.id\n"
        "'''\n"
        "rows=con.execute(sql).fetchall()\n"
        "print(json.dumps([dict(r) for r in rows], ensure_ascii=False))\n"
        "PY"
    )
    res = _ssh(host, port, sql_py, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"favorites query failed: {res.stderr or res.stdout}")
    payload = _json_from_stdout(res.stdout)
    return [
        FavoriteRow(video_id=int(r["video_id"]), video_path=str(r.get("video_path") or ""))
        for r in payload
    ]


def _run_processor(
    *,
    host: str,
    port: str,
    container: str,
    container_video: str,
    timeout: int,
) -> tuple[int, str, str]:
    cmd = (
        f"docker exec -e PYTHONPATH=/app "
        f"-e MQTT_CLIENT_ID=birdlense_replay_favorites "
        f"{shlex.quote(container)} "
        f"python /app/processor/src/main.py {shlex.quote(container_video)} --fake-motion true"
    )
    res = _ssh(host, port, cmd, timeout=timeout)
    return res.returncode, res.stdout or "", res.stderr or ""


def _fetch_latest_summary(
    *,
    host: str,
    port: str,
    remote_db: str,
    after_iso: str,
    timeout: int,
) -> dict[str, Any] | None:
    sql_py = (
        "python3 - <<'PY'\n"
        "import sqlite3, json\n"
        f"con=sqlite3.connect({remote_db!r})\n"
        "row=con.execute(\n"
        "  \"\"\"SELECT data, created_at FROM activity_log\n"
        "     WHERE type='recording_session_summary'\n"
        "       AND created_at >= ?\n"
        "     ORDER BY id DESC LIMIT 1\"\"\",\n"
        f"  ({after_iso!r},),\n"
        ").fetchone()\n"
        "if not row:\n"
        "  print('null')\n"
        "else:\n"
        "  try:\n"
        "    payload=json.loads(row[0] or '{}')\n"
        "  except Exception:\n"
        "    payload={}\n"
        "  print(json.dumps({'created_at': row[1], 'payload': payload}, ensure_ascii=False))\n"
        "PY"
    )
    res = _ssh(host, port, sql_py, timeout=min(timeout, 120))
    if res.returncode != 0:
        return None
    text = (res.stdout or "").strip()
    if text == "null" or not text:
        return None
    try:
        return _json_from_stdout(text)
    except Exception:
        return None


def main() -> int:
    _load_deploy_local()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=_env("DEPLOY_HOST", "birdlense"))
    ap.add_argument("--port", default=_env("DEPLOY_SSH_PORT", "22"))
    ap.add_argument("--container", default=_env("REPLAY_CONTAINER", "birdlense"))
    ap.add_argument(
        "--remote-db",
        default=_env("REPLAY_REMOTE_DB", "/root/BirdLense/app/data/db/birdlense.db"),
    )
    ap.add_argument("--video-id", action="append", type=int, default=[], help="Limit to video id(s)")
    ap.add_argument("--timeout-sec", type=int, default=900)
    ap.add_argument(
        "--json-out",
        default=str(REPO / ".artifacts" / "replay-favorites" / "replay_favorites_latest.json"),
    )
    args = ap.parse_args()

    host = args.host
    if host not in ("localhost", "127.0.0.1") and _env("BIRDLENSE_ALLOW_REMOTE_MUTATION") != "1":
        print(
            "Refusing remote replay without BIRDLENSE_ALLOW_REMOTE_MUTATION=1",
            file=sys.stderr,
        )
        return 2

    favorites = _load_favorites(
        host=host,
        port=args.port,
        remote_db=args.remote_db,
        video_ids=args.video_id,
        timeout=120,
    )
    if not favorites:
        print(json.dumps({"error": "no_favorite_videos", "host": host}))
        return 1

    results: list[dict[str, Any]] = []
    failures = 0
    for row in favorites:
        run_started = datetime.now(timezone.utc).isoformat()
        cpath = _container_path(row.video_path)
        entry: dict[str, Any] = {
            "video_id": row.video_id,
            "video_path": row.video_path,
            "container_path": cpath,
        }
        try:
            rc, out, err = _run_processor(
                host=host,
                port=args.port,
                container=args.container,
                container_video=cpath,
                timeout=args.timeout_sec,
            )
            entry["processor_exit_code"] = rc
            if rc != 0:
                entry["error"] = (err or out)[-2000:]
                failures += 1
            summary = _fetch_latest_summary(
                host=host,
                port=args.port,
                remote_db=args.remote_db,
                after_iso=run_started,
                timeout=120,
            )
            if summary:
                payload = summary.get("payload") or {}
                entry["summary"] = {
                    "created_at": summary.get("created_at"),
                    "yolo_frames_with_tracks": payload.get("yolo_frames_with_tracks"),
                    "persist_duration_ms": payload.get("persist_duration_ms"),
                    "finalize_duration_ms": payload.get("finalize_duration_ms"),
                    "tracks_coverage": payload.get("tracks_coverage"),
                }
                persist_ms = payload.get("persist_duration_ms")
                if persist_ms is not None and float(persist_ms) > 6000:
                    entry["persist_warn"] = True
            else:
                entry["summary"] = None
        except Exception as exc:
            entry["error"] = str(exc)
            failures += 1
        results.append(entry)

    report = {
        "report_format": "replay_favorites@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "videos_total": len(favorites),
        "videos_failed": failures,
        "videos_ok": len(favorites) - failures,
        "videos": results,
    }
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
