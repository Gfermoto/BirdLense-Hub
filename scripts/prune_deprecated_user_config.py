#!/usr/bin/env python3
"""
Удалить из user_config.yaml устаревшие ключи (gallery, heimdall_url и др.).

Список ключей совпадает с DEPRECATED_USER_CONFIG_KEYS в system_config_audit_service,
плюс целиком удаляется верхнеуровневый блок ``gallery``, если остался после точечных удалений.

Примеры:
  python3 scripts/prune_deprecated_user_config.py --dry-run
  python3 scripts/prune_deprecated_user_config.py --path /root/BirdLense/app/app_config/user_config.yaml

Перед записью создаётся резервная копия ``<path>.bak`` (перезаписывается).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WEB_ROOT = _REPO_ROOT / "app" / "web"
if str(_WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_ROOT))

from services.system_config_audit_service import DEPRECATED_USER_CONFIG_KEYS  # noqa: E402


def _delete_dotted(cfg: dict, dotted: str) -> bool:
    parts = dotted.split(".")
    cur: dict = cfg
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            return False
        cur = nxt
    last = parts[-1]
    if last in cur:
        del cur[last]
        return True
    return False


def _prune_empty_dicts(node: dict) -> None:
    """Рекурсивно удалить пустые dict-значения (после вычищения листьев)."""
    if not isinstance(node, dict):
        return
    for k in list(node.keys()):
        v = node[k]
        if isinstance(v, dict):
            _prune_empty_dicts(v)
            if v == {}:
                del node[k]


def prune_user_config(cfg: dict) -> tuple[int, list[str]]:
    removed: list[str] = []
    for dotted in DEPRECATED_USER_CONFIG_KEYS:
        if _delete_dotted(cfg, dotted):
            removed.append(dotted)
    if isinstance(cfg.get("gallery"), dict):
        del cfg["gallery"]
        removed.append("gallery (entire block)")
    elif "gallery" in cfg:
        del cfg["gallery"]
        removed.append("gallery (non-dict removed)")
    _prune_empty_dicts(cfg)
    return len(removed), removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune deprecated keys from BirdLense user_config.yaml")
    parser.add_argument(
        "--path",
        default=str(_REPO_ROOT / "app" / "app_config" / "user_config.yaml"),
        help="Path to user_config.yaml",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes only, do not write")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        print("error: YAML root must be a mapping", file=sys.stderr)
        return 2
    before = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    n, keys = prune_user_config(data)
    after = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    if n == 0:
        print("no deprecated keys to remove")
    else:
        print(f"would remove {n} entries:")
        for k in keys:
            print(f"  - {k}")
    if before == after:
        print("no changes needed")
        return 0
    if args.dry_run:
        print("dry-run: not writing")
        return 0
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"wrote {path} (backup {bak})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
