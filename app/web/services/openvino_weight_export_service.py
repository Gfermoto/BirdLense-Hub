"""Экспорт бинарного YOLO ``.pt`` в OpenVINO IR (Ultralytics) после загрузки через UI (#276)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

OV_BUNDLE_DIRNAME = "binary_openvino_model"


def export_binary_pt_to_openvino(
    pt_path: str,
    *,
    imgsz: int = 640,
    bundle_dir: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Экспорт ``pt_path`` → каталог IR с ``*.xml``.

    Returns:
        (absolute_openvino_dir, None) on success;
        (None, error_code) on failure.
    """
    pt = Path(pt_path).resolve()
    if not pt.is_file():
        return None, "pt_missing"

    try:
        imgsz_i = int(imgsz)
    except (TypeError, ValueError):
        imgsz_i = 640
    imgsz_i = max(32, min(1280, imgsz_i))

    target = Path(bundle_dir).resolve() if bundle_dir else pt.parent / OV_BUNDLE_DIRNAME
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    try:
        from ultralytics import YOLO
    except ImportError:
        return None, "ultralytics_not_available"

    try:
        YOLO(str(pt)).export(format="openvino", imgsz=imgsz_i, simplify=True)
    except Exception:
        logger.exception("OpenVINO export failed for %s", pt)
        return None, "openvino_export_failed"

    found = _find_openvino_bundle(pt)
    if not found:
        return None, "openvino_export_no_xml"

    if found.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(found), str(target))

    if not list(target.glob("*.xml")):
        return None, "openvino_export_no_xml"

    return str(target), None


def _find_openvino_bundle(pt_path: Path) -> Path | None:
    """Каталог IR рядом с ``.pt`` (Ultralytics: ``{stem}_openvino_model``)."""
    parent = pt_path.parent
    expected = parent / f"{pt_path.stem}_openvino_model"
    if expected.is_dir() and list(expected.glob("*.xml")):
        return expected
    for candidate in sorted(parent.iterdir(), key=lambda p: p.name):
        if not candidate.is_dir():
            continue
        if candidate.name.endswith("_openvino_model") and list(candidate.glob("*.xml")):
            return candidate
    return None
