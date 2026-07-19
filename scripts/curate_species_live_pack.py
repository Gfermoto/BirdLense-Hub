#!/usr/bin/env python3
"""Curate multi-species Hub-only live pack by offline named_accept verify.

1. Harvest candidate full clips (``harvest_species_live_clips``).
2. Run ``species_live_hub_only_gate --run-clips --docker`` per species.
3. Keep only clips that pass ``named_accept``.

Orin example::

  python3 scripts/curate_species_live_pack.py \\
    --db app/data/db/birdlense.db --recordings-root app \\
    --limit 6 --per-species-attempts 2 --docker birdlense --copy-full
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "benchmarks/species_live_hub_only"
HARVEST = REPO / "scripts/harvest_species_live_clips.py"
GATE = REPO / "scripts/species_live_hub_only_gate.py"
GATE_REPORT = REPO / "docs/reports/pipeline_golden/species_live_hub_only_latest.json"


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(REPO)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--recordings-root", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=6, help="Target distinct species to keep")
    ap.add_argument(
        "--per-species-attempts",
        type=int,
        default=2,
        help="Harvest/gate this many clips per species before giving up",
    )
    ap.add_argument("--docker", default="birdlense")
    ap.add_argument("--copy-full", action="store_true", default=True)
    ap.add_argument("--frame-step", type=int, default=4)
    ap.add_argument("--max-runtime-sec", type=int, default=180)
    args = ap.parse_args()

    harvest_cmd = [
        sys.executable,
        str(HARVEST),
        "--db",
        str(args.db),
        "--limit",
        str(args.limit),
        "--per-species-attempts",
        str(max(1, int(args.per_species_attempts))),
    ]
    if args.recordings_root:
        harvest_cmd.extend(["--recordings-root", str(args.recordings_root)])
    if args.copy_full:
        harvest_cmd.append("--copy-full")
    if _run(harvest_cmd) != 0:
        print("FAIL: harvest", file=sys.stderr)
        return 1

    manifest_path = PACK / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = list(data.get("clips") or [])
    if not candidates:
        print("FAIL: no candidate clips", file=sys.stderr)
        return 1

    kept: list[dict] = []
    kept_species: set[str] = set()
    species_target = max(1, int(args.limit))
    for clip in candidates:
        species = str(clip.get("expected_species") or "")
        skey = species.lower()
        if skey in kept_species:
            print(f"  {species}: SKIP (already kept)", flush=True)
            continue
        if len(kept) >= species_target:
            break
        # Single-clip manifest for isolation
        trial = {
            "schema": "species_live_hub_only@v1",
            "mqtt": "off",
            "clips": [clip],
        }
        with tempfile.TemporaryDirectory(prefix="species_live_trial_") as tmp:
            trial_pack = Path(tmp) / "pack"
            trial_pack.mkdir()
            (trial_pack / "clips").mkdir()
            src = PACK / str(clip.get("clip") or "")
            if not src.is_file():
                print(f"skip missing {src}", file=sys.stderr)
                continue
            dst = trial_pack / "clips" / src.name
            dst.write_bytes(src.read_bytes())
            trial["clips"][0] = {**clip, "clip": f"clips/{src.name}"}
            (trial_pack / "manifest.json").write_text(
                json.dumps(trial, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            gate_cmd = [
                sys.executable,
                str(GATE),
                "--enforce",
                "--run-clips",
                "--docker",
                str(args.docker),
                "--pack",
                str(trial_pack),
                "--frame-step",
                str(args.frame_step),
                "--max-runtime-sec",
                str(args.max_runtime_sec),
            ]
            rc = _run(gate_cmd)
            payload: dict = {}
            if GATE_REPORT.is_file():
                try:
                    payload = json.loads(GATE_REPORT.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    payload = {}
            ok = rc == 0 and bool(payload.get("ok"))
            print(f"  {species}: {'KEEP' if ok else 'DROP'} rc={rc} fail={payload.get('fail')}")
            if ok:
                kept.append(clip)
                kept_species.add(skey)

    data["clips"] = kept
    data["curated"] = True
    data["per_species_attempts"] = max(1, int(args.per_species_attempts))
    data["curate_note"] = (
        f"offline named_accept verified ({len(kept)} species / {len(candidates)} candidates)"
    )
    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Drop unused mp4s
    keep_names = {Path(str(c.get("clip"))).name for c in kept}
    clips_dir = PACK / "clips"
    if clips_dir.is_dir():
        for mp4 in clips_dir.glob("*.mp4"):
            if mp4.name not in keep_names:
                mp4.unlink(missing_ok=True)

    print(f"OK curated {len(kept)}/{len(candidates)} clips → {manifest_path}")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
