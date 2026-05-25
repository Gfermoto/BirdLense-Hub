"""Per-frame Black Box decision trace (SOTA 2.0)."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_session_writer: FrameDecisionTraceWriter | None = None


@dataclass
class FrameDecisionRecord:
    frame_id: int
    track_id: int
    raw_conf: float
    motion_score: float
    bg_score: float
    shape_score: float
    final_score: float
    final_decision: str
    decision_source: str | None = None
    reject_reason: str | None = None
    reason_code: str | None = None
    box_area_norm: float | None = None
    low_threshold: float | None = None
    high_threshold: float | None = None
    calibrated: bool | None = None
    calibration_frame_count: int | None = None
    weighted_score: float | None = None
    frigate_boost: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrameDecisionTraceWriter:
    """Append-only JSONL per recording session."""

    def __init__(self, path: Path, *, session_key: str) -> None:
        self.path = path
        self.session_key = session_key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")
        meta = {
            "event": "session_start",
            "session_key": session_key,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._fh.write(json.dumps(meta, ensure_ascii=False) + "\n")
        self._fh.flush()

    def write(self, record: FrameDecisionRecord | dict[str, Any]) -> None:
        payload = (
            record.to_dict()
            if isinstance(record, FrameDecisionRecord)
            else dict(record)
        )
        payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with _lock:
            self._fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._fh.flush()

    def close(self) -> None:
        with _lock:
            try:
                self._fh.write(
                    json.dumps(
                        {"event": "session_end", "session_key": self.session_key},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                self._fh.flush()
                self._fh.close()
            except OSError:
                logger.debug("frame trace close failed", exc_info=True)


def set_session_trace_writer(writer: FrameDecisionTraceWriter | None) -> None:
    global _session_writer
    with _lock:
        _session_writer = writer


def get_session_trace_writer() -> FrameDecisionTraceWriter | None:
    return _session_writer


def log_frame_decisions(
    decisions: list[dict[str, Any]],
    *,
    frame_index: int,
) -> None:
    writer = _session_writer
    if writer is None or not decisions:
        return
    for d in decisions:
        rec = FrameDecisionRecord(
            frame_id=frame_index,
            track_id=int(d.get("track_id") or 0),
            raw_conf=float(d.get("raw_conf") or 0.0),
            motion_score=float(d.get("motion_score") or 0.0),
            bg_score=float(d.get("bg_score") or 0.0),
            shape_score=float(d.get("shape_score") or 0.0),
            final_score=float(d.get("final_score") or 0.0),
            final_decision=str(d.get("final_decision") or ""),
            decision_source=d.get("decision_source"),
            reject_reason=d.get("reject_reason"),
            reason_code=d.get("reason_code"),
            box_area_norm=d.get("box_area_norm"),
            low_threshold=d.get("low_threshold"),
            high_threshold=d.get("high_threshold"),
            calibrated=d.get("calibrated"),
            calibration_frame_count=d.get("calibration_frame_count"),
            weighted_score=d.get("weighted_score"),
            frigate_boost=d.get("frigate_boost"),
        )
        writer.write(rec)


def open_session_trace(
    processor_data_dir: Path,
    *,
    session_key: str,
    camera_id: str | None = None,
) -> FrameDecisionTraceWriter:
    """Create JSONL under data/decision_traces/."""
    day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    safe_cam = (camera_id or "unknown").replace("/", "_")
    fname = f"{session_key}_{safe_cam}.jsonl"
    path = processor_data_dir / "decision_traces" / day / fname
    return FrameDecisionTraceWriter(path, session_key=session_key)
