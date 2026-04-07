"""Lightweight fusion + calibration scorer.

Provides a small pluggable scorer for multimodal features. Prefers PyTorch if
available; falls back to a deterministic numpy sigmoid-weighted sum so runtime
does not crash in minimal environments.
"""
from __future__ import annotations

from typing import Mapping, Optional

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False
    import math
    import numpy as np
if _TORCH_AVAILABLE:
    class _TorchMLP(nn.Module):
        def __init__(self, in_dim: int, hidden: int = 32):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden // 2),
                nn.ReLU(),
                nn.Linear(hidden // 2, 1),
            )

        def forward(self, x):
            return self.net(x).squeeze(-1)


class FusionScorer:
    """Compute a calibrated confidence from multimodal features.

    Features expected (not all required): detector_conf, classifier_conf,
    birdnet_prior, key_frame_score, key_frame_count, multi_camera_count.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """Initialize FusionScorer. model_path optional; device defaults to 'cpu'."""
        self.device = device
        self.model_path = model_path
        if _TORCH_AVAILABLE:
            # model topology small and robust; load state if given else init.
            self._in_order = [
                'detector_conf',
                'classifier_conf',
                'birdnet_prior',
                'key_frame_score',
                'key_frame_count',
                'multi_camera_count',
            ]
            self._model = _TorchMLP(len(self._in_order))
            self._model.to(self.device)
            # optional load
            if model_path:
                try:
                    state = torch.load(model_path, map_location=self.device)
                    self._model.load_state_dict(state)
                except Exception:
                    # ignore load errors; keep initialized model
                    pass
            # default temperature for calibration (can be tuned)
            self.temperature = torch.tensor(1.0, device=self.device)
        else:
            # deterministic fallback weights (tuned heuristically)
            self._in_order = [
                'detector_conf',
                'classifier_conf',
                'birdnet_prior',
                'key_frame_score',
                'key_frame_count',
                'multi_camera_count',
            ]
            # higher weight to classifier confidence, moderate to detector and birdnet
            self._weights = np.array(
                [0.15, 0.5, 0.15, 0.1, 0.05, 0.05], dtype=float
            )
            self._bias = 0.0
            self._temp = 1.0

    def _vec_from_features(self, features: Mapping[str, float]):
        vals = []
        for k in self._in_order:
            v = features.get(k, 0.0)
            try:
                vals.append(float(v))
            except Exception:
                vals.append(0.0)
        return vals

    def score(self, features: Mapping[str, float]) -> float:
        """Return calibrated confidence in [0,1]."""
        vals = self._vec_from_features(features)
        if _TORCH_AVAILABLE:
            try:
                x = torch.tensor(
                    vals, dtype=torch.float32, device=self.device
                ).unsqueeze(0)
                with torch.no_grad():
                    logit = self._model(x).squeeze(0)
                    prob = torch.sigmoid(logit / (self.temperature + 1e-12))
                return float(prob.cpu().item())
            except Exception:
                # fallback deterministic
                pass
        # numpy fallback
        try:
            x = np.array(vals, dtype=float)
            z = float(np.dot(self._weights, x) + self._bias)
            # temperature scaling
            z = z / max(1e-6, self._temp)
            p = 1.0 / (1.0 + math.exp(-z))
            return float(min(max(p, 0.0), 1.0))
        except Exception:
            return 0.0
__all__ = ['FusionScorer']
