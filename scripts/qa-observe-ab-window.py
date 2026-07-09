#!/usr/bin/env python3
"""A/B QA observer: domain-health, SLI, 30m species slice (VPS)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Observe BirdLense A/B window on deploy target")
    ap.add_argument("--window", required=True, help="Label, e.g. windowA or windowB")
    ap.add_argument("--duration-sec", type=int, default=43200, help="Total run (default 12h)")
    ap.add_argument("--interval-sec", type=int, default=600, help="Probe interval (default 10m)")
    ap.add_argument("--out-dir", default="tmp/qa-observe")
    args = ap.parse_args()

    base = _env("DEPLOY_URL", "https://birdlense.eyera.info").rstrip("/")
    token = _env("MCP_TOKEN")
    host = _env("DEPLOY_HOST", "root@185.218.111.196")
    port = _env("DEPLOY_SSH_PORT", "2222")
    rdir = _env("DEPLOY_REMOTE_DIR", "/root/BirdLense")
    repo = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    tag = args.window
    out = out_dir / f"overnight_qa_{tag}.jsonl"
    summary = out_dir / f"overnight_qa_{tag}_summary.md"

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def api(path: str) -> dict:
        req = urllib.request.Request(base + path, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    def db_probe() -> dict:
        script = (
            "python3 - <<'PY2'\n"
            "import sqlite3, json\n"
            f"con=sqlite3.connect('{rdir}/app/data/db/birdlense.db')\n"
            "con.row_factory=sqlite3.Row\n"
            "q='''SELECT s.name as species_name, COUNT(*) as n, "
            "SUM(CASE WHEN vs.classifier_needs_review=1 THEN 1 ELSE 0 END) as review_n "
            "FROM video_species vs JOIN species s ON s.id=vs.species_id "
            "JOIN video v ON v.id=vs.video_id "
            "WHERE v.created_at >= datetime('now','-30 minutes') "
            "GROUP BY s.name ORDER BY n DESC LIMIT 8'''\n"
            "rows=[dict(r) for r in con.execute(q).fetchall()]\n"
            "print(json.dumps(rows, ensure_ascii=False))\n"
            "PY2"
        )
        r = subprocess.run(
            ["ssh", "-p", str(port), host, script],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if r.returncode != 0:
            return {"error": (r.stderr or r.stdout).strip()[:400]}
        try:
            return {"rows": json.loads((r.stdout or "[]").strip() or "[]")}
        except Exception as e:
            return {"error": f"parse:{e} raw={(r.stdout or '')[:200]}"}

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
            timeout=60,
            env=env,
            cwd=str(repo),
        )
        return {"ok": r.returncode == 0, "out": (r.stdout + r.stderr).strip()[-500:]}

    summary.write_text(f"# QA {tag}\n\n", encoding="utf-8")
    end_ts = time.time() + args.duration_sec
    while time.time() < end_ts:
        ts = datetime.now(timezone.utc).isoformat()
        rec: dict = {"ts_utc": ts, "window": tag}
        try:
            dh = api("/api/ui/system/domain-health")
            m = dh.get("metrics") or {}
            s = dh.get("samples") or {}
            rec["parity_mismatch_rate_24h"] = m.get("parity_mismatch_rate_24h")
            rec["parity_hotspot_count_24h"] = m.get("parity_hotspot_count_24h")
            rec["top_reasons"] = s.get("parity_top_mismatch_reasons_24h")
        except Exception as e:
            rec["domain_health_error"] = str(e)
        try:
            rec["status_components"] = api("/api/ui/status")
        except Exception as e:
            rec["status_error"] = str(e)
        rec["sli"] = sli_probe()
        rec["db_30m"] = db_probe()
        alert: list[str] = []
        if isinstance(rec.get("parity_hotspot_count_24h"), (int, float)) and rec["parity_hotspot_count_24h"] > 0:
            alert.append("hotspot>0")
        if isinstance(rec.get("parity_mismatch_rate_24h"), (int, float)) and rec["parity_mismatch_rate_24h"] > 0.25:
            alert.append("mismatch>0.25")
        rows = (rec.get("db_30m") or {}).get("rows") or []
        jac = next((r for r in rows if str(r.get("species_name")) == "JACOBIN PIGEON"), None)
        if jac and int(jac.get("n") or 0) >= 3:
            alert.append("jacobin_spike_30m")
        if not rec.get("sli", {}).get("ok", False):
            alert.append("runtime_sli_fail")
        rec["alerts"] = alert
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        line = (
            f"- {ts}: mismatch={rec.get('parity_mismatch_rate_24h')} "
            f"hotspot={rec.get('parity_hotspot_count_24h')} "
            f"alerts={','.join(alert) if alert else 'none'}\n"
        )
        with summary.open("a", encoding="utf-8") as f:
            f.write(line)
        time.sleep(args.interval_sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
