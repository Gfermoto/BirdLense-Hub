"""API payload for bbox parity / geometry diagnostics (SOTA-06)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from services.system_config_audit_service import _load_processor_runtime_snapshot


def _parity_root() -> Path:
    data = (os.environ.get("DATA_DIR") or "data").strip() or "data"
    return Path(data) / "diagnostics" / "bbox_parity"


def build_bbox_parity_debug_payload(*, session_id: str | None = None) -> dict[str, Any]:
    snap = _load_processor_runtime_snapshot() or {}
    gauges = snap.get("gauges") if isinstance(snap.get("gauges"), dict) else {}
    counters = snap.get("counters") if isinstance(snap.get("counters"), dict) else {}

    sessions: list[dict[str, Any]] = []
    root = _parity_root()
    if root.is_dir():
        for child in sorted(root.iterdir())[:50]:
            if not child.is_dir():
                continue
            if session_id and child.name != session_id.replace("/", "_")[:64]:
                continue
            frames = sorted(child.glob("frame_*.jpg"))
            meta_files = sorted(child.glob("frame_*.json"))
            sessions.append(
                {
                    "session_id": child.name,
                    "frame_count": len(frames),
                    "latest_meta": json.loads(meta_files[-1].read_text(encoding="utf-8")) if meta_files else None,
                }
            )

    return {
        "processor_gauges": {
            "bbox_parity_roundtrip_iou_p50": gauges.get("bbox_parity_roundtrip_iou_p50"),
        },
        "processor_counters": {
            "bbox_iou_gate_rejected_total": counters.get("bbox_iou_gate_rejected_total"),
        },
        "parity_sessions": sessions,
        "parity_root": str(root),
        "docs": "docs/ru/detection-geometry.ru.md",
    }
