#!/usr/bin/env python3
"""Convert Zenodo Visual-WetlandBirds crops.csv → per-clip CSVs for ml_behavior_import_wetlandbirds."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

# Zenodo behaviors_ID.csv → BirdLense DEFAULT_TAXONOMY ids (ml_behavior_dataset_manifest.py)
ZENODO_ACTION_TO_BL_ID: dict[int, int] = {
    0: 2,  # Feeding
    1: 4,  # Preening
    2: 6,  # Swimming
    3: 7,  # Walking
    4: 1,  # Alert
    5: 3,  # Flying
    6: 5,  # Resting
}

BL_ID_TO_LABEL: dict[int, str] = {
    1: "alert",
    2: "feeding",
    3: "flying",
    4: "preening",
    5: "resting",
    6: "swimming",
    7: "walking",
}


def _load_species_map(path: Path | None) -> dict[int, str]:
    if path is None or not path.is_file():
        return {}
    out: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                sid = int(float(row.get("ID") or row.get("id") or -1))
            except (TypeError, ValueError):
                continue
            name = str(row.get("Species") or row.get("species") or row.get("name") or "").strip()
            if name:
                out[sid] = name
    return out


def _bbox_for_frame(*, action_id: int, frame_idx: int, n_frames: int) -> list[float]:
    """Normalized 0..1 bbox; flying clips get horizontal motion."""
    t = frame_idx / max(1, n_frames - 1)
    if action_id == 5:  # flying
        x1 = 0.15 + 0.55 * t
        y1 = 0.25 + 0.05 * math.sin(t * math.pi)
        w, h = 0.18, 0.14
    elif action_id == 2:  # feeding
        x1, y1, w, h = 0.35, 0.42, 0.22, 0.18
        y1 += 0.02 * math.sin(frame_idx / 3.0)
    else:
        x1, y1, w, h = 0.4, 0.4, 0.2, 0.16
    return [x1, y1, min(0.98, x1 + w), min(0.98, y1 + h)]


def convert_crops_csv(
    *,
    crops_csv: Path,
    out_annotations_dir: Path,
    species_csv: Path | None = None,
    min_frames: int = 5,
    labels_filter: set[str] | None = None,
) -> dict[str, int]:
    species_map = _load_species_map(species_csv)
    out_annotations_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    label_counts: dict[str, int] = {}

    with crops_csv.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            try:
                z_action = int(row["action_id"])
                start = int(row["start_frame"])
                end = int(row["end_frame"])
                bird_id = str(row["bird_id"])
                video_name = str(row["video_name"]).strip()
                species_id = int(row.get("species_id") or 0)
            except (KeyError, TypeError, ValueError):
                continue

            bl_id = ZENODO_ACTION_TO_BL_ID.get(z_action)
            if bl_id is None:
                continue
            label = BL_ID_TO_LABEL.get(bl_id, "unknown")
            if labels_filter and label not in labels_filter:
                continue

            n_raw = max(1, end - start + 1)
            frame_ids = list(range(start, end + 1))
            while len(frame_ids) < int(min_frames):
                frame_ids.append(frame_ids[-1])

            clip_key = f"{video_name}_b{bird_id}_a{z_action}_{start}_{end}"
            out_path = out_annotations_dir / f"{clip_key}.csv"
            species_name = species_map.get(species_id, "")

            with out_path.open("w", encoding="utf-8", newline="") as out_fh:
                w = csv.writer(out_fh)
                for fi, frame_idx in enumerate(frame_ids):
                    bbox = _bbox_for_frame(action_id=z_action, frame_idx=fi, n_frames=len(frame_ids))
                    w.writerow(
                        [
                            f"{bbox[0]:.6f}",
                            f"{bbox[1]:.6f}",
                            f"{bbox[2]:.6f}",
                            f"{bbox[3]:.6f}",
                            bl_id,
                            f"bird_{bird_id}",
                            species_name,
                        ]
                    )
            written += 1
            label_counts[label] = label_counts.get(label, 0) + 1

    return {"clips_written": written, "label_counts": label_counts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crops-csv", required=True, help="Zenodo crops.csv path")
    ap.add_argument("--out-dir", required=True, help="Output directory of per-clip CSV files")
    ap.add_argument("--species-csv", default="")
    ap.add_argument("--min-frames", type=int, default=5)
    ap.add_argument(
        "--labels",
        default="",
        help="Comma-separated BirdLense labels to export (default: all)",
    )
    args = ap.parse_args()

    labels_filter: set[str] | None = None
    if str(args.labels).strip():
        labels_filter = {x.strip().lower() for x in str(args.labels).split(",") if x.strip()}

    rep = convert_crops_csv(
        crops_csv=Path(args.crops_csv).expanduser().resolve(),
        out_annotations_dir=Path(args.out_dir).expanduser().resolve(),
        species_csv=Path(args.species_csv).expanduser().resolve() if str(args.species_csv).strip() else None,
        min_frames=int(args.min_frames),
        labels_filter=labels_filter,
    )
    import json

    print(json.dumps({"ok": True, **rep}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
