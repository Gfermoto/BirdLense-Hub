"""HuggingFace EfficientNet-B2 bird species classifier (525 classes) + OpenVINO runtime."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

_log = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE = 0.3
UNKNOWN_BIRD_LABEL = "Unknown Bird"
SQUIRREL_SPECIES_LABEL = "Eurasian Red Squirrel"


def resolve_efficientnet_openvino_device(device: str | None) -> str:
    """
    Map hub device strings to OpenVINO plugin names.

    ``intel:gpu`` / ``igpu`` → ``GPU`` (Intel iGPU on VPS/LAN with ``/dev/dri``).
    """
    d = (device or "CPU").strip().lower()
    if d in ("", "cpu", "intel:cpu"):
        return "CPU"
    if d in ("gpu", "igpu", "intel:gpu", "intel_gpu", "gpu.0"):
        return "GPU"
    if d == "auto":
        return "AUTO"
    if d.upper().startswith("GPU"):
        return device.strip().upper().replace("INTEL:", "")
    return device.strip() or "CPU"


@dataclass(frozen=True)
class EfficientNetClassifierResult:
    species_name: str | None
    top1_confidence: float
    entropy: float
    top1_top2_margin: float


def _entropy_margin(probs: np.ndarray) -> tuple[float, float]:
    arr = np.asarray(probs, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return 0.0, 0.0
    p = np.clip(arr, 1e-12, 1.0)
    s = float(p.sum())
    if s <= 0:
        return 0.0, 0.0
    p = p / s
    ent = float(-np.sum(p * np.log(p)))
    if p.size < 2:
        return ent, float(p[0])
    top2 = np.partition(p, -2)[-2:]
    margin = float(np.max(top2) - np.min(top2))
    return ent, margin


def _normalize_species_label(name: str) -> str:
    return str(name or "").replace("_OR_", "/").replace("_", " ").strip()


class EfficientNetB2Classifier:
    """Species classifier on 224×224 BGR crops (Bird detector path only)."""

    def __init__(
        self,
        *,
        weights_dir: str,
        backend: str = "openvino",
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        unknown_label: str = UNKNOWN_BIRD_LABEL,
        device: str | None = None,
        regional_species: list[str] | None = None,
    ) -> None:
        self.weights_dir = str(weights_dir)
        self.backend = (backend or "openvino").strip().lower()
        self.min_confidence = float(min_confidence)
        self.unknown_label = str(unknown_label or UNKNOWN_BIRD_LABEL).strip() or UNKNOWN_BIRD_LABEL
        self.device = (device or "CPU").strip() or "CPU"
        self.regional_species = regional_species
        self._allowed_ids: set[int] | None = None

        if self.backend == "torch":
            self._init_torch()
        elif self.backend == "onnxruntime":
            self._init_onnxruntime()
        elif self.backend == "openvino":
            self._init_openvino()
        else:
            raise ValueError(f"Unsupported EfficientNetB2 backend: {backend!r}")

        self._build_regional_filter()
        _log.info(
            "EfficientNetB2Classifier: backend=%s weights=%s labels=%s regional=%s",
            self.backend,
            self.weights_dir,
            len(self.id2label),
            len(self._allowed_ids) if self._allowed_ids is not None else "ALL",
        )

    @property
    def names(self) -> dict[int, str]:
        """Ultralytics-compatible class index map for regional filters."""
        return dict(self.id2label)

    def _init_torch(self) -> None:
        import torch
        from transformers import EfficientNetForImageClassification, EfficientNetImageProcessor

        self._torch = torch
        self._processor = EfficientNetImageProcessor.from_pretrained(self.weights_dir)
        self._model = EfficientNetForImageClassification.from_pretrained(self.weights_dir)
        self._model.eval()
        self.id2label = {
            int(k): _normalize_species_label(v)
            for k, v in self._model.config.id2label.items()
        }

    def _init_onnxruntime(self) -> None:
        import onnxruntime as ort
        from transformers import EfficientNetImageProcessor

        onnx_path = self._resolve_onnx_path(self.weights_dir)
        self._processor = EfficientNetImageProcessor.from_pretrained(self.weights_dir)
        providers = ["CPUExecutionProvider"]
        dev = (self.device or "").lower()
        if "cuda" in dev:
            providers.insert(0, "CUDAExecutionProvider")
        self._ort_session = ort.InferenceSession(onnx_path, providers=providers)
        self._ort_input_name = self._ort_session.get_inputs()[0].name
        cfg_path = Path(self.weights_dir) / "config.json"
        if cfg_path.is_file():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            raw = cfg.get("id2label") or {}
            self.id2label = {int(k): _normalize_species_label(v) for k, v in raw.items()}
        else:
            self.id2label = {}

    @staticmethod
    def _resolve_onnx_path(weights_dir: str) -> str:
        p = Path(weights_dir)
        for name in ("birds_classifier_260.onnx", "birds_classifier.onnx", "model.onnx"):
            cand = p / name
            if cand.is_file():
                return str(cand)
        if p.is_file() and p.suffix == ".onnx":
            return str(p)
        raise FileNotFoundError(f"No ONNX classifier in {weights_dir}")

    def _init_openvino(self) -> None:
        import openvino as ov
        from transformers import EfficientNetImageProcessor

        xml = self._resolve_xml_path(self.weights_dir)
        self._processor = EfficientNetImageProcessor.from_pretrained(self.weights_dir)
        core = ov.Core()
        self._ov_core = core
        ov_dev = resolve_efficientnet_openvino_device(self.device)
        compile_cfg: dict = {}
        if ov_dev in ("GPU", "AUTO") or str(ov_dev).startswith("GPU"):
            try:
                import openvino.properties.hints as ov_hints

                compile_cfg[ov_hints.performance_mode()] = ov_hints.PerformanceMode.LATENCY
            except Exception:
                pass
        if compile_cfg:
            self._compiled = core.compile_model(xml, ov_dev, compile_cfg)
        else:
            self._compiled = core.compile_model(xml, ov_dev)
        self._ov_input = self._compiled.input(0)
        _log.info("EfficientNetB2 OpenVINO: device=%s xml=%s", ov_dev, xml)

        cfg_path = Path(self.weights_dir) / "config.json"
        if cfg_path.is_file():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            raw = cfg.get("id2label") or {}
            self.id2label = {int(k): _normalize_species_label(v) for k, v in raw.items()}
        else:
            self.id2label = {}

    @staticmethod
    def _resolve_xml_path(weights_dir: str) -> str:
        p = Path(weights_dir)
        if p.is_file() and p.suffix == ".xml":
            return str(p)
        for name in (
            "birds_classifier_260.xml",
            "openvino_model.xml",
            "birds_classifier.xml",
            "model.xml",
        ):
            cand = p / name
            if cand.is_file():
                return str(cand)
        xmls = sorted(p.glob("*.xml"))
        if xmls:
            return str(xmls[0])
        raise FileNotFoundError(f"No OpenVINO XML in {weights_dir}")

    def _build_regional_filter(self) -> None:
        if not self.regional_species:
            self._allowed_ids = None
            return

        def _norm(name: str) -> str:
            return str(name or "").replace("_OR_", "/").replace("_", " ").replace("-", " ").strip().lower()

        wanted = {_norm(s) for s in self.regional_species}
        allowed: set[int] = set()
        for idx, label in self.id2label.items():
            if _norm(label) in wanted:
                allowed.add(int(idx))
        self._allowed_ids = allowed if allowed else None

    def _preprocess_bgr(self, crop_bgr: np.ndarray) -> Any:
        import cv2
        from PIL import Image

        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        size = getattr(self._processor, "size", None) or {"height": 260, "width": 260}
        inputs = self._processor(
            images=pil,
            return_tensors="pt" if self.backend == "torch" else "np",
            size=size,
        )
        return inputs

    def predict_probs_bgr(self, crop_bgr: np.ndarray) -> np.ndarray:
        if crop_bgr is None or crop_bgr.size == 0:
            return np.zeros(len(self.id2label), dtype=np.float64)
        inputs = self._preprocess_bgr(crop_bgr)
        if self.backend == "torch":
            import torch

            with torch.no_grad():
                out = self._model(**inputs)
                logits = out.logits[0]
                probs = torch.softmax(logits, dim=-1).cpu().numpy().astype(np.float64)
            return probs

        if self.backend == "onnxruntime":
            pixel = inputs["pixel_values"]
            if hasattr(pixel, "numpy"):
                pixel = pixel.numpy()
            pixel = np.asarray(pixel, dtype=np.float32)
            if pixel.ndim == 3:
                pixel = np.expand_dims(pixel, 0)
            logits = self._ort_session.run(
                None,
                {self._ort_input_name: pixel},
            )[0][0]
            exp = np.exp(logits - np.max(logits))
            return exp / max(float(exp.sum()), 1e-12)

        pixel = inputs["pixel_values"]
        if hasattr(pixel, "numpy"):
            pixel = pixel.numpy()
        pixel = np.asarray(pixel, dtype=np.float32)
        if pixel.ndim == 3:
            pixel = np.expand_dims(pixel, 0)
        result = self._compiled({self._ov_input: pixel})
        logits = np.asarray(list(result.values())[0][0], dtype=np.float64)
        exp = np.exp(logits - np.max(logits))
        return exp / max(float(exp.sum()), 1e-12)

    def classify_crop_bgr(self, crop_bgr: np.ndarray) -> EfficientNetClassifierResult:
        probs = self.predict_probs_bgr(crop_bgr)
        if probs.size == 0:
            return EfficientNetClassifierResult(None, 0.0, 0.0, 0.0)
        ent, margin = _entropy_margin(probs)

        if self._allowed_ids is not None:
            valid = {i: probs[i] for i in self._allowed_ids if i < len(probs)}
            if not valid:
                return EfficientNetClassifierResult(self.unknown_label, 0.0, ent, margin)
            best_id = max(valid, key=valid.get)
            conf = float(valid[best_id])
        else:
            best_id = int(np.argmax(probs))
            conf = float(probs[best_id])

        if conf < self.min_confidence:
            return EfficientNetClassifierResult(self.unknown_label, conf, ent, margin)

        label = self.id2label.get(best_id, self.unknown_label)
        return EfficientNetClassifierResult(label, conf, ent, margin)

    def warmup(self) -> None:
        dummy = np.zeros((260, 260, 3), dtype=np.uint8)
        self.classify_crop_bgr(dummy)

    def __call__(self, crop_bgr: np.ndarray, **_: Any) -> EfficientNetB2Classifier:
        """Legacy hook: returns self after warmup-style call."""
        self.classify_crop_bgr(crop_bgr)
        return self


def load_efficientnet_b2_classifier(
    weights_dir: str,
    *,
    backend: str = "openvino",
    min_confidence: float | None = None,
    device: str | None = None,
    regional_species: list[str] | None = None,
    app_config: Mapping[str, Any] | None = None,
) -> EfficientNetB2Classifier:
    min_conf = DEFAULT_MIN_CONFIDENCE
    unknown = UNKNOWN_BIRD_LABEL
    if app_config is not None:
        try:
            raw = app_config.get("processor.efficientnet_b2_min_confidence")
            if raw is not None:
                min_conf = float(raw)
        except (TypeError, ValueError):
            pass
        unk = app_config.get("processor.efficientnet_b2_unknown_label")
        if unk:
            unknown = str(unk).strip()
    if min_confidence is not None:
        min_conf = float(min_confidence)
    ov_dev = device
    if ov_dev is None and app_config is not None:
        ov_dev = str(app_config.get("processor.classifier_inference_device") or "CPU")
    return EfficientNetB2Classifier(
        weights_dir=weights_dir,
        backend=backend,
        min_confidence=min_conf,
        unknown_label=unknown,
        device=ov_dev,
        regional_species=regional_species,
    )


def is_squirrel_detector_label(detector_label: str) -> bool:
    d = str(detector_label or "").strip().lower()
    if d in ("rodent", "squirrel"):
        return True
    return "squirrel" in d


def squirrel_species_output(
    detector_label: str,
    app_config: Mapping[str, Any] | None = None,
) -> EfficientNetClassifierResult:
    """Skip bird classifier; map Trapper squirrel box to catalog species name."""
    label = SQUIRREL_SPECIES_LABEL
    if app_config is not None:
        override = app_config.get("processor.squirrel_species_label")
        if override:
            label = str(override).strip() or label
    if str(detector_label or "").strip() == "Rodent":
        label = label  # canonical hub name
    return EfficientNetClassifierResult(label, 1.0, 0.0, 1.0)
