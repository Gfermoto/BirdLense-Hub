"""Birder EU-common species classifier (707 Collins species) — torch + OpenVINO."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from inference.efficientnet_b2_classifier import (
    DEFAULT_MIN_CONFIDENCE,
    UNKNOWN_BIRD_LABEL,
    _entropy_margin,
    _normalize_species_label,
    resolve_efficientnet_openvino_device,
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BirderEuClassifierResult:
    species_name: str | None
    top1_confidence: float
    entropy: float
    top1_top2_margin: float


def _load_manifest(weights_dir: Path) -> dict[str, Any]:
    p = weights_dir / "birdlense_manifest.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    meta_files = list(weights_dir.glob("*.json"))
    meta_files = [m for m in meta_files if m.name != "birdlense_manifest.json"]
    if not meta_files:
        raise FileNotFoundError(f"No birder metadata JSON in {weights_dir}")
    return json.loads(meta_files[0].read_text(encoding="utf-8"))


def _load_id2label(weights_dir: Path) -> dict[int, str]:
    labels_path = weights_dir / "class_labels.txt"
    if labels_path.is_file():
        lines = [ln.strip() for ln in labels_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return {i: _normalize_species_label(ln) for i, ln in enumerate(lines)}
    manifest = _load_manifest(weights_dir)
    n = int(manifest.get("num_labels") or 0)
    if n <= 0:
        raise FileNotFoundError(f"class_labels.txt missing in {weights_dir}")
    return {}


class BirderEuClassifier:
    """Species classifier on BGR crops (Bird path only)."""

    def __init__(
        self,
        *,
        weights_dir: str,
        variant: str,
        backend: str = "openvino",
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        unknown_label: str = UNKNOWN_BIRD_LABEL,
        device: str | None = None,
        regional_species: list[str] | None = None,
    ) -> None:
        self.weights_dir = Path(weights_dir)
        self.variant = str(variant).strip()
        self.backend = (backend or "openvino").strip().lower()
        self.min_confidence = float(min_confidence)
        self.unknown_label = str(unknown_label or UNKNOWN_BIRD_LABEL).strip() or UNKNOWN_BIRD_LABEL
        self.device = (device or "CPU").strip() or "CPU"
        self.regional_species = regional_species
        self._manifest = _load_manifest(self.weights_dir)
        self.id2label = _load_id2label(self.weights_dir)
        if not self.id2label:
            raise RuntimeError(f"Empty label map in {self.weights_dir}")
        self._input_size = int(self._manifest.get("input_size") or 256)
        rgb = self._manifest.get("rgb_stats") or {}
        self._mean = np.array(rgb.get("mean", [0.5191, 0.5306, 0.4877]), dtype=np.float32)
        self._std = np.array(rgb.get("std", [0.2316, 0.2304, 0.2588]), dtype=np.float32)
        self._allowed_ids: set[int] | None = None

        if self.backend == "torch":
            self._init_torch()
        elif self.backend == "openvino":
            self._init_openvino()
        else:
            raise ValueError(f"Unsupported Birder EU backend: {backend!r}")

        self._build_regional_filter()
        _log.info(
            "BirderEuClassifier: variant=%s backend=%s labels=%s input=%s",
            self.variant,
            self.backend,
            len(self.id2label),
            self._input_size,
        )

    @property
    def names(self) -> dict[int, str]:
        return dict(self.id2label)

    def _init_torch(self) -> None:
        import birder

        self._birder = birder
        self._net, self._model_info, self._transform = birder.load_pretrained_model_and_transform(
            self.variant,
            inference=True,
        )
        # Sync labels from checkpoint if class_labels.txt stale
        idx2 = {int(v): _normalize_species_label(k) for k, v in self._model_info.class_to_idx.items()}
        if len(idx2) == len(self.id2label):
            self.id2label = idx2

    def _init_openvino(self) -> None:
        import openvino as ov

        bundle = self.weights_dir
        xml = bundle / "openvino_model.xml"
        if not xml.is_file():
            for name in ("model.xml", f"{self.variant}.xml"):
                cand = bundle / name
                if cand.is_file():
                    xml = cand
                    break
        if not xml.is_file():
            raise FileNotFoundError(
                f"Birder OpenVINO IR missing under {bundle}. Run scripts/export_birder_classifier_to_openvino.py",
            )
        ov_dev = resolve_efficientnet_openvino_device(self.device)
        core = ov.Core()
        self._ov_model = core.read_model(str(xml))
        try:
            self._ov_compiled = core.compile_model(self._ov_model, ov_dev)
        except Exception as exc:
            if str(ov_dev).upper() == "CPU":
                raise
            _log.warning(
                "Birder OpenVINO compile failed on %s, fallback to CPU: %s",
                ov_dev,
                exc,
            )
            self._ov_compiled = core.compile_model(self._ov_model, "CPU")

    def _build_regional_filter(self) -> None:
        if not self.regional_species:
            self._allowed_ids = None
            return
        allowed_names = {_normalize_species_label(s).lower() for s in self.regional_species if str(s).strip()}
        ids: set[int] = set()
        for idx, name in self.id2label.items():
            if name.lower() in allowed_names:
                ids.add(idx)
        self._allowed_ids = ids if ids else None

    def _preprocess_bgr(self, crop_bgr: np.ndarray) -> np.ndarray:
        import cv2

        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        size = self._input_size
        if h != size or w != size:
            rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_LINEAR)
        arr = rgb.astype(np.float32) / 255.0
        arr = (arr - self._mean.reshape(1, 1, 3)) / self._std.reshape(1, 1, 3)
        chw = np.transpose(arr, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        x = np.asarray(logits, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return x
        x = x - np.max(x)
        e = np.exp(x)
        s = e.sum()
        if s <= 0:
            return np.ones_like(x) / max(1, x.size)
        return (e / s).astype(np.float32)

    def _infer_probs(self, crop_bgr: np.ndarray) -> np.ndarray:
        if self.backend == "torch":
            import cv2
            from PIL import Image

            rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            tensor = self._transform(pil).unsqueeze(0)
            import torch

            self._net.eval()
            with torch.no_grad():
                out = self._net(tensor)
            if isinstance(out, (tuple, list)):
                out = out[0]
            logits = out.detach().cpu().numpy()
            return self._softmax(logits.reshape(-1))

        inp = self._preprocess_bgr(crop_bgr)
        res = self._ov_compiled([inp])
        logits = np.asarray(list(res.values())[0])
        if logits.ndim > 1:
            logits = logits[0]
        return self._softmax(logits)

    def classify_crop_bgr(self, crop_bgr: np.ndarray) -> BirderEuClassifierResult:
        probs = self._infer_probs(crop_bgr)
        ent, margin = _entropy_margin(probs)

        if self._allowed_ids is not None:
            valid = {i: probs[i] for i in self._allowed_ids if i < len(probs)}
            if not valid:
                return BirderEuClassifierResult(self.unknown_label, 0.0, ent, margin)
            best_id = max(valid, key=valid.get)
            conf = float(valid[best_id])
        else:
            best_id = int(np.argmax(probs))
            conf = float(probs[best_id])

        if conf < self.min_confidence:
            return BirderEuClassifierResult(self.unknown_label, conf, ent, margin)

        label = self.id2label.get(best_id, self.unknown_label)
        if str(label).strip().lower() in ("unknown", "unknown bird"):
            return BirderEuClassifierResult(self.unknown_label, conf, ent, margin)
        return BirderEuClassifierResult(label, conf, ent, margin)

    def warmup(self) -> None:
        dummy = np.zeros((self._input_size, self._input_size, 3), dtype=np.uint8)
        self.classify_crop_bgr(dummy)


def default_birder_variant(app_config: Mapping[str, Any] | None) -> str:
    if app_config is None:
        return "convnext_v2_tiny_eu-common256px"
    raw = app_config.get("processor.birder_eu_variant")
    return str(raw or "convnext_v2_tiny_eu-common256px").strip()


def _normalize_weights_bundle(weights_dir: str, variant: str) -> Path:
    """Always use ``{variant}_openvino_model/`` for labels + IR (``.pt`` is sibling on disk)."""
    from inference.classifier_model_layout import resolve_birder_bundle_dir

    ref = Path(weights_dir)
    root = ref.parent
    if ref.is_file() and ref.suffix == ".pt":
        root = ref.parent
    elif ref.is_dir() and ref.name == variant:
        root = ref.parent
    return resolve_birder_bundle_dir(root, variant, ref if ref.is_dir() else None)


def load_birder_eu_classifier(
    weights_dir: str,
    *,
    backend: str = "openvino",
    variant: str | None = None,
    min_confidence: float | None = None,
    device: str | None = None,
    regional_species: list[str] | None = None,
    app_config: Mapping[str, Any] | None = None,
) -> BirderEuClassifier:
    min_conf = DEFAULT_MIN_CONFIDENCE
    unknown = UNKNOWN_BIRD_LABEL
    var = variant or default_birder_variant(app_config)
    if app_config is not None:
        try:
            raw = app_config.get("processor.birder_eu_min_confidence")
            if raw is not None:
                min_conf = float(raw)
        except (TypeError, ValueError):
            pass
        unk = app_config.get("processor.birder_eu_unknown_label")
        if unk:
            unknown = str(unk).strip()
        ov_dev = app_config.get("processor.classifier_inference_device")
        if device is None and ov_dev:
            device = str(ov_dev)
    if min_confidence is not None:
        min_conf = float(min_confidence)
    bundle = _normalize_weights_bundle(weights_dir, var)
    return BirderEuClassifier(
        weights_dir=str(bundle),
        variant=var,
        backend=backend,
        min_confidence=min_conf,
        unknown_label=unknown,
        device=device,
        regional_species=regional_species,
    )
