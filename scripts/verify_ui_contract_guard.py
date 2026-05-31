#!/usr/bin/env python3
"""Verify OpenAPI -> generated TS -> UI typecheck contract integrity (#538)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
UI = REPO / "app" / "ui"
GEN_PATH = REPO / "app" / "ui" / "src" / "generated" / "openapi-types.ts"


def _run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        out = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (out.stdout or out.stderr or "").strip()
    except subprocess.CalledProcessError as exc:
        data = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return False, data.strip()


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_results(
    *,
    codegen_ok: bool,
    changed: bool,
    typecheck_ok: bool,
) -> dict[str, Any]:
    ok = bool(codegen_ok and not changed and typecheck_ok)
    return {
        "schema": "ui_contract_guard@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": {
            "codegen_ok": bool(codegen_ok),
            "generated_file_changed": bool(changed),
            "typecheck_ok": bool(typecheck_ok),
        },
        "ok": ok,
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    return "\n".join(
        [
            "# UI Contract Guard",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- ok: `{report.get('ok')}`",
            "",
            "## Checks",
            "",
            f"- codegen_ok: `{checks.get('codegen_ok')}`",
            (
                "- generated_file_changed: "
                f"`{checks.get('generated_file_changed')}`"
            ),
            f"- typecheck_ok: `{checks.get('typecheck_ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-json",
        default="docs/reports/ui_contract/ui_contract_guard_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/ui_contract/ui_contract_guard_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    before = _sha256_file(GEN_PATH)
    codegen_ok, _ = _run(["npm", "run", "codegen:openapi"], UI)
    after = _sha256_file(GEN_PATH)
    changed = bool(before != after)
    typecheck_ok, _ = _run(["npm", "run", "typecheck"], UI)
    report = evaluate_results(
        codegen_ok=codegen_ok,
        changed=changed,
        typecheck_ok=typecheck_ok,
    )
    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
