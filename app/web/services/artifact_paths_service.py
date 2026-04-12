"""Пути к артефактам относительно корня репозитория (#265)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def repo_root_path() -> str:
    """Корень репо: на четыре уровня выше app/web/services/."""
    return str(Path(__file__).resolve().parent.parent.parent.parent)


def resolve_artifact_path(raw_path: str | None) -> str | None:
    path = str(raw_path or "").strip()
    if not path:
        return None
    if os.path.isabs(path):
        return path
    root = repo_root_path()
    candidates = [
        os.path.join(root, path),
        os.path.join(root, "app", path),
        os.path.join(root, "app", "processor", path),
        os.path.join(root, "app", "web", path),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def sha256_file(path: str | None) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def config_fingerprint(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
