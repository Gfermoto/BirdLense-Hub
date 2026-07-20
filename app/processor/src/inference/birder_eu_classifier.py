"""Birder EU-common species classifier (707 Collins species) — torch + ONNX Runtime."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from inference.classifier_common import (
    UNKNOWN_BIRD_LABEL,
    entropy_margin as _entropy_margin,
    normalize_species_label as _normalize_species_label,
)
from processor_config_defaults import BIRDER_EU_MIN_CONFIDENCE

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BirderEuClassifierResult:
    species_name: str | None
    top1_confidence: float
    entropy: float
    top1_top2_margin: float
    # Named near-miss when primary is Unknown (low conf / open-set). Soft finalize may keep it.
    alt_species_name: str | None = None
    alt_confidence: float | None = None
    # Second-best named (always) for site-prior re-rank vs wrong top1.
    runner_up_species_name: str | None = None
    runner_up_confidence: float | None = None
    # Top-k named (name, conf) for site-prior soft rescue vs confusion (pigeon/dove).
    top_named: tuple[tuple[str, float], ...] = ()


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
        backend: str = "torch",
        min_confidence: float = BIRDER_EU_MIN_CONFIDENCE,
        unknown_label: str = UNKNOWN_BIRD_LABEL,
        device: str | None = None,
        regional_species: list[str] | None = None,
        app_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.weights_dir = Path(weights_dir)
        self.variant = str(variant).strip()
        self.backend = (backend or "torch").strip().lower()
        self.min_confidence = float(min_confidence)
        self.unknown_label = str(unknown_label or UNKNOWN_BIRD_LABEL).strip() or UNKNOWN_BIRD_LABEL
        self.device = (device or "CPU").strip() or "CPU"
        self.regional_species = regional_species
        self._app_config = app_config
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
        elif self.backend == "onnxruntime":
            self._init_onnxruntime()
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
        idx2 = {int(v): _normalize_species_label(k) for k, v in self._model_info.class_to_idx.items()}
        if len(idx2) == len(self.id2label):
            self.id2label = idx2

    def _resolve_onnx_path(self) -> Path:
        from inference.classifier_model_layout import resolve_birder_onnx_path

        # RC5 / Bet A: site-adapter ONNX overrides stock weights when active.
        try:
            from processor_support import get_data_dir
            from site_adapter import resolve_site_adapter_weights_path

            alt = resolve_site_adapter_weights_path(get_data_dir())
            if alt is not None and alt.is_file():
                _log.info("BirderEuClassifier: using site_adapter weights %s", alt)
                return alt
        except Exception:
            _log.debug("site_adapter weights resolve skipped", exc_info=True)

        onnx = resolve_birder_onnx_path(self.weights_dir, self.variant)
        if onnx.is_file():
            return onnx
        raise FileNotFoundError(
            f"Birder EU ONNX not found (expected {onnx}). "
            "Run: python3 scripts/download_birder_classifier.py --export-onnx",
        )

    def _init_onnxruntime(self) -> None:
        import onnxruntime as ort

        onnx_path = self._resolve_onnx_path()
        providers = ["CPUExecutionProvider"]
        dev = (self.device or "").lower()
        if "cuda" in dev:
            providers.insert(0, "CUDAExecutionProvider")
        self._ort_session = ort.InferenceSession(str(onnx_path), providers=providers)
        self._ort_input_name = self._ort_session.get_inputs()[0].name
        inp_shape = self._ort_session.get_inputs()[0].shape
        if isinstance(inp_shape, (list, tuple)) and len(inp_shape) == 4:
            h, w = inp_shape[2], inp_shape[3]
            if isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0:
                self._input_size = max(h, w)

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

        if self.backend == "onnxruntime":
            chw = self._preprocess_bgr(crop_bgr)
            logits = self._ort_session.run(
                None,
                {self._ort_input_name: chw},
            )[0]
            return self._softmax(np.asarray(logits, dtype=np.float64).reshape(-1))

        raise ValueError(f"Unsupported backend: {self.backend}")

    def _named_ranked(
        self, probs: np.ndarray, *, exclude_id: int | None = None, top_k: int = 5
    ) -> list[tuple[str, float]]:
        """Top-k non-Unknown classes for soft finalize / prior rescue."""

        def _is_unknown_label(label: str) -> bool:
            return str(label or "").strip().lower() in ("unknown", "unknown bird")

        ids = (
            list(self._allowed_ids)
            if self._allowed_ids is not None
            else list(range(len(probs)))
        )
        ranked: list[tuple[str, float]] = []
        for i in ids:
            if i >= len(probs) or (exclude_id is not None and i == exclude_id):
                continue
            label = self.id2label.get(i, self.unknown_label)
            if _is_unknown_label(label):
                continue
            name = str(label).strip()
            if not name:
                continue
            ranked.append((name, float(probs[i])))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[: max(1, int(top_k))]

    def _best_named_alt(
        self, probs: np.ndarray, *, exclude_id: int | None = None
    ) -> tuple[str | None, float]:
        ranked = self._named_ranked(probs, exclude_id=exclude_id, top_k=1)
        if not ranked:
            return None, 0.0
        return ranked[0][0], ranked[0][1]

    def classify_crop_bgr(self, crop_bgr: np.ndarray) -> BirderEuClassifierResult:
        probs = self._infer_probs(crop_bgr)
        ent, margin = _entropy_margin(probs)

        def _is_unknown_label(label: str) -> bool:
            return str(label or "").strip().lower() in ("unknown", "unknown bird")

        # RC7 open-set: honest argmax — do not skip Unknown to force a named label.
        if self._allowed_ids is not None:
            valid = {i: probs[i] for i in self._allowed_ids if i < len(probs)}
            if not valid:
                return BirderEuClassifierResult(self.unknown_label, 0.0, ent, margin)
            best_id = max(valid, key=valid.get)
            conf = float(valid[best_id])
        else:
            best_id = int(np.argmax(probs))
            conf = float(probs[best_id])

        label = self.id2label.get(best_id, self.unknown_label)
        top_named = tuple(self._named_ranked(probs, exclude_id=None, top_k=35))
        if _is_unknown_label(label):
            alt, alt_conf = self._best_named_alt(probs, exclude_id=best_id)
            return BirderEuClassifierResult(
                self.unknown_label,
                float(conf),
                ent,
                margin,
                alt_species_name=alt,
                alt_confidence=float(alt_conf) if alt else None,
                top_named=top_named,
            )

        if conf < self.min_confidence:
            named = str(label).strip() or None
            ru, ru_conf = self._best_named_alt(probs, exclude_id=best_id)
            return BirderEuClassifierResult(
                self.unknown_label,
                conf,
                ent,
                margin,
                alt_species_name=named,
                alt_confidence=float(conf) if named else None,
                runner_up_species_name=ru,
                runner_up_confidence=float(ru_conf) if ru else None,
                top_named=top_named,
            )
        ru, ru_conf = self._best_named_alt(probs, exclude_id=best_id)
        return BirderEuClassifierResult(
            label,
            conf,
            ent,
            margin,
            runner_up_species_name=ru,
            runner_up_confidence=float(ru_conf) if ru else None,
            top_named=top_named,
        )

    def warmup(self) -> None:
        dummy = np.zeros((self._input_size, self._input_size, 3), dtype=np.uint8)
        self.classify_crop_bgr(dummy)


def default_birder_variant(app_config: Mapping[str, Any] | None) -> str:
    if app_config is None:
        return "convnext_v2_tiny_eu-common256px"
    raw = app_config.get("processor.birder_eu_variant")
    return str(raw or "convnext_v2_tiny_eu-common256px").strip()


def _normalize_weights_bundle(weights_dir: str, variant: str) -> Path:
    from inference.classifier_model_layout import resolve_birder_bundle_dir

    ref = Path(weights_dir)
    if ref.is_file():
        cls_root = ref.parent.parent
    elif ref.is_dir() and ref.name == variant:
        cls_root = ref.parent
    else:
        cls_root = ref.parent if ref.is_dir() else ref.parent.parent
    return resolve_birder_bundle_dir(cls_root, variant, ref if ref.is_dir() else None)


def load_birder_eu_classifier(
    weights_dir: str,
    *,
    backend: str = "torch",
    variant: str | None = None,
    min_confidence: float | None = None,
    device: str | None = None,
    regional_species: list[str] | None = None,
    app_config: Mapping[str, Any] | None = None,
) -> BirderEuClassifier:
    min_conf = float(BIRDER_EU_MIN_CONFIDENCE)
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
        app_config=app_config,
    )