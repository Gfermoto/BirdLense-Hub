#!/usr/bin/env python3
"""Detector / track golden gate (#611, RC6): bird clip must yield tracks + persist rows.

Product scope: **detector** (presence / tracks). Taxonomy / named species is
``scripts/species_golden_gate.py`` — unit fallback here must never imply species PASS.

Without mp4 fixtures, falls back to unit tests (test_yolo_golden_clips_gate.py).
With ``SOTA_GOLDEN_CLIP_1819`` or ``benchmarks/fixtures/clip_1819.mp4``: runs track regen.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "benchmarks/golden_clips.json"
REPORT_DIR = REPO / "docs/reports/pipeline_golden"
GENERIC_SPECIES = frozenset({"bird", "unknown", "unknown bird", "птица", ""})


def _load_manifest() -> dict:
    if not MANIFEST.is_file():
        raise SystemExit(f"FAIL: missing manifest {MANIFEST}")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _resolve_clip_path(meta: dict) -> Path | None:
    for key in ("env_var", "legacy_env_var"):
        name = meta.get(key)
        if not name:
            continue
        raw = os.environ.get(str(name), "").strip()
        if raw:
            path = Path(raw)
            if path.is_file():
                return path
    fixture = meta.get("fixture_path")
    if fixture:
        path = REPO / str(fixture)
        if path.is_file():
            return path
    return None


def _run_regen(clip_path: Path, *, frame_step: int, max_runtime_sec: int) -> dict:
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
        "named_species": sorted({str(d.get("species_name") or "") for d in named if d.get("species_name")}),
        "metrics": metrics,
    }


def _unit_fallback() -> int:
    tests = REPO / "app/processor/tests/test_yolo_golden_clips_gate.py"
    if not tests.is_file():
        print("FAIL: no golden mp4 and no unit tests", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO / 'app/processor/src'}:{REPO / 'app'}"
    env["SKIP_HEAVY_PROCESSOR_TESTS"] = "1"
    proc = subprocess.run(
        ["python3", "-m", "pytest", str(tests), "-q"],
        cwd=str(REPO / "app/processor"),
        env=env,
    )
    return proc.returncode


def _write_report(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "pipeline_golden_latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Detector golden gate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- product: `{payload.get('product')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- taxonomy_evaluated: `{payload.get('taxonomy_evaluated')}`",
        f"- taxonomy_note: `{payload.get('taxonomy_note')}`",
        f"- checked_at: `{payload.get('checked_at')}`",
    ]
    for clip in payload.get("clips") or []:
        lines.append(
            f"- {clip.get('id')}: detections={clip.get('detection_count')} "
            f"persist_frames={clip.get('persist_with_frames')} "
            f"named={clip.get('named_species_count')}"
        )
    (REPORT_DIR / "pipeline_golden_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enforce", action="store_true", help="Exit 1 on failure")
    parser.add_argument("--frame-step", type=int, default=int(os.environ.get("PIPELINE_GOLDEN_FRAME_STEP", "3")))
    parser.add_argument(
        "--max-runtime-sec",
        type=int,
        default=int(os.environ.get("PIPELINE_GOLDEN_MAX_RUNTIME_SEC", "180")),
    )
    parser.add_argument("--skip-heavy", action="store_true", help="Unit tests only (CI default)")
    args = parser.parse_args()

    manifest = _load_manifest()
    clips_meta = manifest.get("clips") or {}
    results: list[dict] = []
    ran_live = False
    ok = True

    for clip_id, meta in clips_meta.items():
        role = str(meta.get("role") or "")
        path = None if args.skip_heavy else _resolve_clip_path(meta)
        row: dict = {"id": clip_id, "role": role, "path": str(path) if path else None}
        if path is None:
            results.append(row)
            continue
        ran_live = True
        try:
            stats = _run_regen(path, frame_step=args.frame_step, max_runtime_sec=args.max_runtime_sec)
            row.update(stats)
        except Exception as exc:
            row["error"] = str(exc)
            ok = False
            results.append(row)
            continue
        if role == "birds_recall":
            if int(row.get("persist_with_frames") or 0) <= 0:
                ok = False
                row["fail"] = "birds clip: persist_with_frames=0"
            elif int(row.get("detection_count") or 0) <= 0:
                ok = False
                row["fail"] = "birds clip: detection_count=0"
            # Optional taxonomy assert only when labels exist (live species pack).
            expected = meta.get("expected_species") or []
            if expected:
                got = {str(s).strip().lower() for s in (row.get("named_species") or []) if s}
                want = {str(s).strip().lower() for s in expected if s}
                if not (got & want):
                    ok = False
                    row["fail"] = f"birds clip: expected_species {sorted(want)} not in {sorted(got)}"
        results.append(row)

    mode = "live" if ran_live else "unit_fallback"
    taxonomy_evaluated = False
    if not ran_live:
        rc = _unit_fallback()
        ok = rc == 0 and ok
        mode = "unit_fallback"
    else:
        taxonomy_evaluated = any(
            (c.get("role") == "birds_recall" and (clips_meta.get(c["id"]) or {}).get("expected_species"))
            for c in results
            if c.get("id")
        )

    payload = {
        "schema": "pipeline_golden_gate@v2",
        "product": "detector",
        "ok": ok,
        "mode": mode,
        "taxonomy_evaluated": taxonomy_evaluated,
        "taxonomy_note": (
            "evaluated via expected_species on live clips"
            if taxonomy_evaluated
            else "not_evaluated — use make validate-species-golden"
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "clips": results,
    }
    _write_report(payload)

    if ok:
        tax = "taxonomy=evaluated" if taxonomy_evaluated else "taxonomy=not_evaluated"
        print(f"PASS detector-golden ({mode}, product=detector, {tax})")
        return 0
    print(f"FAIL detector-golden ({mode})", file=sys.stderr)
    for clip in results:
        if clip.get("fail") or clip.get("error"):
            print(f"  {clip.get('id')}: {clip.get('fail') or clip.get('error')}", file=sys.stderr)
    return 1 if args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
