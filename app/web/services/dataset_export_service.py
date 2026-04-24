"""Shim: реализация в ``services.dataset_export.export_core`` (#344 фаза C).

Сохраняйте импорты ``from services.dataset_export_service import …`` и ``from services import dataset_export_service``.
"""

from __future__ import annotations

from services.dataset_export.export_core import *  # noqa: F401,F403
from services.dataset_export import export_core as _export_core

__all__ = list(_export_core.__all__)
