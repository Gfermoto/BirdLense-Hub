#!/usr/bin/env python3
"""Hub-only SOTA baseline: named_share excluding Frigate-sourced rows.

Reads ``recording_session_summary`` JSON lines from stdin (or ``--ssh`` Orin logs)
and prints aggregate named_share vs named_share_hub.

Examples:
  ssh host 'docker logs birdlense --since 24h' | python3 scripts/hub_only_baseline.py
  python3 scripts/hub_only_baseline.py --ssh gfer@192.168.1.153 --since 24h
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from typing import Any


_FRIGATE_REASONS = frozenset(
    {
        "promoted_by_frigate",
        "frigate_standalone",
        "frigate_standalone_excluded",
        "frigate_trigger_named_accept",
        "review_only_frigate_trigger_salvage",
    }
)
_GENERIC = frozenset({"bird", "unknown", "unknown bird", "rodent", "squirrel", ""})


def _is_named(name: str) -> bool:
    return str(name or "").strip().lower() not in _GENERIC


def _frigate_reason(reason: str) -> bool:
    return str(reason or "").strip().lower() in _FRIGATE_REASONS


def _parse_summaries(lines: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in lines:
        if "recording_session_summary" not in line:
            continue
        i = line.find("{")
        if i < 0:
            continue
        try:
            out.append(json.loads(line[i:]))
        except json.JSONDecodeError:
            continue
    return out


def _aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    hub_named = hub_total = mixed_named = mixed_total = 0
    vq_hub: list[float] = []
    vq_mixed: list[float] = []
    for s in summaries:
        vq = s.get("visit_quality") or {}
        if isinstance(vq, dict):
            if vq.get("named_share_hub") is not None:
                vq_hub.append(float(vq["named_share_hub"]))
            if vq.get("named_share") is not None:
                vq_mixed.append(float(vq["named_share"]))
            hub_named += int(vq.get("hub_named_rows") or 0)
            hub_total += int(vq.get("hub_persisted_rows") or 0)
            mixed_named += int(vq.get("named_rows") or 0)
            mixed_total += int(vq.get("persisted_rows") or 0)
        for k, v in ((s.get("trigger_graph") or {}).get("decision_reason_counts") or {}).items():
            try:
                reasons[str(k)] += int(v or 0)
            except (TypeError, ValueError):
                pass

    frigate_reasons = sum(c for r, c in reasons.items() if _frigate_reason(r))
    hub_reasons = sum(c for r, c in reasons.items() if not _frigate_reason(r))
    return {
        "sessions": len(summaries),
        "named_share_hub_from_vq": (round(hub_named / hub_total, 4) if hub_total else None),
        "named_share_mixed_from_vq": (round(mixed_named / mixed_total, 4) if mixed_total else None),
        "vq_named_share_hub_mean": (round(sum(vq_hub) / len(vq_hub), 4) if vq_hub else None),
        "vq_named_share_mixed_mean": (round(sum(vq_mixed) / len(vq_mixed), 4) if vq_mixed else None),
        "hub_persisted_rows": hub_total,
        "hub_named_rows": hub_named,
        "decision_reason_hubish": hub_reasons,
        "decision_reason_frigate": frigate_reasons,
        "top_reasons": reasons.most_common(12),
        "slo_named_share_hub_ge_0_40": (
            None
            if hub_total == 0
            else bool((hub_named / hub_total) >= 0.40)
        ),
        "verdict": "hold",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ssh", default="", help="host for remote docker logs")
    ap.add_argument("--since", default="24h", help="docker logs --since")
    ap.add_argument("--json-out", default="", help="optional path to write JSON")
    args = ap.parse_args()

    if args.ssh:
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            args.ssh,
            f"docker logs birdlense --since {args.since} 2>&1",
        ]
        raw = subprocess.check_output(cmd, text=True, errors="replace")
        lines = raw.splitlines()
    else:
        lines = sys.stdin.read().splitlines()

    payload = _aggregate(_parse_summaries(lines))
    payload["window"] = args.since
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
