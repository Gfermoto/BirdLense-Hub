#!/usr/bin/env python3
"""
Дописать в user_config.yaml отсутствующие ключи из default_config.yaml (рекурсивно).

Поведение как при ручном merge на VPS: значения в user не перезаписываются, добавляются
только отсутствующие ветки/ключи из default.

Локально:
  python3 scripts/merge_user_config_missing_keys.py --config-dir app/app_config
  python3 scripts/merge_user_config_missing_keys.py --config-dir app/app_config --write

На сервере (из корня репо, с рабочим SSH из deploy.local.sh):
  bash scripts/server-merge-user-config-missing-keys.sh
  bash scripts/server-merge-user-config-missing-keys.sh --write --restart
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    print("Нужен PyYAML: pip install pyyaml", file=sys.stderr)
    raise SystemExit(1) from e


def fill_missing_from_default(default: dict, user: dict) -> dict:
    """Добавить из default только те ключи, которых нет в user (рекурсивно)."""
    out = copy.deepcopy(user) if isinstance(user, dict) else {}
    if not isinstance(default, dict):
        return out
    for key, dval in default.items():
        if key not in out:
            out[key] = copy.deepcopy(dval)
        elif isinstance(dval, dict) and isinstance(out.get(key), dict):
            out[key] = fill_missing_from_default(dval, out[key])
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=root / "app" / "app_config",
        help="Каталог с default_config.yaml и user_config.yaml",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Записать user_config.yaml (иначе только сравнение)",
    )
    args = parser.parse_args()
    cfg_dir: Path = args.config_dir.resolve()
    default_path = cfg_dir / "default_config.yaml"
    user_path = cfg_dir / "user_config.yaml"

    if not default_path.is_file():
        print(f"Нет файла: {default_path}", file=sys.stderr)
        return 1
    with default_path.open(encoding="utf-8") as f:
        default_cfg = yaml.safe_load(f) or {}
    if not isinstance(default_cfg, dict):
        print("default_config.yaml: корень должен быть mapping", file=sys.stderr)
        return 1

    user_cfg: dict = {}
    if user_path.is_file():
        with user_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if raw is not None and not isinstance(raw, dict):
            print("user_config.yaml: корень должен быть mapping", file=sys.stderr)
            return 1
        user_cfg = raw or {}

    before = json.dumps(user_cfg, sort_keys=True, default=str)
    merged = fill_missing_from_default(default_cfg, user_cfg)
    after = json.dumps(merged, sort_keys=True, default=str)

    if before == after:
        print("Изменений нет: в user уже есть все ключи из default (по структуре).")
        return 0

    if not args.write:
        print(
            "Обнаружены отсутствующие ключи относительно default. "
            "Повторите с --write для записи user_config.yaml.",
        )
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    if user_path.is_file():
        bak = user_path.with_name(f"user_config.yaml.bak.merge-keys-{stamp}")
        bak.write_bytes(user_path.read_bytes())
        print(f"Резервная копия: {bak}")

    with user_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            merged,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    print(f"Записано: {user_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
