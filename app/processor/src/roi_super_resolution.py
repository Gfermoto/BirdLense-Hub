from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

_LOG = logging.getLogger(__name__)

_MODEL_FSRCNN = "fsrcnn_x2"
_MODEL_REALESRGAN = "realesrgan_x2"


@dataclass
class RoiSrMeta:
    enabled: bool
    model: str
    native: bool
    latency_ms: float


class RoiSuperResolution:
    """ROI-only SR stage for small crops (experimental #472)."""

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.enabled = bool(cfg.get("experimental.sr_enabled", False))
        self.model = str(cfg.get("experimental.sr_model", _MODEL_FSRCNN) or _MODEL_FSRCNN).strip().lower()
        self.scale = max(2, min(4, int(cfg.get("experimental.sr_scale", 2) or 2)))
        self.min_crop_px = max(4, int(cfg.get("experimental.sr_min_crop_px", 8) or 8))
        self.max_crop_px = max(self.min_crop_px, int(cfg.get("experimental.sr_max_crop_px", 96) or 96))
        self.max_latency_ms = max(1.0, float(cfg.get("experimental.sr_max_latency_ms", 20.0) or 20.0))
        self._warned_once = False
        self._native = False
        self._fsrcnn = None
        self._realesrgan_net = None
        self._setup(cfg)

    def _setup(self, cfg: Mapping[str, Any]) -> None:
        if not self.enabled:
            return
        if self.model == _MODEL_FSRCNN:
            self._setup_fsrcnn(cfg)
            return
        if self.model == _MODEL_REALESRGAN:
            self._setup_realesrgan(cfg)
            return
        self.model = _MODEL_FSRCNN
        self._setup_fsrcnn(cfg)

    def _setup_fsrcnn(self, cfg: Mapping[str, Any]) -> None:
        try:
            model_path = str(cfg.get("processor.models.sr_fsrcnn_x2_path") or "").strip()
            if not model_path:
                return
            p = Path(model_path)
            if not p.is_absolute():
                proc_root = Path(__file__).resolve().parent.parent
                p = (proc_root / p).resolve()
            if not p.exists():
                return
            if not hasattr(cv2, "dnn_superres"):
                return
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(str(p))
            sr.setModel("fsrcnn", self.scale)
            self._fsrcnn = sr
            self._native = True
        except Exception:
            self._fsrcnn = None
            _LOG.debug("SR: FSRCNN init failed", exc_info=True)

    def _setup_realesrgan(self, cfg: Mapping[str, Any]) -> None:
        try:
            model_path = str(cfg.get("processor.models.sr_realesrgan_x2_path") or "").strip()
            if not model_path:
                return
            p = Path(model_path)
            if not p.is_absolute():
                proc_root = Path(__file__).resolve().parent.parent
                p = (proc_root / p).resolve()
            if not p.exists():
                return
            net = cv2.dnn.readNetFromONNX(str(p))
            self._realesrgan_net = net
            self._native = True
        except Exception:
            self._realesrgan_net = None
            _LOG.debug("SR: RealESRGAN init failed", exc_info=True)

    def should_enhance(self, crop: np.ndarray, *, min_box_size_px: int) -> bool:
        if not self.enabled:
            return False
        if crop is None or crop.size == 0:
            return False
        h, w = crop.shape[:2]
        short_side = min(h, w)
        if short_side < self.min_crop_px:
            return False
        if short_side > self.max_crop_px:
            return False
        return short_side < max(1, int(min_box_size_px))

    def _fallback_upscale(self, crop: np.ndarray) -> np.ndarray:
        up = cv2.resize(
            crop,
            (crop.shape[1] * self.scale, crop.shape[0] * self.scale),
            interpolation=cv2.INTER_CUBIC if self.model == _MODEL_FSRCNN else cv2.INTER_LANCZOS4,
        )
        blur = cv2.GaussianBlur(up, (0, 0), sigmaX=0.8)
        return cv2.addWeighted(up, 1.25, blur, -0.25, 0)

    def _native_upscale(self, crop: np.ndarray) -> np.ndarray:
        if self.model == _MODEL_FSRCNN and self._fsrcnn is not None:
            return self._fsrcnn.upsample(crop)
        if self.model == _MODEL_REALESRGAN and self._realesrgan_net is not None:
            blob = cv2.dnn.blobFromImage(
                crop,
                scalefactor=1.0 / 255.0,
                size=(crop.shape[1], crop.shape[0]),
                mean=(0, 0, 0),
                swapRB=True,
                crop=False,
            )
            self._realesrgan_net.setInput(blob)
            out = self._realesrgan_net.forward()
            out = np.squeeze(out, axis=0)
            out = np.transpose(out, (1, 2, 0))
            out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
            return out
        return self._fallback_upscale(crop)

    def enhance(self, crop: np.ndarray) -> tuple[np.ndarray, RoiSrMeta]:
        if not self.enabled:
            return crop, RoiSrMeta(False, self.model, False, 0.0)
        t0 = time.perf_counter()
        native_used = False
        try:
            if self._native:
                out = self._native_upscale(crop)
                native_used = True
            else:
                out = self._fallback_upscale(crop)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if elapsed > self.max_latency_ms and not self._warned_once:
                _LOG.warning(
                    "SR ROI overhead %.1fms > budget %.1fms (%s)",
                    elapsed,
                    self.max_latency_ms,
                    self.model,
                )
                self._warned_once = True
            return out, RoiSrMeta(True, self.model, native_used, elapsed)
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000.0
            _LOG.debug("SR ROI failed; fallback to original crop", exc_info=True)
            return crop, RoiSrMeta(True, self.model, False, elapsed)


def build_roi_super_resolution(cfg: Mapping[str, Any]) -> RoiSuperResolution:
    return RoiSuperResolution(cfg)
