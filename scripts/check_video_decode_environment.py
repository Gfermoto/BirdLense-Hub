#!/usr/bin/env python3
"""Preflight checks for video decode / HW paths (#373): /dev/dri, optional vainfo.

Does not modify config. Prints JSON for scripts and humans.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def _stat_dev_dri() -> dict:
    out = {"path": "/dev/dri", "exists": os.path.isdir("/dev/dri")}
    if not out["exists"]:
        return out
    nodes = []
    try:
        for name in sorted(os.listdir("/dev/dri")):
            p = os.path.join("/dev/dri", name)
            if os.path.exists(p):
                nodes.append(name)
    except OSError:
        nodes = []
    out["nodes"] = nodes
    return out


def main() -> int:
    vainfo_path = shutil.which("vainfo")
    vainfo_ok = False
    vainfo_stderr = ""
    if vainfo_path and os.path.isdir("/dev/dri"):
        try:
            r = subprocess.run(
                [vainfo_path],
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, "LIBVA_DRIVER_NAME": os.environ.get("LIBVA_DRIVER_NAME", "")},
            )
            vainfo_ok = r.returncode == 0
            vainfo_stderr = (r.stderr or r.stdout or "")[:2000]
        except (OSError, subprocess.TimeoutExpired) as e:
            vainfo_stderr = str(e)

    payload = {
        "schema": "video_decode_environment_check@v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dev_dri": _stat_dev_dri(),
        "vainfo": {
            "binary": vainfo_path,
            "ran_ok": vainfo_ok,
            "stderr_tail": vainfo_stderr[-800:] if vainfo_stderr else "",
        },
        "hints": [
            "BirdLense default_config: video.encoding is usually cpu; intel VA-API requires encoding: intel and /dev/dri in container.",
            "See docs/CV_ML_DECODE.md for benchmark matrix.",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
