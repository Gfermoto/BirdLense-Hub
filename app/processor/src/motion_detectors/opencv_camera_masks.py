"""Per-camera OpenCV motion mask specs (Frigate-style polygon strings)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _mask_specs_from_raw(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue
        if isinstance(item, dict):
            coords = str(item.get("coordinates") or "").strip()
            if coords:
                out.append(coords)
    return out


def resolve_opencv_mask_specs(
    *,
    camera_id: str | None,
    cameras_config: Iterable[Mapping[str, Any]] | None,
) -> list[str]:
    """OpenCV masks only from ``video.cameras[].opencv_masks`` (no global fallback)."""
    cam_key = str(camera_id or "").strip()
    if not cam_key or not cameras_config:
        return []
    for row in cameras_config:
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("id") or row.get("stream_name") or "").strip()
        if row_id != cam_key:
            continue
        return _mask_specs_from_raw(row.get("opencv_masks"))
    return []
