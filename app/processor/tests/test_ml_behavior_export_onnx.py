"""Tests for scripts/ml_behavior_export_onnx.py (#416); requires onnx + onnxruntime."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[3]

try:
    import onnx  # noqa: F401

    _HAVE_ONNX = True
except ImportError:
    _HAVE_ONNX = False


def _load_export_script():
    path = _REPO_ROOT / "scripts" / "ml_behavior_export_onnx.py"
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("ml_behavior_export_onnx", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(_HAVE_ONNX, "onnx not installed")
class TestMlBehaviorExportOnnx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_export_script()

    def test_export_roundtrip_matches_numpy_logits(self):
        export = {
            "schema": "behavior_logistic_export@v1",
            "labels": ["a", "b"],
            "coef": [[1.0, 0.0, -0.5], [0.0, 1.0, 0.25]],
            "intercept": [-0.1, 0.2],
        }
        with tempfile.TemporaryDirectory() as td:
            outp = Path(td) / "m.onnx"
            self.mod.export_behavior_logistic_onnx(export_json=export, out_onnx=outp)
            self.assertTrue(outp.is_file())
            import onnx as onnx_pkg

            onx = onnx_pkg.load(str(outp))
            onnx_pkg.checker.check_model(onx)
            import onnxruntime as ort

            sess = ort.InferenceSession(str(outp), providers=["CPUExecutionProvider"])
            x = np.array([[0.5, 1.0, 0.25]], dtype=np.float32)
            logits_ov = np.asarray(sess.run(None, {sess.get_inputs()[0].name: x})[0], dtype=np.float64).reshape(-1)
            w = np.array(export["coef"], dtype=np.float64)
            b = np.array(export["intercept"], dtype=np.float64).reshape(-1)
            logits_np = (x.astype(np.float64) @ w.T).reshape(-1) + b
            np.testing.assert_allclose(logits_ov, logits_np, rtol=1e-5, atol=1e-5)


if __name__ == "__main__":
    unittest.main()
