"""Tests for scripts/pipeline_golden_gate.py (#611)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts/pipeline_golden_gate.py"


class TestPipelineGoldenGateScript(unittest.TestCase):
    def test_unit_fallback_passes(self):
        env = os.environ.copy()
        env.pop("SOTA_GOLDEN_CLIP_1819", None)
        env.pop("YOLO_GOLDEN_CLIP_1819", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--enforce", "--skip-heavy"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        report = REPO / "docs/reports/pipeline_golden/pipeline_golden_latest.json"
        self.assertTrue(report.is_file())
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("mode"), "unit_fallback")


if __name__ == "__main__":
    unittest.main()
