#!/usr/bin/env python3
"""Backfill: strip sticky/review-only bbox frames already stored in VideoSpecies.frames."""

from __future__ import annotations

import argparse
import json
import os
import sys

_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
_WEB_ROOT = os.path.join(_APP_ROOT, "web")
_PROCESSOR_SRC = os.path.join(_APP_ROOT, "processor", "src")
for p in (_WEB_ROOT, _APP_ROOT, _PROCESSOR_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)


def _parse_frames(raw: str | None) -> list[dict]:
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _should_clear(
    *,
    frames: list[dict],
    start_time: float,
    end_time: float,
    classifier_needs_review: bool,
    species_visit_id: int | None,
    strip_review: bool,
    cfg,
) -> str | None:
    from track_geometry import static_pinned_track_reason

    if strip_review and classifier_needs_review and species_visit_id is None and frames:
        return "review_only_no_overlay"
    if frames and cfg.enabled:
        pseudo = {"start_time": start_time, "end_time": end_time, "frames": frames}
        reason = static_pinned_track_reason(pseudo, cfg)
        if reason:
            return reason
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--video-id", type=int, default=None, help="Only this video_id")
    parser.add_argument("--limit", type=int, default=50000)
    args = parser.parse_args()

    from app import create_app
    from app_config.app_config import app_config
    from models import VideoSpecies, db
    from track_geometry import StaticPinnedTrackConfig

    app = create_app()
    with app.app_context():
        cfg = StaticPinnedTrackConfig.from_runtime_cfg(app_config.config or {})
        strip_review = bool(app_config.get("detection.strip_review_only_overlay_frames", True))
        q = VideoSpecies.query.filter(
            VideoSpecies.frames.isnot(None),
            VideoSpecies.frames != "",
            VideoSpecies.frames != "[]",
        )
        if args.video_id is not None:
            q = q.filter(VideoSpecies.video_id == int(args.video_id))
        rows = q.limit(max(1, int(args.limit))).all()

        cleared = 0
        for vs in rows:
            frames = _parse_frames(vs.frames)
            if not frames:
                continue
            reason = _should_clear(
                frames=frames,
                start_time=float(vs.start_time or 0),
                end_time=float(vs.end_time or 0),
                classifier_needs_review=bool(vs.classifier_needs_review),
                species_visit_id=vs.species_visit_id,
                strip_review=strip_review,
                cfg=cfg,
            )
            if not reason:
                continue
            cleared += 1
            print(
                f"clear video_id={vs.video_id} vs_id={vs.id} frames={len(frames)} reason={reason}"
            )
            if not args.dry_run:
                vs.frames = json.dumps([])

        if not args.dry_run and cleared:
            db.session.commit()
        print(json.dumps({"scanned": len(rows), "cleared": cleared, "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
