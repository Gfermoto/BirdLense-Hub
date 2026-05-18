#!/usr/bin/env python3
"""Export Behavior v2 video profile to OpenVINO-ready artifact descriptor (#458)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video-export", required=True, help="behavior_video_export@v1 json")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--precision", choices=["fp16", "int8"], default="fp16")
    args = ap.parse_args()

    src = Path(args.video_export).expanduser().resolve()
    payload = json.loads(src.read_text(encoding="utf-8"))
    if str(payload.get("schema") or "") != "behavior_video_export@v1":
        raise SystemExit("invalid schema, expected behavior_video_export@v1")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    precision = str(args.precision).lower()
    model_version = str(payload.get("model_version") or "video-v1")
    descriptor = {
        "schema": "behavior_openvino_export@v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": model_version,
        "precision": precision,
        "source_export": str(src),
        "expected_files": {
            "xml": f"{model_version}.xml",
            "bin": f"{model_version}.bin",
        },
    }
    out = out_dir / f"behavior_openvino_export@{model_version}_{precision}.json"
    out.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "descriptor": str(out), "precision": precision}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
