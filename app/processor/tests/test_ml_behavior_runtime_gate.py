"""Synthetic tests for scripts/ml_behavior_runtime_gate.py (#416)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / "scripts" / "ml_behavior_runtime_gate.py"
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("ml_behavior_runtime_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ml_behavior_runtime_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlBehaviorRuntimeGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _tiny_profile(self, *, mean_sec: float, p95_sec: float) -> dict:
        return {
            "schema": "behavior_runtime_profile@v1",
            "wall_seconds": {
                "mean": mean_sec,
                "p95": p95_sec,
            },
        }

    def test_gate_passes_when_profile_is_below_thresholds(self):
        profile = self._tiny_profile(mean_sec=0.004, p95_sec=0.009)
        out = self.mod.build_behavior_runtime_gate_report(
            profile=profile,
            max_p95_ms=25.0,
            max_mean_ms=15.0,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["p95_within_limit"])
        self.assertTrue(out["gates"]["mean_within_limit"])

    def test_gate_fails_when_p95_exceeds_threshold(self):
        profile = self._tiny_profile(mean_sec=0.005, p95_sec=0.040)
        out = self.mod.build_behavior_runtime_gate_report(
            profile=profile,
            max_p95_ms=25.0,
            max_mean_ms=15.0,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"]["p95_within_limit"])
        self.assertTrue(out["gates"]["mean_within_limit"])

    def test_gate_rejects_wrong_schema(self):
        with self.assertRaises(ValueError):
            self.mod.build_behavior_runtime_gate_report(
                profile={"schema": "other"},
                max_p95_ms=25.0,
                max_mean_ms=15.0,
            )


if __name__ == "__main__":
    unittest.main()
