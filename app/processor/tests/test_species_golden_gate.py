"""RC6: species golden gate must pass Hub-only taxonomy cases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts/species_golden_gate.py"


class TestSpeciesGoldenGate(unittest.TestCase):
    def test_species_gate_enforced_pass(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--enforce"],
            cwd=str(REPO),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        report = REPO / "docs/reports/pipeline_golden/species_golden_latest.json"
        self.assertTrue(report.is_file())
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("product"), "taxonomy")
        self.assertGreaterEqual(int(data.get("case_count") or 0), 5)

    def test_cases_file_has_frigate_non_hub_win(self):
        cases = json.loads((REPO / "benchmarks/species_golden_cases.json").read_text(encoding="utf-8"))
        frigate = [c for c in cases["cases"] if c["id"] == "frigate_named_not_hub_win"]
        self.assertEqual(len(frigate), 1)
        self.assertFalse(frigate[0]["expect"]["hub_taxonomy_win"])


if __name__ == "__main__":
    unittest.main()
