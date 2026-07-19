#!/usr/bin/env python3
"""Species / taxonomy golden gate (RC6).

Evaluates Hub-only labeled cases against ``RecognitionOutcome``.
Unlike ``pipeline_golden_gate.py`` (detector/tracks), this gate fails when
Bird/Unknown is treated as a taxonomy win or Frigate is counted as Hub go-metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "benchmarks/species_golden_cases.json"
REPORT_DIR = REPO / "docs/reports/pipeline_golden"


def _load_cases() -> dict:
    if not CASES.is_file():
        raise SystemExit(f"FAIL: missing {CASES}")
    return json.loads(CASES.read_text(encoding="utf-8"))


def _ensure_import_path() -> None:
    src = REPO / "app/processor/src"
    app = REPO / "app"
    for p in (str(src), str(app)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _check_case(case: dict) -> dict:
    from recognition_outcome import from_persist_row  # type: ignore

    case_id = str(case.get("id") or "?")
    row = case.get("row") or {}
    expect = case.get("expect") or {}
    outcome = from_persist_row(row)
    fail: list[str] = []

    want_kind = expect.get("kind")
    if want_kind is not None and outcome.kind.value != want_kind:
        fail.append(f"kind={outcome.kind.value} want={want_kind}")

    if "hub_taxonomy_win" in expect and outcome.hub_taxonomy_win != bool(expect["hub_taxonomy_win"]):
        fail.append(
            f"hub_taxonomy_win={outcome.hub_taxonomy_win} want={expect['hub_taxonomy_win']}"
        )

    want_auth = expect.get("authority")
    if want_auth is not None and outcome.authority != want_auth:
        fail.append(f"authority={outcome.authority} want={want_auth}")

    want_skip = expect.get("skip_reason")
    if want_skip is not None and outcome.skip_reason != want_skip:
        fail.append(f"skip_reason={outcome.skip_reason!r} want={want_skip!r}")

    return {
        "id": case_id,
        "ok": not fail,
        "fail": fail,
        "got": outcome.to_dict(),
    }


def _write_report(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "species_golden_latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Species golden gate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- product: `{payload.get('product')}`",
        f"- checked_at: `{payload.get('checked_at')}`",
        f"- cases: `{payload.get('case_count')}`",
    ]
    for row in payload.get("results") or []:
        status = "PASS" if row.get("ok") else "FAIL"
        extra = ""
        if row.get("fail"):
            extra = " — " + "; ".join(row["fail"])
        lines.append(f"- {row.get('id')}: {status}{extra}")
    (REPORT_DIR / "species_golden_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enforce", action="store_true", help="Exit 1 on failure")
    args = parser.parse_args()

    _ensure_import_path()
    payload_in = _load_cases()
    results = [_check_case(c) for c in (payload_in.get("cases") or [])]
    ok = all(r.get("ok") for r in results) and bool(results)

    payload = {
        "schema": "species_golden_gate@v1",
        "product": "taxonomy",
        "ok": ok,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "results": results,
        "cases_path": str(CASES.relative_to(REPO)),
    }
    _write_report(payload)

    if ok:
        print(f"PASS species-golden ({len(results)} cases, product=taxonomy)")
        return 0
    print("FAIL species-golden", file=sys.stderr)
    for row in results:
        if not row.get("ok"):
            print(f"  {row.get('id')}: {'; '.join(row.get('fail') or [])}", file=sys.stderr)
    return 1 if args.enforce else 0


if __name__ == "__main__":
    raise SystemExit(main())
