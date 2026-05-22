"""Загрузка class_maps/*.yaml и применение allowlist + detector_scope в рантайме."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

logger = logging.getLogger(__name__)


def _map_path_for_binary(processor_root: str, binary_path: str) -> Path | None:
    stem = Path(str(binary_path or "").strip()).stem
    if not stem:
        return None
    for base in (
        Path(processor_root) / "models" / "detection" / "class_maps",
        Path(processor_root) / "models" / "detection" / "weights",
    ):
        candidate = base / f"{stem}.yaml"
        if candidate.is_file():
            return candidate
    maps_dir = Path(processor_root) / "models" / "detection" / "class_maps"
    direct = maps_dir / f"{stem}.yaml"
    return direct if direct.is_file() else None


def _normalize_scope_keys(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("", "all"):
            return []
        return [s]
    if isinstance(raw, (list, tuple)):
        return [str(x).strip().lower() for x in raw if str(x).strip()]
    return []


def resolve_allowed_class_ids(cfg: Mapping[str, Any]) -> list[int]:
    """Разрешённые class id из our_scope + class_to_scope минус ignore_class_ids."""
    names = cfg.get("native_names") or {}
    if not isinstance(names, Mapping):
        names = {}
    ignore: set[int] = set()
    for item in cfg.get("ignore_class_ids") or []:
        try:
            ignore.add(int(item))
        except (TypeError, ValueError):
            continue

    scope_keys = _normalize_scope_keys(cfg.get("our_scope"))
    cts = cfg.get("class_to_scope") or {}
    if not isinstance(cts, Mapping):
        cts = {}

    allowed: set[int] = set()
    if scope_keys:
        for key in scope_keys:
            for cid in cts.get(key) or []:
                try:
                    allowed.add(int(cid))
                except (TypeError, ValueError):
                    continue
    elif ignore and names:
        for key in names:
            try:
                cid = int(key)
            except (TypeError, ValueError):
                continue
            if cid not in ignore:
                allowed.add(cid)
    allowed -= ignore
    return sorted(allowed)


def resolve_detector_scope_labels(cfg: Mapping[str, Any], allowed_ids: list[int]) -> list[str]:
    names = cfg.get("native_names") or {}
    if not isinstance(names, Mapping):
        return []
    out: list[str] = []
    for cid in allowed_ids:
        label = names.get(cid) or names.get(str(cid))
        if label is None:
            continue
        out.append(str(label).strip())
    return out


def load_detector_class_map(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def apply_class_map_to_config(app_config: Any, processor_root: str, binary_path: str) -> bool:
    """
    Если есть class_maps/<stem>.yaml — выставить allowlist и detector_scope из карты.
    Возвращает True, если карта применена.
    """
    map_path = _map_path_for_binary(processor_root, binary_path)
    if map_path is None:
        return False
    cfg = load_detector_class_map(map_path)
    allowed = resolve_allowed_class_ids(cfg)
    if not allowed:
        logger.warning("detector class map %s: no allowed class ids", map_path)
        return False
    scope_labels = resolve_detector_scope_labels(cfg, allowed)
    if not scope_labels:
        logger.warning("detector class map %s: empty scope labels", map_path)
        return False

    app_config.set("processor.binary_predict_class_allowlist", allowed)
    app_config.set("processor.detector_scope", scope_labels)
    app_config.set("processor.detector_native_class_labels", True)
    logger.info(
        "detector class map applied: %s allowlist=%s scope=%s ignore=%s",
        map_path.name,
        allowed,
        scope_labels,
        list(cfg.get("ignore_class_ids") or []),
    )
    return True
