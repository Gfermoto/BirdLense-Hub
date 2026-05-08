"""Резолв пути к YAML трекера Ultralytics.

Встроенное имя (bytetrack.yaml) vs ``models/tracker/*.yaml`` под ``app/processor``.
"""

from __future__ import annotations

import os

from inference.binary_paths import processor_package_root


def resolve_tracker_config_path(raw: str | None) -> str:
    """Resolve tracker cfg: builtin name, absolute path, or under processor root."""
    t = str(raw or '').strip() or 'bytetrack.yaml'
    if os.path.isfile(t):
        return os.path.abspath(t)
    root = processor_package_root()
    candidate = os.path.join(root, t.lstrip('/\\'))
    if os.path.isfile(candidate):
        return candidate
    return t
