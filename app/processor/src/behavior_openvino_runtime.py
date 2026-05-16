"""Behavior logits via OpenVINO (ONNX/IR); softmax matches logistic baseline (#416)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

_log = logging.getLogger(__name__)

MappingLike = Any


def _softmax(logits: np.ndarray) -> np.ndarray:
    x = logits.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-12)


def _resolve_behavior_openvino_path(raw: str, *, processor_cwd: str | None) -> Path | None:
    """Resolve ONNX/XML path or first *.xml under directory."""
    p = (raw or "").strip()
    if not p:
        return None
    path = Path(p)
    suf = path.suffix.lower()
    if path.is_file() and suf in (".onnx", ".xml"):
        return path.resolve()
    if path.is_dir():
        for name in ("model.onnx", "behavior_logistic.onnx"):
            cand = (path / name).resolve()
            if cand.is_file():
                return cand
        xmls = sorted(path.glob("*.xml"))
        if xmls:
            return xmls[0].resolve()
        return None
    roots: list[Path] = []
    if processor_cwd:
        roots.append(Path(processor_cwd))
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        cand = (root / p).resolve()
        cs = cand.suffix.lower()
        if cand.is_file() and cs in (".onnx", ".xml"):
            return cand
        if cand.is_dir():
            for name in ("model.onnx", "behavior_logistic.onnx"):
                cp = (cand / name).resolve()
                if cp.is_file():
                    return cp
            xs = sorted(cand.glob("*.xml"))
            if xs:
                return xs[0].resolve()
            break
    env = (os.environ.get("BIRDLENSE_BEHAVIOR_OPENVINO_PATH") or "").strip()
    if env:
        pe = Path(env).expanduser()
        if pe.is_file():
            return pe.resolve()
    return None


class BehaviorOpenvinoRuntime:
    """Single compiled model per process (finalize is single-threaded)."""

    def __init__(self) -> None:
        self._compiled: Any = None
        self._input_name: str | None = None
        self._output_idx = 0
        self._model_key: str | None = None
        self._labels: list[str] | None = None

    def load_if_needed(
        self,
        onnx_or_xml: Path,
        labels: list[str],
        *,
        app_config: MappingLike | None,
    ) -> bool:
        """Compile OpenVINO model if path or labels changed."""
        key = f"{onnx_or_xml.resolve()}|{','.join(labels)}"
        if self._compiled is not None and self._model_key == key:
            self._labels = list(labels)
            return True
        try:
            import openvino as ov

            from inference.selector import (
                openvino_runtime_available,
                resolve_classifier_inference_device,
                resolve_openvino_device_policy,
            )
        except ImportError as e:
            _log.warning("behavior openvino: import failed (%s)", e)
            return False

        if not openvino_runtime_available():
            return False

        core = ov.Core()
        try:
            model = core.read_model(str(onnx_or_xml))
            compiled = None
            raw_dev = resolve_classifier_inference_device(app_config) or ""
            for dev in resolve_openvino_device_policy(raw_dev or "auto"):
                try:
                    compiled = core.compile_model(model, dev)
                    break
                except Exception:
                    continue
            if compiled is None:
                compiled = core.compile_model(model, "CPU")
            inp0 = compiled.inputs[0]
            self._compiled = compiled
            self._input_name = inp0.get_any_name()
            self._output_idx = 0
            self._model_key = key
            self._labels = list(labels)
            return True
        except Exception as exc:
            _log.warning("behavior openvino: failed to load %s (%s)", onnx_or_xml, exc)
            self._compiled = None
            self._model_key = None
            self._labels = None
            return False


_RUNTIME_OV = BehaviorOpenvinoRuntime()


def maybe_predict_video_behavior_openvino(
    app_config: Any,
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    processor_cwd: str | None,
    onnx_or_xml_path: Path,
    labels: list[str],
    max_detections: int,
) -> tuple[str | None, float]:
    """Infer logits via OpenVINO; label order matches JSON export."""
    from behavior_baseline_runtime import runtime_meta_features

    if not labels or not video_detections:
        return None, 0.0
    if not _RUNTIME_OV.load_if_needed(onnx_or_xml_path, labels, app_config=app_config):
        return None, 0.0
    assert _RUNTIME_OV._compiled is not None
    assert _RUNTIME_OV._input_name is not None
    feats = runtime_meta_features(
        video_detections,
        duration_s=float(duration_s),
        max_detections=max_detections,
    )
    x = np.array([feats], dtype=np.float32)
    name = _RUNTIME_OV._input_name
    ov_out = _RUNTIME_OV._compiled({name: x})
    raw_out = ov_out[_RUNTIME_OV._compiled.outputs[_RUNTIME_OV._output_idx]]
    logits = np.asarray(raw_out, dtype=np.float64).reshape(-1)
    lab = _RUNTIME_OV._labels or labels
    if logits.shape[0] != len(lab):
        _log.warning(
            "behavior openvino: logits dim %s != n_labels %s",
            logits.shape[0],
            len(lab),
        )
        return None, 0.0
    probs = _softmax(logits)
    idx = int(np.argmax(probs))
    return lab[idx], float(probs[idx])


def resolve_behavior_openvino_model_path(
    app_config: Any,
    *,
    processor_cwd: str | None,
) -> Path | None:
    """Resolve from processor.models.behavior_openvino."""
    raw = ""
    if app_config is not None:
        raw = str(app_config.get("processor.models.behavior_openvino") or "").strip()
    return _resolve_behavior_openvino_path(raw, processor_cwd=processor_cwd)
