"""Synthetic tests for scripts/ml_behavior_canary_gate.py (#416)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / "scripts" / "ml_behavior_canary_gate.py"
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("ml_behavior_canary_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ml_behavior_canary_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlBehaviorCanaryGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _tiny_report(self, macro_f1: float, accuracy: float, ok: bool = True) -> dict:
        return {
            "schema": "behavior_train_report@v1",
            "metrics": {"macro_f1": macro_f1, "accuracy": accuracy},
            "ok": ok,
            "gates": {},
        }

    def test_gate_passes_when_canary_matches(self):
        b = self._tiny_report(0.8, 0.9)
        c = self._tiny_report(0.8, 0.9)
        out = self.mod.build_behavior_canary_gate_report(
            baseline_report=b,
            canary_report=c,
            max_macro_f1_drop=0.03,
            max_accuracy_drop=0.05,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["macro_f1_regression_ok"])

    def test_gate_fails_on_f1_regression(self):
        b = self._tiny_report(0.8, 0.9)
        c = self._tiny_report(0.70, 0.9)
        out = self.mod.build_behavior_canary_gate_report(
            baseline_report=b,
            canary_report=c,
            max_macro_f1_drop=0.03,
            max_accuracy_drop=0.05,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["macro_f1_regression_ok"])


if __name__ == "__main__":
    unittest.main()
