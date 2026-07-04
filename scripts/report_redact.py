#!/usr/bin/env python3
"""Redact secrets from agent-generated markdown/JSON reports before save."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REDACTED = "[REDACTED]"

# Key=value / YAML / markdown label patterns (values only).
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)(admin\s+password|sudo\s+password|ssh\s+password|"
            r"settings_password|contributor_password|mqtt_password|"
            r"go2rtc_password|rtsp_password|password)\s*[:=]\s*\S+"
        ),
        r"\1: " + REDACTED,
    ),
    (
        re.compile(
            r"(?i)(FLASK_SECRET_KEY|PROCESSOR_SECRET|MCP_TOKEN|"
            r"BIRDLENSE_MCP_TOKEN|BIRDLENSE_METRICS_TOKEN|"
            r"ebird_api_key|openweather_api_key|api_key|token|secret)\s*[:=]\s*\S+"
        ),
        r"\1=" + REDACTED,
    ),
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]{8,}"), "Bearer " + REDACTED),
    (re.compile(r"rtsp://[^:\s]+:[^@\s]+@"), "rtsp://[REDACTED]:[REDACTED]@"),
    (re.compile(r"sshpass\s+-e\s+ssh"), "ssh"),  # drop sshpass hint lines
    (re.compile(r"export\s+SSHPASS=['\"][^'\"]+['\"]"), "export SSHPASS=" + REDACTED),
]


def redact_text(text: str) -> tuple[str, int]:
    """Return redacted text and number of substitutions."""
    total = 0
    out = text
    for pattern, repl in _PATTERNS:
        out, n = pattern.subn(repl, out)
        total += n
    return out, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="File to check or redact")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if secrets detected (no write)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite file with redacted content",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read from stdin, write redacted text to stdout",
    )
    args = parser.parse_args()

    if args.stdin:
        raw = sys.stdin.read()
        redacted, n = redact_text(raw)
        sys.stdout.write(redacted)
        return 1 if n and args.check else 0

    if not args.path:
        parser.error("path required unless --stdin")

    path = Path(args.path)
    if not path.is_file():
        print(f"report_redact: file not found: {path}", file=sys.stderr)
        return 2

    raw = path.read_text(encoding="utf-8")
    redacted, n = redact_text(raw)

    if args.check and n:
        print(f"report_redact: {n} secret pattern(s) in {path}", file=sys.stderr)
        return 1

    if args.in_place and n:
        path.write_text(redacted, encoding="utf-8")
        print(f"report_redact: redacted {n} pattern(s) in {path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
