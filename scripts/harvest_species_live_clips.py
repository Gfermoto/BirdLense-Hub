#!/usr/bin/env python3
"""Harvest short labeled Hub YOLO clips into benchmarks/species_live_hub_only/.

Typical Orin usage (inside repo on device or via ssh):

  python3 scripts/harvest_species_live_clips.py \\
    --db app/data/db/birdlense.db \\
    --recordings-root app/data \\
    --limit 4 --clip-seconds 6

Writes gitignored mp4 under clips/ + updates manifest.json.
Does not require Frigate; prefers detection_provider=yolo and excludes
generic Bird/Unknown labels.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "benchmarks/species_live_hub_only"
GENERIC = {"bird", "unknown", "unknown bird", "птица"}


def _ffmpeg_cut(
    src: Path,
    dst: Path,
    *,
    seconds: float,
    ffmpeg_bin: str = "ffmpeg",
    docker_container: str = "",
    container_src: Path | None = None,
    container_dst: Path | None = None,
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    in_path = str(container_src or src)
    out_path = str(container_dst or dst)
    ff_args = [
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        in_path,
        "-t",
        str(max(1.0, seconds)),
        "-c",
        "copy",
        out_path,
    ]
    if docker_container:
        # Ensure host output dir exists; container must see same bind mount.
        cmd = ["docker", "exec", docker_container, "ffmpeg", *ff_args]
    else:
        cmd = [ffmpeg_bin, *ff_args]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument(
        "--recordings-root",
        type=Path,
        default=None,
        help="Directory that contains data/recordings/... (usually app/ or app/data parent).",
    )
    ap.add_argument("--limit", type=int, default=4)
    ap.add_argument("--clip-seconds", type=float, default=6.0)
    ap.add_argument("--copy-full", action="store_true", help="Copy full mp4 (no ffmpeg cut).")
    ap.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg binary (Orin host often missing ffmpeg: "
        "--ffmpeg 'docker exec birdlense ffmpeg' is not supported; "
        "use --docker-ffmpeg birdlense instead).",
    )
    ap.add_argument(
        "--docker-ffmpeg",
        metavar="CONTAINER",
        default="",
        help="Run ffmpeg inside a container (paths must be visible there).",
    )
    ap.add_argument(
        "--container-data-root",
        type=Path,
        default=Path("/app"),
        help="With --docker-ffmpeg: container path that mirrors --recordings-root layout.",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        print(f"FAIL: db missing {args.db}", file=sys.stderr)
        return 1

    root = args.recordings_root
    if root is None:
        # video_path like data/recordings/... → root is parent of that relative tree
        root = args.db.parent.parent if args.db.parent.name == "db" else args.db.parent

    con = sqlite3.connect(str(args.db))
    con.row_factory = sqlite3.Row
    q = """
    SELECT v.id AS video_id, v.video_path, v.camera_id, s.name AS species,
           vs.confidence, vs.detection_provider, vs.classifier_needs_review
    FROM video_species vs
    JOIN video v ON v.id = vs.video_id
    JOIN species s ON s.id = vs.species_id
    WHERE v.deleted_at IS NULL
      AND lower(s.name) NOT IN ('bird','unknown','unknown bird','птица')
      AND lower(coalesce(vs.detection_provider,'')) LIKE '%yolo%'
      AND coalesce(vs.classifier_needs_review, 0) = 0
      AND vs.confidence >= 0.5
    ORDER BY vs.confidence DESC, vs.id DESC
    LIMIT ?
    """
    rows = list(con.execute(q, (max(1, args.limit) * 8,)))
    clips_out: list[dict] = []
    seen_species: set[str] = set()
    clips_dir = PACK / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    docker_ctr = str(args.docker_ffmpeg or "").strip()

    for r in rows:
        species = str(r["species"] or "").strip()
        key = species.lower()
        if key in GENERIC or key in seen_species:
            continue
        rel_video = str(r["video_path"] or "").lstrip("./")
        src = root / rel_video
        if not src.is_file():
            # try app/ prefix layouts
            alt = root.parent / rel_video if root.name == "data" else None
            if alt and alt.is_file():
                src = alt
            else:
                print(f"skip missing {src}", file=sys.stderr)
                continue
        slug = key.replace(" ", "_").replace("-", "_")[:40]
        out_name = f"{r['video_id']}_{slug}.mp4"
        dst = clips_dir / out_name
        try:
            if args.copy_full:
                shutil.copy2(src, dst)
            elif docker_ctr:
                # Cut into container /tmp (writable), then docker cp to pack.
                ctr_src = args.container_data_root / rel_video
                ctr_tmp = Path("/tmp") / f"species_live_{out_name}"
                _ffmpeg_cut(
                    src,
                    dst,
                    seconds=args.clip_seconds,
                    docker_container=docker_ctr,
                    container_src=ctr_src,
                    container_dst=ctr_tmp,
                )
                subprocess.run(
                    ["docker", "cp", f"{docker_ctr}:{ctr_tmp}", str(dst)],
                    check=True,
                )
                subprocess.run(
                    ["docker", "exec", docker_ctr, "rm", "-f", str(ctr_tmp)],
                    check=False,
                )
            else:
                _ffmpeg_cut(
                    src,
                    dst,
                    seconds=args.clip_seconds,
                    ffmpeg_bin=args.ffmpeg,
                )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"skip cut {src}: {exc}", file=sys.stderr)
            continue
        clips_out.append(
            {
                "clip": f"clips/{out_name}",
                "camera_id": r["camera_id"],
                "expected_kind": "named_accept",
                "expected_species": species,
                "mqtt": "off",
                "source_video_id": int(r["video_id"]),
                "source_confidence": float(r["confidence"] or 0.0),
            }
        )
        seen_species.add(key)
        if len(clips_out) >= args.limit:
            break

    manifest = {
        "schema": "species_live_hub_only@v1",
        "mqtt": "off",
        "clips": clips_out,
        "harvest_note": "mp4 under clips/ are gitignored; regenerate via this script",
    }
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK harvested {len(clips_out)} clips → {PACK / 'manifest.json'}")
    for c in clips_out:
        print(f"  {c['clip']} → {c['expected_species']}")
    return 0 if clips_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
