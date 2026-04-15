#!/usr/bin/env python3
"""One-off: build zh.json from en.json via Google Translate (Simplified Chinese). Preserves {{i18n}} placeholders."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "app" / "ui" / "locales" / "en.json"
ZH_PATH = ROOT / "app" / "ui" / "locales" / "zh.json"

PH = re.compile(r"(\{\{[^}]+\}\})")


def mask_placeholders(s: str) -> tuple[str, dict[str, str]]:
    m: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        tok = f"⟦{len(m)}⟧"
        m[tok] = match.group(0)
        return tok

    return PH.sub(repl, s), m


def unmask(s: str, m: dict[str, str]) -> str:
    for tok, orig in m.items():
        s = s.replace(tok, orig)
    return s


def translate_leaf(translator: GoogleTranslator, s: str, *, delay: float) -> str:
    if not s:
        return s
    masked, mapping = mask_placeholders(s)
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            out = translator.translate(masked)
            time.sleep(delay)
            return unmask(out, mapping)
        except Exception as e:  # noqa: BLE001 — network/API flakes
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"translate failed after retries: {last_err!r}") from last_err


def walk(translator: GoogleTranslator, obj: object, delay: float, stats: list[int]) -> object:
    if isinstance(obj, dict):
        return {k: walk(translator, v, delay, stats) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(translator, x, delay, stats) for x in obj]
    if isinstance(obj, str):
        stats[0] += 1
        if stats[0] % 100 == 0:
            print(f"  … {stats[0]} strings", flush=True)
        return translate_leaf(translator, obj, delay=delay)
    return obj


def main() -> int:
    delay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.12
    print(f"Reading {EN_PATH}", flush=True)
    data = json.loads(EN_PATH.read_text(encoding="utf-8"))
    translator = GoogleTranslator(source="en", target="zh-CN")
    stats = [0]
    print(f"Translating to zh-CN (delay={delay}s between calls)…", flush=True)
    out = walk(translator, data, delay, stats)
    ZH_PATH.parent.mkdir(parents=True, exist_ok=True)
    ZH_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ZH_PATH} ({stats[0]} strings)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
