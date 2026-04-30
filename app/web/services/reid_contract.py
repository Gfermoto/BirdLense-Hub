"""Shared constants/helpers for offline Re-ID embeddings sidecar (#389)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EMBEDDING_SCHEMA_V1 = "embedding_schema@v1"


def parse_iso_utc(ts: str | None) -> datetime | None:
    """Parse ISO timestamps from embedding JSONL into UTC-aware datetimes."""
    if not ts:
        return None
    raw = str(ts).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def embedding_age_hours(
    created_at: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    """Return embedding age in whole hours (UTC), or None if timestamp is invalid."""
    dt = parse_iso_utc(created_at)
    if not dt:
        return None
    ref = now or datetime.now(timezone.utc)
    return max(0.0, (ref - dt).total_seconds() / 3600.0)


def stable_sha16_from_strings(parts: list[str]) -> str:
    """Short SHA256 fingerprint over joined string parts (testing/helpers)."""
    import hashlib

    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def stable_sha16_from_bytes(data: bytes) -> str:
    """Short SHA256 fingerprint over raw bytes (crop fingerprint)."""
    import hashlib

    return hashlib.sha256(data).hexdigest()[:16]


def stable_sha16_from_state_dict(state_dict: dict[str, Any]) -> str:
    """Deterministic fingerprint for torch weights without relying on file paths."""
    import hashlib

    h = hashlib.sha256()
    for k in sorted(state_dict.keys()):
        h.update(str(k).encode("utf-8"))
        h.update(b":")
        v = state_dict[k]
        try:
            import torch

            if torch.is_tensor(v):
                vv = v.detach().cpu().contiguous().view(-1)[:4096]
                h.update(vv.numpy().tobytes())
                h.update(str(tuple(v.shape)).encode("utf-8"))
                h.update(str(v.dtype).encode("utf-8"))
                continue
        except Exception:
            pass
        h.update(str(type(v)).encode("utf-8"))
        h.update(b";")
    return h.hexdigest()[:16]
