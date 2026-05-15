#!/usr/bin/env python3
"""
Экспорт кропов из БД BirdLense (SQLite) для цепочки Re-ID / DINO (#383).

Читает ``video_species`` + ``video`` + ``species``, для каждой строки с ``frames``:
считает offset (середина ``start_time``..``end_time``), bbox ближайшего кадра
(как в ``shared/detection_crop_contract``), вырезает JPEG кроп с тем же
пайплайном, что и ``detection_crop_service.extract_detection_frame_cropped``.

**Запуск с корня репозитория Hub** (где лежат ``app/data/`` и БД)::

    export DATA_DIR=app/data   # опционально, по умолчанию ./app/data от корня
    python3 scripts/reid/export_crops_from_sqlite.py \\
      --db app/data/db/birdlense.db --output-dir /tmp/reid_crops --limit 100

Дальше: ``embed_dinov2_crop.py --glob '/tmp/reid_crops/*.jpg' -o embed.jsonl`` и
``embed_cosine_report.py``.

Зависимости: **ffmpeg** в PATH, **opencv-python** (``cv2``) для кропа кадра.
Без Flask; ``DATA_DIR`` + импорт ``web.data_paths.full_path_for_video`` (добавьте
``app`` в ``PYTHONPATH`` — скрипт делает это сам от расположения файла).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

# Репозиторий: .../BirdLense (родитель scripts/)
_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
os.environ.setdefault("DATA_DIR", str(_REPO / "app" / "data"))

from shared.detection_crop_contract import bbox_for_offset  # noqa: E402
from web.data_paths import full_path_for_video  # noqa: E402

_VIDEO_SAFE = re.compile(r"^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$")


def _extract_frame_jpeg(full_path: str, offset_sec: float) -> bytes | None:
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(offset_sec),
            "-i",
            full_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-f",
            "image2",
            "pipe:1",
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        if r.returncode != 0:
            return None
        return r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def _jpeg_crop_bbox(jpeg_bytes: bytes, bbox_norm: list[float]) -> bytes | None:
    if not bbox_norm or len(bbox_norm) != 4:
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("Requires opencv-python: pip install opencv-python", file=sys.stderr)
        return None
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    x1 = int(bbox_norm[0] * w)
    y1 = int(bbox_norm[1] * h)
    x2 = int(bbox_norm[2] * w)
    y2 = int(bbox_norm[3] * h)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = img[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes() if ok and buf is not None else None


def _offset_mid(start: float, end: float) -> float:
    return float(start) + max(0.0, float(end) - float(start)) / 2.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        type=Path,
        default=Path("app/data/db/birdlense.db"),
        help="Путь к birdlense.db (от корня репо)",
    )
    ap.add_argument(
        "--output-dir", "-o", type=Path, required=True, help="Куда писать JPEG кропы"
    )
    ap.add_argument("--limit", type=int, default=200, help="Макс. строк video_species")
    ap.add_argument("--species-id", type=int, default=None, help="Фильтр по species_id")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Дополнительно записать JSON Lines метаданные (vs_id, path, species, track_id)",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    q = """
        SELECT vs.id AS vs_id, vs.frames AS frames, vs.start_time AS start_time, vs.end_time AS end_time,
               vs.track_id AS track_id, vs.species_id AS species_id,
               vs.individual_nickname AS individual_nickname,
               v.video_path AS video_path, v.id AS video_id, s.name AS species_name
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        JOIN species s ON s.id = vs.species_id
        WHERE v.deleted_at IS NULL
          AND vs.frames IS NOT NULL
          AND trim(vs.frames) != ''
    """
    params: list = []
    if args.species_id is not None:
        q += " AND vs.species_id = ?"
        params.append(args.species_id)
    q += " ORDER BY vs.id DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(q, params).fetchall()
    conn.close()

    manifest_lines: list[str] = []
    saved = 0
    skipped = 0

    for row in rows:
        vs_id = row["vs_id"]
        video_path = row["video_path"]
        if not video_path or not _VIDEO_SAFE.match(str(video_path).replace("\\", "/")):
            skipped += 1
            continue
        full = full_path_for_video(str(video_path))
        if not full or not Path(full).is_file():
            skipped += 1
            continue

        try:
            st = float(row["start_time"] or 0.0)
            en = float(row["end_time"] or st)
        except (TypeError, ValueError):
            skipped += 1
            continue
        offset = _offset_mid(st, en)
        bbox = bbox_for_offset(row["frames"], offset)
        if not bbox:
            skipped += 1
            continue

        jpeg = _extract_frame_jpeg(full, offset)
        if not jpeg:
            skipped += 1
            continue
        crop_bytes = _jpeg_crop_bbox(jpeg, bbox)
        if not crop_bytes:
            skipped += 1
            continue

        slug = re.sub(r"[^\w\-]+", "_", str(row["species_name"] or "unknown"))[:60]
        tid = row["track_id"] if row["track_id"] is not None else "x"
        fname = f"vs{vs_id}_tr{tid}_{slug}.jpg"
        out_path = args.output_dir / fname
        out_path.write_bytes(crop_bytes)
        saved += 1

        meta = {
            "crop_path": str(out_path.resolve()),
            "video_species_id": vs_id,
            "video_id": row["video_id"],
            "track_id": row["track_id"],
            "species_name": row["species_name"],
            "species_id": row["species_id"],
            "individual_nickname": row["individual_nickname"],
            "video_path": video_path,
            "offset_sec": offset,
        }
        manifest_lines.append(json.dumps(meta, ensure_ascii=False))

    print(
        f"Saved {saved} crops → {args.output_dir} (skipped {skipped})", file=sys.stderr
    )

    if args.manifest:
        args.manifest.write_text(
            "\n".join(manifest_lines) + ("\n" if manifest_lines else ""),
            encoding="utf-8",
        )
        print(f"Manifest → {args.manifest}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
