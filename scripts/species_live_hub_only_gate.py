#!/usr/bin/env python3
"""Live Hub-only species pack gate (RC6 residual).

Expects ``benchmarks/species_live_hub_only/manifest.json`` listing labeled clips.
Without clips: PASS + skipped unless ``--require-clips``.
With clips: validate files + mqtt=off; optional heavy regen via ``--run-clips``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "benchmarks/species_live_hub_only"
MANIFEST = PACK / "manifest.json"
REPORT_DIR = REPO / "docs/reports/pipeline_golden"
GENERIC_SPECIES = frozenset({"bird", "unknown", "unknown bird", "птица", ""})


def _run_regen(clip_path: Path, *, frame_step: int, max_runtime_sec: int) -> dict:
    # Prefer container layout (/app) when present; else repo checkout.
    if Path("/app/processor/src").is_dir():
        app_root = Path("/app")
        src = Path("/app/processor/src")
    else:
        app_root = REPO / "app"
        src = app_root / "processor/src"
    for p in (str(app_root), str(src)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from track_regenerator import process_video_for_tracks  # type: ignore

    metrics: dict = {}
    detections = process_video_for_tracks(
        str(clip_path),
        frame_step=max(1, frame_step),
        max_runtime_sec=max_runtime_sec,
        metrics_out=metrics,
    )
    with_frames = [d for d in detections if d.get("frames")]
    named = [
        d
        for d in detections
        if str(d.get("species_name") or "").strip().lower() not in GENERIC_SPECIES
    ]
    return {
        "clip": str(clip_path),
        "detection_count": len(detections),
        "persist_with_frames": len(with_frames),
        "named_species_count": len(named),
        "named_species": sorted(
            {str(d.get("species_name") or "") for d in named if d.get("species_name")}
        ),
        "metrics": metrics,
    }


def _check_clip_row(
    clip: dict,
    *,
    pack: Path,
    run_clips: bool,
    frame_step: int,
    max_runtime_sec: int,
) -> dict:
    row: dict = {
        "clip": clip.get("clip"),
        "expected_kind": clip.get("expected_kind"),
        "expected_species": clip.get("expected_species"),
        "ok": True,
        "fail": None,
    }
    rel = str(clip.get("clip") or "").strip()
    if not rel:
        row["ok"] = False
        row["fail"] = "missing_clip_path"
        return row
    path = pack / rel
    if not path.is_file():
        row["ok"] = False
        row["fail"] = f"clip_missing:{rel}"
        return row
    row["bytes"] = path.stat().st_size
    mqtt = str(clip.get("mqtt") or "").strip().lower()
    if mqtt and mqtt not in {"off", "0", "false", "no"}:
        row["ok"] = False
        row["fail"] = f"mqtt_must_be_off:{mqtt}"
        return row

    kind = str(clip.get("expected_kind") or "").strip()
    if kind and kind not in {"named_accept", "presence", "review"}:
        row["ok"] = False
        row["fail"] = f"bad_expected_kind:{kind}"
        return row

    if not run_clips:
        row["mode"] = "manifest_only"
        return row

    try:
        stats = _run_regen(path, frame_step=frame_step, max_runtime_sec=max_runtime_sec)
    except Exception as exc:  # noqa: BLE001 — gate reports error
        row["ok"] = False
        row["fail"] = f"regen_error:{exc}"
        row["mode"] = "runtime"
        return row
    row.update(stats)
    row["mode"] = "runtime"
    got = {str(s).strip().lower() for s in (stats.get("named_species") or []) if s}
    want_species = str(clip.get("expected_species") or "").strip().lower()

    if kind == "named_accept":
        if not want_species:
            row["ok"] = False
            row["fail"] = "named_accept_requires_expected_species"
        elif want_species not in got:
            row["ok"] = False
            row["fail"] = f"expected_species {want_species!r} not in {sorted(got)}"
        elif int(stats.get("persist_with_frames") or 0) <= 0:
            row["ok"] = False
            row["fail"] = "named_accept:persist_with_frames=0"
    elif kind == "presence":
        if int(stats.get("persist_with_frames") or 0) <= 0 and int(stats.get("detection_count") or 0) <= 0:
            row["ok"] = False
            row["fail"] = "presence:no_tracks"
    elif kind == "review":
        # Soft: must produce some track evidence; named mismatch is OK.
        if int(stats.get("detection_count") or 0) <= 0:
            row["ok"] = False
            row["fail"] = "review:no_detections"
    return row


def _run_via_docker(container: str, argv: list[str], *, pack: Path) -> int:
    """Copy pack into container, run gate with processor deps, copy report back."""
    import subprocess

    remote_pack = "/tmp/species_live_hub_only_pack"
    remote_report = "/tmp/species_live_hub_only_latest.json"
    subprocess.run(["docker", "exec", container, "rm", "-rf", remote_pack], check=False)
    subprocess.run(["docker", "cp", str(pack), f"{container}:{remote_pack}"], check=True)
    remote_script = "/tmp/species_live_hub_only_gate.py"
    subprocess.run(["docker", "cp", str(Path(__file__).resolve()), f"{container}:{remote_script}"], check=True)
    inner = [
        "docker",
        "exec",
        "-e",
        f"SPECIES_LIVE_PACK={remote_pack}",
        "-e",
        "PYTHONPATH=/app/processor/src:/app",
        "-e",
        "DATA_DIR=/app/data",
        container,
        "python3",
        remote_script,
        *argv,
        f"--report={remote_report}",
        f"--pack={remote_pack}",
    ]
    proc = subprocess.run(inner, check=False)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    local_report = REPORT_DIR / "species_live_hub_only_latest.json"
    subprocess.run(["docker", "cp", f"{container}:{remote_report}", str(local_report)], check=False)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true")
    ap.add_argument(
        "--require-clips",
        action="store_true",
        help="Fail when manifest missing or clip list empty (strict CI).",
    )
    ap.add_argument(
        "--run-clips",
        action="store_true",
        help="Run track regenerator on each clip (needs models; Orin/local GPU).",
    )
    ap.add_argument("--frame-step", type=int, default=int(os.environ.get("SPECIES_LIVE_FRAME_STEP", "3")))
    ap.add_argument(
        "--max-runtime-sec",
        type=int,
        default=int(os.environ.get("SPECIES_LIVE_MAX_RUNTIME_SEC", "180")),
    )
    ap.add_argument(
        "--docker",
        default=os.environ.get("SPECIES_LIVE_DOCKER", "").strip(),
        help="Run heavy regen inside container (e.g. birdlense).",
    )
    ap.add_argument(
        "--report",
        default="",
        help="Override report JSON path (used by docker inner run).",
    )
    ap.add_argument(
        "--pack",
        default=os.environ.get("SPECIES_LIVE_PACK", "").strip(),
        help="Override pack directory (docker inner run).",
    )
    args = ap.parse_args()
    if os.environ.get("SPECIES_LIVE_RUN", "").strip() in {"1", "true", "yes"}:
        args.run_clips = True
    if os.environ.get("REQUIRE_CLIPS", "").strip() in {"1", "true", "yes"}:
        args.require_clips = True

    pack = Path(args.pack) if args.pack else PACK
    manifest = pack / "manifest.json"
    report_path = Path(args.report) if args.report else (REPORT_DIR / "species_live_hub_only_latest.json")

    if args.docker and args.run_clips:
        inner_argv = ["--enforce", "--run-clips"]
        if args.require_clips:
            inner_argv.append("--require-clips")
        inner_argv.extend(["--frame-step", str(args.frame_step)])
        inner_argv.extend(["--max-runtime-sec", str(args.max_runtime_sec)])
        return _run_via_docker(args.docker, inner_argv, pack=pack)

    try:
        pack_label = str(pack.relative_to(REPO))
    except ValueError:
        pack_label = str(pack)

    payload: dict = {
        "ok": True,
        "product": "taxonomy_live_hub_only",
        "skipped": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pack": pack_label,
        "clips": 0,
        "fail": [],
        "results": [],
        "mode": "empty",
    }

    if not manifest.is_file():
        payload["skipped"] = True
        payload["skip_reason"] = "manifest_missing"
        if args.require_clips:
            payload["ok"] = False
            payload["fail"] = ["manifest_missing"]
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload["ok"] = False
            payload["fail"] = [f"manifest_invalid:{exc}"]
            data = {}
        if isinstance(data, dict) and str(data.get("mqtt") or "off").lower() not in {
            "off",
            "0",
            "false",
            "no",
            "",
        }:
            payload["ok"] = False
            payload["fail"].append(f"pack_mqtt_must_be_off:{data.get('mqtt')}")
        clips = data.get("clips") if isinstance(data, dict) else None
        if not isinstance(clips, list) or not clips:
            payload["skipped"] = True
            payload["skip_reason"] = "clips_empty"
            if args.require_clips:
                payload["ok"] = False
                payload["fail"] = ["clips_empty"]
        else:
            payload["clips"] = len(clips)
            payload["mode"] = "runtime" if args.run_clips else "manifest_only"
            for clip in clips:
                if not isinstance(clip, dict):
                    payload["ok"] = False
                    payload["fail"].append("clip_entry_not_object")
                    continue
                row = _check_clip_row(
                    clip,
                    pack=pack,
                    run_clips=args.run_clips,
                    frame_step=args.frame_step,
                    max_runtime_sec=args.max_runtime_sec,
                )
                payload["results"].append(row)
                if not row.get("ok"):
                    payload["ok"] = False
                    payload["fail"].append(str(row.get("fail") or "clip_fail"))

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    status = "PASS" if payload["ok"] else "FAIL"
    skip = f" skipped={payload.get('skip_reason')}" if payload.get("skipped") else ""
    print(
        f"{status} species-live-hub-only "
        f"(clips={payload['clips']} mode={payload.get('mode')}{skip})"
    )
    if args.enforce and not payload["ok"]:
        return 1
    return 0 if payload["ok"] else (1 if args.enforce else 0)


if __name__ == "__main__":
    sys.exit(main())
