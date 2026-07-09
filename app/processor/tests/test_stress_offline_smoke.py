"""CI smoke: stress_test_offline scenarios (synthetic, no YOLO)."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


class TestStressOfflineSmoke(unittest.TestCase):
    def test_stress_script_passes_synthetic(self):
        env = {
            **dict(__import__("os").environ),
            "STRESS_MAX_SILENCE_ACCEPTED": "0",
            "STRESS_MIN_STORM_RECALL": "1.0",
        }
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "stress_test_offline.py"), "--no-yolo"],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
