#!/usr/bin/env python3
"""Export training data for fusion scorer.

The exporter prefers decision traces written by the processor into
`ActivityLog(type='decision_trace')`, because those rows preserve track-level
evidence, audio support/conflict, and accept/reject labels.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Iterable


def _maybe_reexec_with_project_venv() -> None:
    """Run under app/.venv when the caller used system Python."""
    project_root = Path(__file__).resolve().parents[1]
    venv_python = project_root / 'app' / '.venv' / 'bin' / 'python'
    if not venv_python.exists():
        return
    if getattr(sys, 'prefix', None) != getattr(sys, 'base_prefix', None):
        return
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


_maybe_reexec_with_project_venv()


DEFAULT_COLUMNS = [
    "detector_conf",
    "classifier_conf",
    "birdnet_prior",
    "key_frame_score",
    "key_frame_count",
    "multi_camera_count",
    "label",
    "valid_track_label",
    "species_top1_label",
    "accepted",
    "decision_kind",
    "trust_band",
    "reject_reason_code",
    "evidence_state",
    "audio_evidence",
    "audio_support_count",
    "audio_support_species",
    "audio_conflict_species",
    "audio_conflict_score",
    "classifier_vote_share",
    "track_id",
    "video_id",
    "species_name",
    "persisted_to_clip",
]


def _persisted_track_list(payload: dict) -> list:
    """Один список строк клипа: persisted_tracks или legacy accepted_tracks (не оба циклом)."""
    pt = payload.get("persisted_tracks")
    if pt is not None:
        return pt if isinstance(pt, list) else []
    at = payload.get("accepted_tracks")
    return at if isinstance(at, list) else []


def _normalize_trace_row(row: dict) -> dict:
    accepted = bool(row.get("accepted"))
    decision_kind = str(row.get("decision_kind") or ("accepted_species" if accepted else "rejected"))
    label = 1 if accepted else 0
    species_top1_label = 1 if accepted and decision_kind == "accepted_species" else 0
    return {
        "detector_conf": row.get("detector_conf") or row.get("detector_confidence") or row.get("confidence") or 0.0,
        "classifier_conf": row.get("classifier_conf") or row.get("classifier_confidence") or row.get("confidence") or 0.0,
        "birdnet_prior": row.get("birdnet_prior") or row.get("_birdnet_prior") or 0.0,
        "key_frame_score": row.get("key_frame_score") or row.get("best_frame_score") or 0.0,
        "key_frame_count": row.get("key_frame_count") or 0,
        "multi_camera_count": row.get("multi_camera_count") or row.get("_multi_camera_count") or 0,
        "label": label,
        "valid_track_label": label,
        "species_top1_label": species_top1_label,
        "accepted": accepted,
        "decision_kind": decision_kind,
        "trust_band": row.get("trust_band") or ("green" if accepted else "red"),
        "reject_reason_code": row.get("reject_reason_code") or "",
        "evidence_state": row.get("evidence_state") or "",
        "audio_evidence": row.get("audio_evidence") or "none",
        "audio_support_count": row.get("audio_support_count") or 0,
        "audio_support_species": row.get("audio_support_species") or "",
        "audio_conflict_species": row.get("audio_conflict_species") or "",
        "audio_conflict_score": row.get("audio_conflict_score") or 0.0,
        "classifier_vote_share": row.get("classifier_vote_share") or 0.0,
        "track_id": row.get("track_id") or 0,
        "video_id": row.get("video_id") or 0,
        "species_name": row.get("species_name") or row.get("species") or "",
        "persisted_to_clip": 1 if row.get("persisted_to_clip") else 0,
    }


def export_from_csv(src: Path, out: Path) -> None:
    # copy or normalize columns
    with src.open("r", encoding="utf-8") as fsrc, out.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fsrc)
        fieldnames = list(dict.fromkeys((reader.fieldnames or []) + DEFAULT_COLUMNS))
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            out_row = {k: row.get(k, 0) for k in fieldnames}
            if 'valid_track_label' not in row:
                out_row['valid_track_label'] = row.get('label', 0)
            if 'species_top1_label' not in row:
                out_row['species_top1_label'] = row.get('label', 0)
            writer.writerow(out_row)
    print(f"Wrote normalized CSV to {out}")


def export_from_db(out: Path) -> None:
    """Export calibration rows from decision traces, with a legacy fallback."""
    project_root = Path(__file__).resolve().parents[1]
    app_dir = project_root / "app"
    web_dir = app_dir / "web"
    for path in (str(app_dir), str(web_dir), str(project_root)):
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        from flask import Flask
        from web.models import ActivityLog, VideoSpecies, db  # type: ignore
    except Exception as e:
        print(
            "DB export failed: cannot import web app/models. "
            "Run this from the repo root with the web package available.",
            file=sys.stderr,
        )
        print("Error:", e, file=sys.stderr)
        sys.exit(2)

    app = Flask("fusion_export")
    app.config.from_object("config.Config")
    db.init_app(app)
    with app.app_context():
        with out.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=DEFAULT_COLUMNS)
            writer.writeheader()

            trace_rows = (
                db.session.query(ActivityLog)
                .filter(ActivityLog.type == "decision_trace")
                .order_by(ActivityLog.created_at.asc())
                .all()
            )
            if trace_rows:
                written = 0
                for trace in trace_rows:
                    try:
                        payload = json.loads(trace.data or "{}")
                    except (TypeError, ValueError):
                        continue
                    for row in _persisted_track_list(payload):
                        writer.writerow(_normalize_trace_row(row))
                        written += 1
                    for row in payload.get("rejected_tracks") or []:
                        writer.writerow(_normalize_trace_row(row))
                        written += 1
                print(f"Exported {written} decision-trace rows to {out}")
                return

            rows = (
                db.session.query(VideoSpecies)
                .filter(VideoSpecies.source == "video")
                .all()
            )
            if not rows:
                print(
                    "No rows found in ActivityLog or VideoSpecies. Nothing exported.",
                    file=sys.stderr,
                )
                sys.exit(3)

            written = 0
            for r in rows:
                extra = {}
                raw_extra = getattr(r, "extra", None)
                if raw_extra:
                    try:
                        extra = (
                            json.loads(raw_extra)
                            if isinstance(raw_extra, str)
                            else dict(raw_extra)
                        )
                    except Exception:
                        extra = {}
                writer.writerow(
                    _normalize_trace_row(
                        {
                            "accepted": getattr(r, "manually_corrected", False),
                            "decision_kind": (
                                "accepted_species"
                                if getattr(r, "manually_corrected", False)
                                else "accepted_generic"
                            ),
                            "species_name": getattr(
                                getattr(r, "species", None), "name", None
                            ),
                            "track_id": getattr(r, "track_id", None),
                            "video_id": getattr(r, "video_id", None),
                            "detector_confidence": (
                                extra.get("detector_confidence")
                                or getattr(r, "confidence", 0.0)
                            ),
                            "classifier_confidence": (
                                extra.get("classifier_confidence")
                                or getattr(r, "confidence", 0.0)
                            ),
                            "_birdnet_prior": extra.get("_birdnet_prior") or 0.0,
                            "best_frame_score": extra.get("best_frame_score") or 0.0,
                            "key_frame_count": extra.get("key_frame_count") or 0,
                            "_multi_camera_count": extra.get("_multi_camera_count")
                            or 0,
                        }
                    )
                )
                written += 1
            print(f"Exported {written} fallback rows to {out}")


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", "-o", type=Path, required=True, help="Output CSV path")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--source-csv", type=Path, help="Normalize existing CSV of features")
    grp.add_argument("--source", choices=["db"], help="Source 'db' to try export from DB")
    args = p.parse_args(list(argv) if argv else None)

    out = args.out
    if args.source_csv:
        export_from_csv(args.source_csv, out)
        return 0
    if args.source == "db":
        export_from_db(out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

