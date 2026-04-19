"""Нормализованный xyxy [0..1] из Frigate MQTT ``after`` (box / snapshot / region)."""

from __future__ import annotations


def _as_four_floats(seq) -> tuple[float, float, float, float] | None:
    if not isinstance(seq, (list, tuple)) or len(seq) < 4:
        return None
    try:
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except (TypeError, ValueError):
        return None


def _frame_dimensions(after: dict) -> tuple[float, float] | None:
    fs = after.get("frame_shape")
    if isinstance(fs, (list, tuple)) and len(fs) >= 2:
        try:
            h = float(fs[0])
            w = float(fs[1])
            if w > 1.0 and h > 1.0:
                return w, h
        except (TypeError, ValueError):
            pass
    pairs = (("width", "height"), ("frame_width", "frame_height"))
    for wk, hk in pairs:
        try:
            w = float(after.get(wk) or 0.0)
            h = float(after.get(hk) or 0.0)
            if w > 1.0 and h > 1.0:
                return w, h
        except (TypeError, ValueError):
            continue
    return None


def _normalize_xyxy(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    fw: float | None,
    fh: float | None,
) -> list[float] | None:
    if x2 <= x1 or y2 <= y1:
        return None
    m = max(x1, y1, x2, y2)
    if m <= 1.000001:
        nx1 = max(0.0, min(1.0, x1))
        ny1 = max(0.0, min(1.0, y1))
        nx2 = max(0.0, min(1.0, x2))
        ny2 = max(0.0, min(1.0, y2))
        if nx2 <= nx1 or ny2 <= ny1:
            return None
        return [nx1, ny1, nx2, ny2]
    if fw and fh and fw > 0 and fh > 0:
        return _normalize_xyxy(x1 / fw, y1 / fh, x2 / fw, y2 / fh, 1.0, 1.0)
    return None


def _bbox_from_object(obj: dict, fw: float | None, fh: float | None) -> list[float] | None:
    box = obj.get("box")
    t4 = _as_four_floats(box)
    if t4:
        return _normalize_xyxy(*t4, fw, fh)

    region = obj.get("region")
    t4 = _as_four_floats(region)
    if not t4:
        return None
    x1, y1, a, b = t4
    # Сначала как xyxy (типично для полного кадра / snapshot).
    res = _normalize_xyxy(x1, y1, a, b, fw, fh)
    if res:
        return res
    # xywh в пикселях
    w_box, h_box = a, b
    if w_box > 0 and h_box > 0:
        return _normalize_xyxy(x1, y1, x1 + w_box, y1 + h_box, fw, fh)
    return None


def frigate_after_to_normalized_xyxy(after: dict | None) -> list[float] | None:
    """
    Вернуть [x1,y1,x2,y2] в долях кадра (0..1) или None.

    Порядок: ``after.box`` / ``after.region``, затем ``after.snapshot`` (те же поля).
    Размеры кадра: ``frame_shape`` [h,w], иначе width/height на том же объекте.
    """
    if not isinstance(after, dict):
        return None
    dims = _frame_dimensions(after)
    fw, fh = (dims[0], dims[1]) if dims else (None, None)
    r = _bbox_from_object(after, fw, fh)
    if r:
        return r
    snap = after.get("snapshot")
    if isinstance(snap, dict):
        snap_dims = _frame_dimensions(snap)
        sw, sh = (snap_dims[0], snap_dims[1]) if snap_dims else (None, None)
        r = _bbox_from_object(snap, sw or fw, sh or fh)
        if r:
            return r
    return None
