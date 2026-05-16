#!/usr/bin/env python3
"""
Глубокое слияние YAML-фрагмента в user_config.yaml (patch перекрывает user).

Локально:
  python3 scripts/apply_user_config_patch.py \\
    --config-dir app/app_config \\
    --patch scripts/user-config-recall-hotfix.partial.yaml --write

На сервере (патч в volume app_config, скрипт через stdin):
  см. scripts/server-apply-user-config-recall-patch.sh
"""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    print("Нужен PyYAML: pip install pyyaml", file=sys.stderr)
    raise SystemExit(1) from e


def deep_merge_overwrite(base: dict, patch: dict) -> dict:
    """Рекурсивно: ключи из patch заменяют/дополняют base."""
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(patch, dict):
        return out
    for key, pval in patch.items():
        if isinstance(pval, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_overwrite(out[key], pval)
        else:
            out[key] = copy.deepcopy(pval)
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=root / "app" / "app_config",
        help="Каталог с user_config.yaml",
    )
    parser.add_argument(
        "--patch",
        type=Path,
        required=True,
        help="YAML-фрагмент (только перекрываемые ключи)",
    )
    parser.add_argument("--write", action="store_true", help="Записать user_config.yaml")
    args = parser.parse_args()

    cfg_dir: Path = args.config_dir.resolve()
    user_path = cfg_dir / "user_config.yaml"
    patch_path: Path = args.patch.resolve()

    if not patch_path.is_file():
        print(f"Нет файла патча: {patch_path}", file=sys.stderr)
        return 1
    with patch_path.open(encoding="utf-8") as f:
        patch_cfg = yaml.safe_load(f) or {}
    if not isinstance(patch_cfg, dict):
        print("Патч: корень должен быть mapping", file=sys.stderr)
        return 1

    user_cfg: dict = {}
    if user_path.is_file():
        with user_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if raw is not None and not isinstance(raw, dict):
            print("user_config.yaml: корень должен быть mapping", file=sys.stderr)
            return 1
        user_cfg = raw or {}
    else:
        print(f"Нет user_config.yaml: {user_path}", file=sys.stderr)
        return 1

    merged = deep_merge_overwrite(user_cfg, patch_cfg)

    import json

    if json.dumps(user_cfg, sort_keys=True, default=str) == json.dumps(merged, sort_keys=True, default=str):
        print("Изменений нет (уже совпадает с патчем).")
        return 0

    if not args.write:
        print("Есть отличия. Повторите с --write.")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    bak = user_path.with_name(f"user_config.yaml.bak.patch-{stamp}")
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
