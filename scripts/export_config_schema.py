#!/usr/bin/env python3
"""Export BirdLense merged-config JSON Schema (SOTA-01)."""

from __future__ import annotations

import sys

_APP_ROOT = __file__
for _ in range(2):
    _APP_ROOT = __import__("os").path.dirname(_APP_ROOT)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from app_config.config_schema import write_config_json_schema


def main() -> int:
    path = write_config_json_schema()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
