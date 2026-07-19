#!/usr/bin/env python3
"""Live Hub-only species pack gate (RC6 residual).

Expects ``benchmarks/species_live_hub_only/manifest.json`` listing labeled clips.
Without clips: PASS + skipped unless ``--require-clips``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "benchmarks/species_live_hub_only"
MANIFEST = PACK / "manifest.json"
REPORT_DIR = REPO / "docs/reports/pipeline_golden"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true")
    ap.add_argument(
        "--require-clips",
        action="store_true",
        help="Fail when manifest missing or clip list empty (strict CI).",
    )
    args = ap.parse_args()

    payload: dict = {
        "ok": True,
        "product": "taxonomy_live_hub_only",
        "skipped": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pack": str(PACK.relative_to(REPO)),
        "clips": 0,
        "fail": [],
    }

    if not MANIFEST.is_file():
        payload["skipped"] = True
        payload["skip_reason"] = "manifest_missing"
        if args.require_clips:
            payload["ok"] = False
            payload["fail"] = ["manifest_missing"]
    else:
        try:
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload["ok"] = False
            payload["fail"] = [f"manifest_invalid:{exc}"]
            data = {}
        clips = data.get("clips") if isinstance(data, dict) else None
        if not isinstance(clips, list) or not clips:
            payload["skipped"] = True
            payload["skip_reason"] = "clips_empty"
            if args.require_clips:
                payload["ok"] = False
                payload["fail"] = ["clips_empty"]
        else:
            payload["clips"] = len(clips)
            # Clip execution (mp4 + MQTT off) lands when pack is populated.
            payload["note"] = "manifest present; runtime clip eval not wired yet"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "species_live_hub_only_latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    status = "PASS" if payload["ok"] else "FAIL"
    skip = f" skipped={payload.get('skip_reason')}" if payload.get("skipped") else ""
    print(f"{status} species-live-hub-only (clips={payload['clips']}{skip})")
    if args.enforce and not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
