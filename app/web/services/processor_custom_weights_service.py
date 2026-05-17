"""Загрузка пользовательских весов YOLO (binary / classifier) и class_names.txt (#276).

Файлы только под DATA_DIR/custom_weights/; в user_config пишутся **абсолютные** пути,
т.к. относительные пути processor.models.* резолвятся от корня ``app/processor``, не от DATA_DIR.

Валидация .pt без torch: проверка zip-структуры (типичный формат Ultralytics) или минимальный размер.
"""

from __future__ import annotations

import io
import hashlib
import logging
import os
import shutil
import tempfile
import zipfile
from typing import Any

from app_config.app_config import AppConfig, app_config
from data_paths import _data_dir
from services.openvino_weight_export_service import OV_BUNDLE_DIRNAME, export_binary_pt_to_openvino

logger = logging.getLogger(__name__)

CUSTOM_SUBDIR = "custom_weights"
BINARY_NAME = "binary.pt"
CLASSIFIER_NAME = "classifier.pt"
ALLOWLIST_NAME = "class_names.txt"

_MAX_PT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB
_MAX_TXT_BYTES = 32 * 1024 * 1024  # 32 MiB
_MIN_PT_BYTES = 4096


def _processor_root() -> str:
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(web_dir, "..", "processor"))


def _custom_dir() -> str:
    base = os.path.join(_data_dir(), CUSTOM_SUBDIR)
    os.makedirs(base, mode=0o755, exist_ok=True)
    return os.path.realpath(base)


def _canonical_file(name: str) -> str:
    return os.path.join(_custom_dir(), name)


def _resolve_model_path(rel_or_abs: str) -> str:
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(_processor_root(), rel_or_abs)


def effective_binary_path() -> str:
    """Путь для UI статуса/отпечатка: приоритет OpenVINO IR при наличии, иначе ``processor.models.binary``.

    Если ``inference_backend=openvino``, но IR не задан, резолвер даёт ``''``, хотя оператор уже
    загрузил ``binary.pt`` (ключ ``processor.models.binary``). Processor по-прежнему требует IR
    на старте; здесь нужен человекочитаемый слот метаданных и fingerprint загруженного .pt (#276).
    """
    root = _processor_root()
    from inference.binary_paths import (
        resolve_binary_detector_weight_path,
        resolve_relative_to_processor_root,
    )

    path, _backend = resolve_binary_detector_weight_path(app_config, root)
    path_stripped = str(path or "").strip()
    if path_stripped:
        return path_stripped
    default_bin = "models/detection/weights/yolo11n.pt"
    raw = app_config.get("processor.models.binary", default_bin)
    rel = str(raw).strip() if raw is not None else default_bin
    if not rel:
        rel = default_bin
    return resolve_relative_to_processor_root(rel, root)


def effective_classifier_path() -> str:
    from inference.classifier_paths import resolve_classifier_weight_path

    return resolve_classifier_weight_path(
        app_config,
        _processor_root(),
    )[0]


def effective_allowlist_path() -> str | None:
    from services.species_catalog_allowlist_service import resolve_allowlist_path

    return resolve_allowlist_path(app_config.get)


def _stat_slot(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    if os.path.isdir(path):
        from inference.binary_paths import openvino_bundle_fingerprint

        try:
            st = os.stat(path)
        except OSError:
            return None
        total = 0
        try:
            for fn in os.listdir(path):
                fp = os.path.join(path, fn)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        except OSError:
            pass
        return {
            "path": path,
            "bytes": total if total > 0 else None,
            "mtime_unix": int(st.st_mtime),
            "fingerprint_sha256_16": (openvino_bundle_fingerprint(path) or "")[:16] or None,
        }
    if not os.path.isfile(path):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return {
        "path": path,
        "bytes": st.st_size,
        "mtime_unix": int(st.st_mtime),
        "fingerprint_sha256_16": _sha256_16(path),
    }


def _sha256_16(path: str | None) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _is_under_custom_dir(path: str | None) -> bool:
    if not path:
        return False
    try:
        cdir = _custom_dir()
        rp = os.path.realpath(path)
        return rp == cdir or rp.startswith(cdir + os.sep)
    except OSError:
        return False


def _slot_info(effective: str, default_path: str) -> dict[str, Any]:
    st = _stat_slot(effective)
    out: dict[str, Any] = {
        "path": effective,
        "uses_custom_dir": _is_under_custom_dir(effective),
        "default_path": default_path,
        "bytes": None,
        "mtime_unix": None,
        "fingerprint_sha256_16": None,
    }
    if st:
        out["bytes"] = st["bytes"]
        out["mtime_unix"] = st["mtime_unix"]
        out["fingerprint_sha256_16"] = st["fingerprint_sha256_16"]
    return out


def _allowlist_slot() -> dict[str, Any]:
    ea = effective_allowlist_path()
    out: dict[str, Any] = {
        "path": ea,
        "uses_custom_dir": _is_under_custom_dir(ea),
        "bytes": None,
        "mtime_unix": None,
        "fingerprint_sha256_16": None,
    }
    if not ea:
        return out
    st = _stat_slot(ea)
    if st:
        out["bytes"] = st["bytes"]
        out["mtime_unix"] = st["mtime_unix"]
        out["fingerprint_sha256_16"] = st["fingerprint_sha256_16"]
    return out


def get_status() -> dict[str, Any]:
    """Сводка для UI: эффективные пути, встроенные дефолты, признак «наш» custom-файл."""
    from inference.selector import resolve_inference_backend

    def_bin = _resolve_model_path("models/detection/weights/yolo11n.pt")
    def_cls = _resolve_model_path("models/classification/weights/best.pt")
    eb = effective_binary_path()
    ec = effective_classifier_path()
    return {
        "custom_weights_dir": _custom_dir(),
        "inference_backend": resolve_inference_backend(app_config),
        "binary": _slot_info(eb, def_bin),
        "classifier": _slot_info(ec, def_cls),
        "allowlist": _allowlist_slot(),
    }


def _validate_pt_bytes(content: bytes) -> str | None:
    if len(content) < _MIN_PT_BYTES:
        return "file_too_small"
    if len(content) > _MAX_PT_BYTES:
        return "file_too_large"
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return "not_zip_checkpoint"
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as z:
            names = z.namelist()
    except zipfile.BadZipFile:
        return "bad_zip"
    if not names:
        return "empty_zip"
    return None


def _validate_class_names_text(content: bytes) -> str | None:
    if len(content) > _MAX_TXT_BYTES:
        return "file_too_large"
    if len(content) == 0:
        return "empty_file"
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return "not_utf8"
    lines = [ln.split("#", 1)[0].strip() for ln in text.splitlines() if ln.split("#", 1)[0].strip()]
    if not lines:
        return "no_class_lines"
    if len(lines) > 50_000:
        return "too_many_lines"
    return None


def save_upload(
    role: str,
    file_storage,
    *,
    acknowledge_classifier_only: bool = False,
) -> tuple[dict[str, Any], int]:
    """Сохранить multipart-файл и обновить user_config. Возвращает (body, http_code)."""
    role = (role or "").strip().lower()
    if role not in ("binary", "classifier", "class_names"):
        return {"error": "invalid_role"}, 400
    if file_storage is None or not getattr(file_storage, "filename", None):
        return {"error": "missing_file"}, 400

    raw = file_storage.read()
    if role in ("binary", "classifier"):
        ext = os.path.splitext(str(file_storage.filename).lower())[1]
        if ext != ".pt":
            return {"error": "expected_pt"}, 400
        err = _validate_pt_bytes(raw)
        if err:
            return {"error": err}, 400
        target_name = BINARY_NAME if role == "binary" else CLASSIFIER_NAME
        config_path = _canonical_file(target_name)
        user_key = "processor.models.binary" if role == "binary" else "processor.models.classifier"
    else:
        ext = os.path.splitext(str(file_storage.filename).lower())[1]
        if ext not in (".txt", ""):
            return {"error": "expected_txt"}, 400
        err = _validate_class_names_text(raw)
        if err:
            return {"error": err}, 400
        config_path = _canonical_file(ALLOWLIST_NAME)
        user_key = "species.catalog_allowlist_file"

    if role == "classifier" and not acknowledge_classifier_only:
        allow_path = effective_allowlist_path()
        if not allow_path or not os.path.isfile(allow_path):
            return {"error": "allowlist_missing_upload_class_names_or_ack"}, 400

    d = os.path.dirname(config_path)
    os.makedirs(d, mode=0o755, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, config_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    openvino_export: dict[str, Any] | None = None
    user = app_config.load_raw_user_config_dict()
    AppConfig._set_nested(user, user_key, config_path)
    if role == "binary":
        try:
            imgsz = int(app_config.get("processor.binary_imgsz") or 640)
        except (TypeError, ValueError):
            imgsz = 640
        ov_dir = os.path.join(_custom_dir(), OV_BUNDLE_DIRNAME)
        ov_path, ov_err = export_binary_pt_to_openvino(
            config_path,
            imgsz=imgsz,
            bundle_dir=ov_dir,
        )
        openvino_export = {
            "attempted": True,
            "ok": ov_err is None,
            "path": ov_path,
            "error": ov_err,
        }
        if ov_path:
            AppConfig._set_nested(user, "processor.models.binary_openvino", ov_path)
            AppConfig._set_nested(user, "processor.inference_backend", "openvino")
            if not str(user.get("processor", {}).get("inference_device") or "").strip():
                AppConfig._set_nested(user, "processor.inference_device", "intel:gpu")
    issues = app_config.validate_user_config_tree(user)
    if issues:
        try:
            os.remove(config_path)
        except OSError:
            pass
        return {"error": "config_validation_failed", "details": issues[:5]}, 400

    app_config._persist_raw_user_config(user)
    app_config.reload()
    from services.species_catalog_allowlist_service import clear_allowlist_cache

    clear_allowlist_cache()

    body: dict[str, Any] = {
        "ok": True,
        "path": config_path,
        "role": role,
        "status": get_status(),
    }
    if openvino_export is not None:
        body["openvino_export"] = openvino_export
    return body, 200


def reset_roles(roles: list[str]) -> tuple[dict[str, Any], int]:
    """Удалить файлы в custom_weights и снять переопределения в user_config для этих слотов."""
    want = {str(r).strip().lower() for r in roles if str(r).strip()}
    if not want:
        return {"error": "missing_roles"}, 400
    allowed = {"binary", "classifier", "class_names", "all"}
    if not want.issubset(allowed):
        return {"error": "invalid_role"}, 400

    if "all" in want:
        want = {"binary", "classifier", "class_names"}

    user = app_config.load_raw_user_config_dict()
    removed_files: list[str] = []

    def _maybe_remove_file(name: str) -> None:
        p = _canonical_file(name)
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed_files.append(p)
            except OSError as e:
                logger.warning("remove custom weight failed %s: %s", p, e)

    if "binary" in want:
        eb = effective_binary_path()
        if _is_under_custom_dir(eb):
            AppConfig._remove_nested(user, "processor.models.binary")
        ov_custom = _canonical_file(OV_BUNDLE_DIRNAME)
        if os.path.isdir(ov_custom):
            try:
                shutil.rmtree(ov_custom)
                removed_files.append(ov_custom)
            except OSError as e:
                logger.warning("remove custom openvino bundle failed %s: %s", ov_custom, e)
        bo = app_config.get("processor.models.binary_openvino")
        if bo and _is_under_custom_dir(str(bo)):
            AppConfig._remove_nested(user, "processor.models.binary_openvino")
        _maybe_remove_file(BINARY_NAME)

    if "classifier" in want:
        ec = effective_classifier_path()
        if _is_under_custom_dir(ec):
            AppConfig._remove_nested(user, "processor.models.classifier")
        _maybe_remove_file(CLASSIFIER_NAME)

    if "class_names" in want:
        ea = effective_allowlist_path()
        if _is_under_custom_dir(ea):
            AppConfig._remove_nested(user, "species.catalog_allowlist_file")
        _maybe_remove_file(ALLOWLIST_NAME)

    issues = app_config.validate_user_config_tree(user)
    if issues:
        return {"error": "config_validation_failed", "details": issues[:5]}, 400

    app_config._persist_raw_user_config(user)
    app_config.reload()
    from services.species_catalog_allowlist_service import clear_allowlist_cache

    clear_allowlist_cache()

    return {
        "ok": True,
        "removed_files": removed_files,
        "status": get_status(),
    }, 200
