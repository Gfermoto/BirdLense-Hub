#!/usr/bin/env python3
"""Build Golden Dataset from hard cases and operator corrections."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class GoldenCase:
    case_id: str
    case_type: str
    created_at: str
    camera_id: str | None
    video_id: int | None
    video_path: str | None
    crop_path: str | None
    predicted_species: str | None
    ground_truth_species: str | None
    confidence: float | None
    source_ref: str

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "created_at": self.created_at,
            "camera_id": self.camera_id,
            "video_id": self.video_id,
            "video_path": self.video_path,
            "crop_path": self.crop_path,
            "predicted_species": self.predicted_species,
            "ground_truth_species": self.ground_truth_species,
            "confidence": self.confidence,
            "source_ref": self.source_ref,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="app/data/db/birdlense.db")
    p.add_argument("--data-dir", default="app/data")
    p.add_argument("--output-dir", default="app/data/datasets/golden_v1")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--limit", type=int, default=4000)
    p.add_argument("--seed-active-buffer", action="store_true", default=True)
    p.add_argument("--no-seed-active-buffer", dest="seed_active_buffer", action="store_false")
    return p.parse_args()


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _recent_cutoff(days: int) -> str:
    ts = _utc_now() - timedelta(days=max(1, days))
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(v) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_case_id(prefix: str, raw: str) -> str:
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def _as_posix(path: str | None) -> str | None:
    if not path:
        return None
    return str(path).replace("\\", "/")


def _pick_video_for_time(con: sqlite3.Connection, created_at: str, camera_id: str | None) -> sqlite3.Row | None:
    q = """
    SELECT v.id, v.video_path, v.start_time
    FROM video v
    WHERE datetime(v.start_time) <= datetime(?)
      AND datetime(v.start_time) >= datetime(?, '-10 minutes')
      AND v.deleted_at IS NULL
    ORDER BY datetime(v.start_time) DESC
    LIMIT 1
    """
    row = con.execute(q, (created_at, created_at)).fetchone()
    if row:
        return row
    # Fallback when timestamps are inconsistent.
    return con.execute(
        "SELECT id, video_path, start_time FROM video WHERE deleted_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()


def _mine_frigate_only_cases(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenCase]:
    q = """
    SELECT id, created_at, camera_id, yolo_raw_boxes_total, session_extended_by_frigate_only, payload_json
    FROM session_runtime_metrics
    WHERE datetime(created_at) >= datetime(?)
      AND session_extended_by_frigate_only > 0
      AND yolo_raw_boxes_total = 0
    ORDER BY datetime(created_at) DESC
    LIMIT ?
    """
    out: list[GoldenCase] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        video = _pick_video_for_time(con, str(row["created_at"]), row["camera_id"])
        src_ref = f"session_runtime_metrics:{row['id']}"
        case_id = _to_case_id("frigate-only", src_ref)
        out.append(
            GoldenCase(
                case_id=case_id,
                case_type="frigate_only_yolo_silent",
                created_at=str(row["created_at"]),
                camera_id=row["camera_id"],
                video_id=int(video["id"]) if video else None,
                video_path=_as_posix(video["video_path"]) if video else None,
                crop_path=None,
                predicted_species=None,
                ground_truth_species=None,
                confidence=None,
                source_ref=src_ref,
            )
        )
    return out


def _mine_low_conf_cases(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenCase]:
    q = """
    SELECT vs.id, vs.created_at, vs.video_id, vs.confidence, s.name AS species_name, v.video_path
    FROM video_species vs
    JOIN species s ON s.id = vs.species_id
    JOIN video v ON v.id = vs.video_id
    WHERE datetime(vs.created_at) >= datetime(?)
      AND vs.source = 'video'
      AND vs.confidence IS NOT NULL
      AND vs.confidence < 0.5
      AND v.deleted_at IS NULL
    ORDER BY datetime(vs.created_at) DESC
    LIMIT ?
    """
    out: list[GoldenCase] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        src_ref = f"video_species:{row['id']}"
        case_id = _to_case_id("lowconf", src_ref)
        out.append(
            GoldenCase(
                case_id=case_id,
                case_type="low_confidence_detection",
                created_at=str(row["created_at"]),
                camera_id=None,
                video_id=int(row["video_id"]),
                video_path=_as_posix(row["video_path"]),
                crop_path=None,
                predicted_species=row["species_name"],
                ground_truth_species=None,
                confidence=_safe_float(row["confidence"]),
                source_ref=src_ref,
            )
        )
    return out


def _mine_operator_corrections(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenCase]:
    q = """
    SELECT d.id, d.created_at, d.video_id, d.camera, d.from_species_name, d.to_species_name,
           d.confidence, d.crop_path, v.video_path
    FROM detection_feedback_event d
    LEFT JOIN video v ON v.id = d.video_id
    WHERE datetime(d.created_at) >= datetime(?)
      AND d.action IN ('relabel', 'delete_as_background')
    ORDER BY datetime(d.created_at) DESC
    LIMIT ?
    """
    out: list[GoldenCase] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        src_ref = f"detection_feedback_event:{row['id']}"
        case_id = _to_case_id("correction", src_ref)
        out.append(
            GoldenCase(
                case_id=case_id,
                case_type="operator_correction",
                created_at=str(row["created_at"]),
                camera_id=row["camera"],
                video_id=int(row["video_id"]) if row["video_id"] is not None else None,
                video_path=_as_posix(row["video_path"]),
                crop_path=_as_posix(row["crop_path"]),
                predicted_species=row["from_species_name"],
                ground_truth_species=row["to_species_name"],
                confidence=_safe_float(row["confidence"]),
                source_ref=src_ref,
            )
        )
    return out


def _dedupe(cases: list[GoldenCase]) -> list[GoldenCase]:
    seen: set[str] = set()
    out: list[GoldenCase] = []
    for c in cases:
        if c.case_id in seen:
            continue
        seen.add(c.case_id)
        out.append(c)
    return out


def _copy_or_link_evidence(case: GoldenCase, data_dir: Path, dst_root: Path) -> dict[str, str | None]:
    case_dir = dst_root / "samples" / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    copied_crop = None
    linked_video = None
    if case.crop_path:
        src = data_dir / case.crop_path.lstrip("/")
        if src.exists() and src.is_file():
            ext = src.suffix or ".jpg"
            dst = case_dir / f"crop{ext}"
            shutil.copy2(src, dst)
            copied_crop = str(dst.relative_to(dst_root))
    if case.video_path:
        src = data_dir / case.video_path.lstrip("/")
        if src.exists() and src.is_file():
            dst = case_dir / f"video{src.suffix or '.mp4'}"
            try:
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                os.symlink(src, dst)
                linked_video = str(dst.relative_to(dst_root))
            except OSError:
                # If symlink is not possible, copy small clips only.
                if src.stat().st_size <= 120 * 1024 * 1024:
                    shutil.copy2(src, dst)
                    linked_video = str(dst.relative_to(dst_root))
    return {"crop_asset": copied_crop, "video_asset": linked_video}


def _split_train_test(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    train: list[dict] = []
    test: list[dict] = []
    for c in cases:
        gt = (c.get("ground_truth_species") or "").strip()
        pred = (c.get("predicted_species") or "").strip()
        if not gt or not pred:
            train.append(c)
            continue
        h = int(hashlib.sha1(c["case_id"].encode("utf-8")).hexdigest()[:8], 16)
        if h % 10 < 8:
            train.append(c)
        else:
            test.append(c)
    return train, test


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _seed_active_buffer(con: sqlite3.Connection, rows: list[dict]) -> int:
    # Same schema as SessionStateRepository active_learning_buffer.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS active_learning_buffer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            camera_id TEXT,
            reason_code TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            status TEXT NOT NULL DEFAULT 'pending',
            payload_json TEXT
        )
        """
    )
    added = 0
    now = _utc_now().isoformat()
    for row in rows:
        reason = str(row.get("case_type") or "golden_case")
        payload = {"golden_case_id": row.get("case_id"), "source_ref": row.get("source_ref")}
        con.execute(
            """
            INSERT INTO active_learning_buffer(created_at, camera_id, reason_code, severity, status, payload_json)
            VALUES (?, ?, ?, 'info', 'pending', ?)
            """,
            (now, row.get("camera_id"), reason, json.dumps(payload, ensure_ascii=False)),
        )
        added += 1
    con.commit()
    return added


def main() -> int:
    args = _parse_args()
    data_dir = Path(args.data_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "samples").mkdir(parents=True, exist_ok=True)
    cutoff = _recent_cutoff(args.days)

    con = _connect(args.db)
    try:
        cases = []
        cases.extend(_mine_frigate_only_cases(con, cutoff, args.limit))
        cases.extend(_mine_low_conf_cases(con, cutoff, args.limit))
        cases.extend(_mine_operator_corrections(con, cutoff, args.limit))
        cases = _dedupe(cases)
        manifest: list[dict] = []
        for c in cases:
            rec = c.to_dict()
            rec.update(_copy_or_link_evidence(c, data_dir, output_dir))
            manifest.append(rec)
        train, test = _split_train_test(manifest)
        _write_jsonl(output_dir / "all_cases.jsonl", manifest)
        _write_jsonl(output_dir / "train.jsonl", train)
        _write_jsonl(output_dir / "test.jsonl", test)
        seeded = _seed_active_buffer(con, manifest) if args.seed_active_buffer else 0
        stats = {
            "generated_at": _utc_now().isoformat(),
            "db": str(Path(args.db).resolve()),
            "data_dir": str(data_dir),
            "output_dir": str(output_dir),
            "lookback_days": args.days,
            "total_cases": len(manifest),
            "train_cases": len(train),
            "test_cases": len(test),
            "by_type": {
                "frigate_only_yolo_silent": sum(1 for x in manifest if x.get("case_type") == "frigate_only_yolo_silent"),
                "low_confidence_detection": sum(1 for x in manifest if x.get("case_type") == "low_confidence_detection"),
                "operator_correction": sum(1 for x in manifest if x.get("case_type") == "operator_correction"),
            },
            "active_learning_buffer_seeded": seeded,
        }
        (output_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
