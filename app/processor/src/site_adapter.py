"""SiteAdapter learning loop (RC5 / Bet A).

Review corrections → versioned adapter under data/site_adapter/.
Thin runtime apply: species confidence priors + optional weights file presence.
LoRA/ONNX weight load stays future work — priors are the first closed loop.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
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
    # Additive confidence deltas keyed by lowercased species common name.
    species_priors: tuple[tuple[str, float], ...] = ()
    # Optional relative path under adapter_dir (weights present ⇒ canary-ready apply path).
    weights_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "source": self.source,
            "status": self.status,
            "notes": self.notes,
            "canary_share": self.canary_share,
            "species_priors": dict(self.species_priors),
            "weights_file": self.weights_file,
        }

    def priors_map(self) -> dict[str, float]:
        return {str(k).strip().lower(): float(v) for k, v in self.species_priors if str(k).strip()}


def adapter_dir(data_dir: str | Path) -> Path:
    return Path(data_dir) / ADAPTER_DIRNAME


def _parse_priors(raw: Any) -> tuple[tuple[str, float], ...]:
    if not isinstance(raw, Mapping):
        return ()
    out: list[tuple[str, float]] = []
    for key, val in raw.items():
        name = str(key or "").strip().lower()
        if not name:
            continue
        try:
            delta = float(val)
        except (TypeError, ValueError):
            continue
        out.append((name, delta))
    return tuple(out)


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
        weights = raw.get("weights_file")
        return SiteAdapterManifest(
            version=str(raw.get("version") or "0"),
            created_at=str(raw.get("created_at") or ""),
            source=str(raw.get("source") or "unknown"),
            status=str(raw.get("status") or STATUS_INACTIVE),
            notes=(str(raw["notes"]) if raw.get("notes") is not None else None),
            canary_share=float(raw.get("canary_share") or 0.0),
            species_priors=_parse_priors(raw.get("species_priors")),
            weights_file=(str(weights).strip() or None) if weights is not None else None,
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
    species_priors: Mapping[str, float] | None = None,
    weights_file: str | None = None,
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
        species_priors=_parse_priors(species_priors or {}),
        weights_file=(str(weights_file).strip() or None) if weights_file else None,
    )
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def weights_present(data_dir: str | Path, manifest: SiteAdapterManifest | None = None) -> bool:
    m = manifest if manifest is not None else load_site_adapter(data_dir)
    if m is None or not m.weights_file:
        return False
    return (adapter_dir(data_dir) / m.weights_file).is_file()


def _runtime_apply_mode(manifest: SiteAdapterManifest | None, data_dir: str | Path) -> str:
    if manifest is None:
        return "noop_until_adapter_weights"
    has_priors = bool(manifest.species_priors)
    has_weights = weights_present(data_dir, manifest)
    if has_priors and has_weights:
        return "priors_and_weights_file"
    if has_priors:
        return "species_priors"
    if has_weights:
        return "weights_file_present"
    return "noop_until_adapter_weights"


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
            "has_species_priors": False,
            "has_weights_file": False,
        }
    return {
        "present": True,
        "status": manifest.status,
        "version": manifest.version,
        "created_at": manifest.created_at,
        "source": manifest.source,
        "canary_share": manifest.canary_share,
        "canary_ready": manifest.status in {STATUS_CANARY, STATUS_ACTIVE},
        "runtime_apply": _runtime_apply_mode(manifest, data_dir),
        "has_species_priors": bool(manifest.species_priors),
        "has_weights_file": weights_present(data_dir, manifest),
        "notes": manifest.notes,
    }


def canary_selected_for_track(
    manifest: SiteAdapterManifest,
    track_id: Any = None,
) -> bool:
    """Deterministic canary bucket for a track."""
    if manifest.status == STATUS_INACTIVE:
        return False
    share = float(manifest.canary_share)
    if manifest.status == STATUS_ACTIVE and share <= 0.0:
        share = 1.0
    if share <= 0.0:
        return False
    if share >= 1.0:
        return True
    key = f"{manifest.version}:{track_id if track_id is not None else ''}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    return bucket < share


def apply_site_adapter_canary(
    *,
    data_dir: str | Path,
    track_id: Any = None,
) -> bool:
    """True when this track should receive site-adapter adjustments."""
    manifest = load_site_adapter(data_dir)
    if manifest is None:
        return False
    if not canary_selected_for_track(manifest, track_id):
        return False
    return bool(manifest.species_priors) or weights_present(data_dir, manifest)


def adjust_confidence_with_site_adapter(
    *,
    data_dir: str | Path,
    species: str | None,
    confidence: float,
    track_id: Any = None,
) -> tuple[float, dict[str, Any]]:
    """Apply species prior delta when canary selected. Returns (confidence, info)."""
    info: dict[str, Any] = {"applied": False}
    try:
        base = float(confidence)
    except (TypeError, ValueError):
        base = 0.0
    manifest = load_site_adapter(data_dir)
    if manifest is None or not canary_selected_for_track(manifest, track_id):
        return max(0.0, min(1.0, base)), info
    name = str(species or "").strip().lower()
    delta = manifest.priors_map().get(name, 0.0) if name else 0.0
    if delta == 0.0 and not weights_present(data_dir, manifest):
        return max(0.0, min(1.0, base)), info
    adjusted = max(0.0, min(1.0, base + float(delta)))
    info = {
        "applied": delta != 0.0,
        "version": manifest.version,
        "status": manifest.status,
        "species": name or None,
        "delta": float(delta),
        "confidence_before": base,
        "confidence_after": adjusted,
        "weights_file": bool(weights_present(data_dir, manifest)),
    }
    return adjusted, info
