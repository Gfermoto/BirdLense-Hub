#!/usr/bin/env python3
"""
Daily offline SSL/Re-ID maintenance cycle.

Pipeline:
1) extract recent crops from video_species (frames + video_path),
2) build Ornimetrics reid_embedder embeddings via runtime ReID backend,
3) upsert embeddings into reid_embedding,
4) recluster embeddings per species,
5) refresh Re-ID candidate labels (individual_label) and optional video nicknames,
6) emit metrics report (consistency/churn/id switches).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT if (ROOT / "web").is_dir() and (ROOT / "processor").is_dir() else ROOT / "app"
for p in (APP, APP / "web", APP / "processor" / "src"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

os.environ.setdefault("DATA_DIR", str(APP / "data"))

from shared.detection_crop_contract import bbox_for_offset  # noqa: E402
from web.data_paths import full_path_for_video  # noqa: E402
import reid_runtime  # noqa: E402


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _species_token(name: str) -> str:
    import re

    token = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")
    return token[:24] if token else "bird"


def _crop_fingerprint_sha16(crop: np.ndarray) -> str:
    raw = np.asarray(crop, dtype=np.uint8).tobytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def _embedding_model_sha16(state: dict[str, Any]) -> str:
    payload = "|".join(
        [
            str(state.get("model_name") or ""),
            str(state.get("backend") or ""),
            str(state.get("effective_device") or ""),
            str(state.get("side") or ""),
        ]
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _ensure_reid_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reid_embedding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_species_id INTEGER,
            video_id INTEGER,
            species_id INTEGER,
            track_id INTEGER,
            crop_path TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            embedding_json TEXT NOT NULL,
            species_name TEXT,
            individual_label TEXT,
            embedding_schema TEXT,
            embedding_model_id TEXT,
            embedding_model_sha16 TEXT,
            crop_fingerprint_sha16 TEXT,
            jsonl_created_at_utc TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_reid_embedding_video_species_id ON reid_embedding(video_species_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_reid_embedding_species_id ON reid_embedding(species_id)"
    )


@dataclass
class Sample:
    vs_id: int
    video_id: int
    species_id: int
    species_name: str
    track_id: int | None
    video_path: str
    start_time: float
    end_time: float
    frames_raw: str
    old_nickname: str | None
    manually_corrected: bool


def _load_samples(conn: sqlite3.Connection, window_hours: int, limit: int) -> list[Sample]:
    q = """
    SELECT
      vs.id, vs.video_id, vs.species_id, s.name AS species_name, vs.track_id,
      v.video_path, vs.start_time, vs.end_time, vs.frames,
      vs.individual_nickname, COALESCE(vs.manually_corrected, 0) AS manually_corrected
    FROM video_species vs
    JOIN video v ON v.id = vs.video_id
    JOIN species s ON s.id = vs.species_id
    WHERE v.deleted_at IS NULL
      AND vs.source = 'video'
      AND vs.frames IS NOT NULL
      AND TRIM(vs.frames) != ''
      AND vs.created_at >= datetime('now', ?)
    ORDER BY vs.id DESC
    LIMIT ?
    """
    rows = conn.execute(q, (f"-{int(window_hours)} hours", int(limit))).fetchall()
    out: list[Sample] = []
    for r in rows:
        out.append(
            Sample(
                vs_id=int(r[0]),
                video_id=int(r[1]),
                species_id=int(r[2]),
                species_name=str(r[3] or ""),
                track_id=int(r[4]) if r[4] is not None else None,
                video_path=str(r[5] or ""),
                start_time=float(r[6] or 0.0),
                end_time=float(r[7] or 0.0),
                frames_raw=str(r[8] or ""),
                old_nickname=(str(r[9]).strip() if r[9] is not None and str(r[9]).strip() else None),
                manually_corrected=bool(int(r[10] or 0)),
            )
        )
    return out


def _extract_crop(sample: Sample) -> np.ndarray | None:
    full = full_path_for_video(sample.video_path)
    if not full or not Path(full).is_file():
        return None
    duration = max(0.0, sample.end_time - sample.start_time)
    offset = sample.start_time + (duration * 0.5)
    bbox = bbox_for_offset(sample.frames_raw, offset)
    if not bbox:
        return None
    cap = cv2.VideoCapture(str(full))
    cap.set(cv2.CAP_PROP_POS_MSEC, float(offset) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    h, w = frame.shape[:2]
    x1 = max(0, min(w, int(float(bbox[0]) * w)))
    y1 = max(0, min(h, int(float(bbox[1]) * h)))
    x2 = max(0, min(w, int(float(bbox[2]) * w)))
    y2 = max(0, min(h, int(float(bbox[3]) * h)))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    if den <= 1e-12:
        return -1.0
    return float(np.dot(a, b) / den)


def _recluster(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    by_species: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_species[row["species_name"]].append(row)

    updated: list[dict[str, Any]] = []
    for species_name, items in by_species.items():
        centroids: list[np.ndarray] = []
        members: list[list[int]] = []
        for idx, item in enumerate(items):
            vec = item["embedding"]
            best_i = -1
            best_s = -1.0
            for ci, cvec in enumerate(centroids):
                score = _cosine(vec, cvec)
                if score > best_s:
                    best_s = score
                    best_i = ci
            if best_i >= 0 and best_s >= threshold:
                members[best_i].append(idx)
                arr = np.stack([items[j]["embedding"] for j in members[best_i]], axis=0)
                cent = np.mean(arr, axis=0)
                n = np.linalg.norm(cent)
                centroids[best_i] = cent / n if n > 1e-12 else centroids[best_i]
            else:
                members.append([idx])
                centroids.append(vec.copy())

        token = _species_token(species_name)
        for ci, member_idx in enumerate(members, start=1):
            label = f"{token}_{ci:03d}"
            centroid = centroids[ci - 1]
            for mi in member_idx:
                item = items[mi]
                item["new_label"] = label
                item["cluster_similarity"] = _cosine(item["embedding"], centroid)
                updated.append(item)
    return updated


def run_cycle(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_reid_table(conn)

    state = reid_runtime._ensure_model_state()
    if state is None:
        raise RuntimeError("ReID runtime model is unavailable")

    model_id = f"runtime:{state.get('backend')}:{state.get('model_name')}"
    model_sha16 = _embedding_model_sha16(state)
    created_at = _utc_now().isoformat()
    samples = _load_samples(conn, args.window_hours, args.limit)

    extracted = 0
    embedded_rows: list[dict[str, Any]] = []
    for sample in samples:
        crop = _extract_crop(sample)
        if crop is None:
            continue
        extracted += 1
        emb = reid_runtime._to_embedding(crop, state=state)
        if emb is None:
            continue
        embedded_rows.append(
            {
                "sample": sample,
                "embedding": emb.astype(np.float32),
                "species_name": sample.species_name,
                "crop_fp": _crop_fingerprint_sha16(crop),
            }
        )

    reclustered = _recluster(embedded_rows, float(args.cluster_threshold))

    changed = 0
    with_existing = 0
    id_switches = 0
    consistency_vals: list[float] = []
    for row in reclustered:
        sample: Sample = row["sample"]
        new_label = str(row["new_label"])
        if sample.old_nickname:
            with_existing += 1
            if sample.old_nickname != new_label:
                changed += 1
        consistency_vals.append(float(row.get("cluster_similarity") or 0.0))

        crop_path = f"ssl://video_species/{sample.vs_id}"
        conn.execute(
            """
            INSERT INTO reid_embedding (
                video_species_id, video_id, species_id, track_id, crop_path,
                model, dim, embedding_json, species_name, individual_label,
                embedding_schema, embedding_model_id, embedding_model_sha16,
                crop_fingerprint_sha16, jsonl_created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(crop_path) DO UPDATE SET
                model=excluded.model,
                dim=excluded.dim,
                embedding_json=excluded.embedding_json,
                species_name=excluded.species_name,
                individual_label=excluded.individual_label,
                embedding_schema=excluded.embedding_schema,
                embedding_model_id=excluded.embedding_model_id,
                embedding_model_sha16=excluded.embedding_model_sha16,
                crop_fingerprint_sha16=excluded.crop_fingerprint_sha16,
                jsonl_created_at_utc=excluded.jsonl_created_at_utc
            """,
            (
                sample.vs_id,
                sample.video_id,
                sample.species_id,
                sample.track_id,
                crop_path,
                str(state.get("model_name") or "ornimetrics_reid"),
                int(row["embedding"].shape[0]),
                json.dumps([float(x) for x in row["embedding"].tolist()], separators=(",", ":")),
                sample.species_name,
                new_label,
                "embedding_schema@v1",
                model_id,
                model_sha16,
                row["crop_fp"],
                created_at,
            ),
        )

        if args.update_video_nicknames and not sample.manually_corrected and not sample.old_nickname:
            conn.execute(
                "UPDATE video_species SET individual_nickname=? WHERE id=?",
                (new_label, sample.vs_id),
            )

    # ID switches: same (video_id, track_id, species) got >1 label in current cycle.
    track_labels: dict[tuple[int, int, str], set[str]] = defaultdict(set)
    for row in reclustered:
        sample: Sample = row["sample"]
        if sample.track_id is None:
            continue
        key = (sample.video_id, sample.track_id, sample.species_name)
        track_labels[key].add(str(row["new_label"]))
    id_switches = sum(1 for labels in track_labels.values() if len(labels) > 1)

    conn.commit()
    conn.close()

    consistency = float(np.mean(consistency_vals)) if consistency_vals else 0.0
    churn = (changed / with_existing) if with_existing > 0 else 0.0
    report = {
        "schema": "reid_ssl_cycle_report@v1",
        "generated_at_utc": _utc_now().isoformat(),
        "db_path": str(db_path),
        "window_hours": int(args.window_hours),
        "limit": int(args.limit),
        "cluster_threshold": float(args.cluster_threshold),
        "runtime": {
            "backend": state.get("backend"),
            "effective_device": state.get("effective_device"),
            "model_name": state.get("model_name"),
            "model_id": model_id,
            "model_sha16": model_sha16,
        },
        "counts": {
            "samples_loaded": len(samples),
            "crops_extracted": extracted,
            "embeddings_built": len(embedded_rows),
            "rows_reclustered": len(reclustered),
            "nicknames_changed": changed,
            "rows_with_existing_nickname": with_existing,
            "id_switches": id_switches,
        },
        "metrics": {
            "reid_consistency": round(consistency, 6),
            "nickname_churn": round(churn, 6),
            "id_switches": int(id_switches),
        },
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="app/data/db/birdlense.db")
    ap.add_argument("--window-hours", type=int, default=24)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--cluster-threshold", type=float, default=0.88)
    ap.add_argument("--update-video-nicknames", action="store_true")
    ap.add_argument("--report-json", default="app/data/reid_ssl_reports/latest.json")
    args = ap.parse_args()

    report = run_cycle(args)
    out = Path(args.report_json).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "report_json": str(out), "metrics": report.get("metrics")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
