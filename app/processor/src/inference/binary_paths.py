"""Резолв пути к весам бинарного детектора (torch ``.pt`` vs OpenVINO IR, #371)."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Mapping


def processor_package_root() -> str:
    """Каталог ``app/processor`` (рядом ``models/``, ``src/``)."""
    inference_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(inference_dir)
    return os.path.dirname(src_dir)


def resolve_relative_to_processor_root(rel_or_abs: str, processor_root: str) -> str:
    """Абсолютный путь: как есть или относительно корня пакета процессора."""
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(processor_root, rel_or_abs)


def detector_weights_available(path: str) -> bool:
    """``.pt`` файл или каталог/IR OpenVINO (есть ``*.xml``)."""
    if os.path.isfile(path):
        return True
    if os.path.isdir(path):
        try:
            for fn in os.listdir(path):
                if fn.endswith(".xml"):
                    return True
        except OSError:
            return False
    return False


def resolve_binary_detector_weight_path(
    app_config: Mapping[str, Any],
    processor_root: str | None = None,
) -> tuple[str, str]:
    """
    Вернуть ``(абсолютный_путь, inference_backend)``.

    Для ``openvino`` без конфига/env путь может быть ``''``.
    Для ``auto``: предпочесть OpenVINO при наличии валидного IR и runtime, иначе torch.
    """
    from inference.selector import openvino_runtime_available, resolve_inference_backend

    root = processor_root if processor_root is not None else processor_package_root()
    requested_backend = resolve_inference_backend(app_config)
    env_ov = os.environ.get("BIRDLENSE_BINARY_OPENVINO_PATH") or ""
    binary_env_ov = env_ov.strip()
    if requested_backend in ("openvino", "auto"):
        if binary_env_ov:
            if os.path.isabs(binary_env_ov):
                p = binary_env_ov
            else:
                p = resolve_relative_to_processor_root(binary_env_ov, root)
        else:
            rel_ov = app_config.get("processor.models.binary_openvino")
            rel_ov_s = str(rel_ov).strip() if rel_ov is not None else ""
            if rel_ov_s:
                p = resolve_relative_to_processor_root(rel_ov_s, root)
            else:
                p = ""
        if requested_backend == "openvino":
            return (p, "openvino")
        if p and detector_weights_available(p) and openvino_runtime_available():
            return (p, "openvino")
    default_bin = "models/detection/weights/best.pt"
    rel = app_config.get("processor.models.binary", default_bin)
    p = resolve_relative_to_processor_root(str(rel).strip(), root)
    return (p, "torch")


def openvino_bundle_fingerprint(path: str | None) -> str | None:
    """
    Отпечаток OpenVINO: один ``.xml`` или каталог (SHA256 всех ``*.xml``).

    Имена файлов сортируются лексикографически.
    """
    if not path or not os.path.exists(path):
        return None
    if os.path.isfile(path):
        if not path.endswith(".xml"):
            return None
        return _sha256_file_path(path)
    if not os.path.isdir(path):
        return None
    try:
        xml_names = sorted(fn for fn in os.listdir(path) if fn.endswith(".xml"))
    except OSError:
        return None
    if not xml_names:
        return None
    h = hashlib.sha256()
    for name in xml_names:
        fp = os.path.join(path, name)
        if os.path.isfile(fp):
            h.update(name.encode("utf-8"))
            h.update(b"\x00")
            with open(fp, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
    return h.hexdigest()


def _sha256_file_path(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()
