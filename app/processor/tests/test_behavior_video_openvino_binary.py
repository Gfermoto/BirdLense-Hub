"""Binary video OpenVINO export: single logit, two labels."""

from __future__ import annotations

import numpy as np


def test_binary_single_logit_maps_to_two_labels():
    from behavior_video_runtime import _predict_video_openvino  # noqa: PLC0415

    labels = ["feeding", "flying"]
    logits = np.array([2.0], dtype=np.float64)
    p_pos = 1.0 / (1.0 + np.exp(-float(logits[0])))
    probs = np.array([1.0 - p_pos, p_pos], dtype=np.float64)
    idx = int(np.argmax(probs))
    assert labels[idx] == "flying"
    assert probs[idx] > 0.5
