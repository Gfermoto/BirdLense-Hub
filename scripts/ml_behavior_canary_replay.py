#!/usr/bin/env python3
"""Replay canary: meta_v1 vs video model on historical Hub DB tracklets."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "app"))
sys.path.insert(0, str(_REPO_ROOT / "processor" / "src"))


def _load_cfg_yaml(cfg_dir: Path) -> dict[str, Any]:
    import yaml

    d: dict[str, Any] = {}
    for name in ("default_config.yaml", "user_config.yaml"):
        p = cfg_dir / name
        if p.is_file():
            part = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

            def merge(a: dict, b: dict) -> None:
                for k, v in b.items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        merge(a[k], v)
                    else:
                        a[k] = v

            merge(d, part)
    return d


class AppConfig:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        cur: Any = self._data
        for part in key.split("."):
            if not isinstance(cur, dict):
                return default
            cur = cur.get(part)
            if cur is None:
                return default
        return cur


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--config-dir", default="/app/app_config")
    ap.add_argument("--processor-cwd", default="/app/processor")
    ap.add_argument("--video-export", help="Override video export JSON for v2")
    ap.add_argument("--since-video-id", type=int, default=0)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import yaml  # noqa: F401

    from behavior_baseline_runtime import maybe_predict_video_behavior
    from behavior_video_runtime import maybe_predict_video_behavior_video

    cfg = _load_cfg_yaml(Path(args.config_dir))
    app = AppConfig(cfg)
    if args.video_export:
        br = cfg.setdefault("processor", {}).setdefault("behavior_recognition", {})
        br["video_weights_path"] = str(Path(args.video_export).resolve())
        ov_dir = Path(args.video_export).parent
        br["video_openvino_path"] = str(ov_dir)
        br["enabled"] = True

    conn = sqlite3.connect(str(Path(args.db)))
    conn.row_factory = sqlite3.Row
    q = """
        SELECT id, video_path FROM video
        WHERE deleted_at IS NULL AND id > ?
        ORDER BY id DESC LIMIT ?
    """
    videos = conn.execute(q, (int(args.since_video_id), int(args.limit))).fetchall()

    n = 0
    disc = 0
    agree = 0
    rows_out: list[dict[str, Any]] = []

    for v in videos:
        vid = int(v["id"])
        vpath = v["video_path"]
        dets = []
        for (fr_raw,) in conn.execute(
            "SELECT frames FROM video_species WHERE video_id=? AND frames IS NOT NULL",
            (vid,),
        ):
            try:
                fr = json.loads(fr_raw)
            except json.JSONDecodeError:
                continue
            if isinstance(fr, list) and len(fr) >= 3:
                dets.append({"frames": fr})
        if not dets:
            continue
        meta_lab, meta_conf = maybe_predict_video_behavior(
            app, dets, duration_s=30.0, processor_cwd=str(args.processor_cwd)
        )
        vid_lab, vid_conf, _, _ = maybe_predict_video_behavior_video(
            app, dets, duration_s=30.0, processor_cwd=str(args.processor_cwd), video_path=vpath
        )
        n += 1
        is_disc = bool(meta_lab and vid_lab and str(meta_lab).lower() != str(vid_lab).lower())
        if is_disc:
            disc += 1
        else:
            agree += 1
        rows_out.append(
            {
                "video_id": vid,
                "meta_label": meta_lab,
                "meta_confidence": meta_conf,
                "video_label": vid_lab,
                "video_confidence": vid_conf,
                "discrepancy": is_disc,
            }
        )

    rate = (disc / n) if n else 0.0
    report = {
        "schema": "behavior_canary_replay@v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_videos": n,
        "discrepancies": disc,
        "agreements": agree,
        "discrepancy_rate": round(rate, 4),
        "label_pairs": dict(Counter((r["meta_label"], r["video_label"]) for r in rows_out if r["discrepancy"])),
        "samples": rows_out[:50],
    }
    outp = Path(args.out).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(outp), "discrepancy_rate": report["discrepancy_rate"], "n": n}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
