"""Unified storage quota trim (Frigate RecordingCleanup / StorageMaintainer parity)."""

from __future__ import annotations

from app_config.app_config import app_config
from services.retention_service import retention_deletion_pending, run_retention


def _retention_mode() -> str:
    return str(app_config.get("retention.mode") or "cascade").strip().lower()


def quota_deletion_pending() -> tuple[bool, str]:
    """True when recordings exceed days or max_gb policy."""
    mode = _retention_mode()
    if mode == "disabled":
        return False, ""
    return retention_deletion_pending(mode=mode)


def run_quota_trim(*, dry_run: bool = False, policy_scope: str | None = None) -> tuple[int, int]:
    """Trim oldest/expired sessions until policy satisfied. Returns (deleted_count, freed_bytes)."""
    mode = _retention_mode()
    if mode == "disabled":
        return 0, 0
    return run_retention(dry_run=dry_run, mode=mode, policy_scope=policy_scope)
