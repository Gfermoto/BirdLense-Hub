"""SiteAdapter learning loop scaffold (RC5 / Bet A).

Review corrections → versioned adapter manifest under data/site_adapter/.
Runtime canary apply is intentionally a no-op until a real adapter (LoRA /
prototype memory) lands — status is still a product KPI.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

ADAPTER_DIRNAME = "site_adapter"
MANIFEST_NAME = "manifest.json"
STATUS_INACTIVE = "inactive"
STATUS_CANARY = "canary"
STATUS_ACTIVE = "active"


@dataclass(frozen=True)
class SiteAdapterManifest:
    version: str
    created_at: str
    source: str
    status: str = STATUS_INACTIVE
    notes: str | None = None
    canary_share: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def adapter_dir(data_dir: str | Path) -> Path:
    return Path(data_dir) / ADAPTER_DIRNAME


def load_site_adapter(data_dir: str | Path) -> SiteAdapterManifest | None:
    path = adapter_dir(data_dir) / MANIFEST_NAME
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("site_adapter manifest unreadable: %s", path, exc_info=True)
        return None
    if not isinstance(raw, Mapping):
        return None
    try:
        return SiteAdapterManifest(
            version=str(raw.get("version") or "0"),
            created_at=str(raw.get("created_at") or ""),
            source=str(raw.get("source") or "unknown"),
            status=str(raw.get("status") or STATUS_INACTIVE),
            notes=(str(raw["notes"]) if raw.get("notes") is not None else None),
            canary_share=float(raw.get("canary_share") or 0.0),
        )
    except (TypeError, ValueError):
        return None


def write_site_adapter_manifest(
    data_dir: str | Path,
    *,
    version: str,
    source: str,
    status: str = STATUS_INACTIVE,
    notes: str | None = None,
    canary_share: float = 0.0,
) -> SiteAdapterManifest:
    """Persist a new/updated adapter manifest (export / ops path)."""
    root = adapter_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest = SiteAdapterManifest(
        version=str(version),
        created_at=datetime.now(timezone.utc).isoformat(),
        source=str(source),
        status=str(status or STATUS_INACTIVE),
        notes=notes,
        canary_share=max(0.0, min(1.0, float(canary_share))),
    )
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def site_adapter_status(data_dir: str | Path) -> dict[str, Any]:
    """Product KPI blob for feedback_loop / system health."""
    manifest = load_site_adapter(data_dir)
    if manifest is None:
        return {
            "present": False,
            "status": STATUS_INACTIVE,
            "version": None,
            "canary_ready": False,
            "runtime_apply": "noop_until_adapter_weights",
        }
    return {
        "present": True,
        "status": manifest.status,
        "version": manifest.version,
        "created_at": manifest.created_at,
        "source": manifest.source,
        "canary_share": manifest.canary_share,
        "canary_ready": manifest.status in {STATUS_CANARY, STATUS_ACTIVE},
        "runtime_apply": "noop_until_adapter_weights",
        "notes": manifest.notes,
    }


def apply_site_adapter_canary(
    *,
    data_dir: str | Path,
    track_id: Any = None,
) -> bool:
    """Return True if canary path should alter classify — always False until weights land."""
    _ = (data_dir, track_id)
    return False
