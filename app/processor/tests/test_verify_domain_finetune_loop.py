"""Tests for scripts/verify_domain_finetune_loop.py."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_MOD_PATH = _REPO / "scripts" / "verify_domain_finetune_loop.py"
_spec = importlib.util.spec_from_file_location("verify_domain_finetune_loop", _MOD_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["verify_domain_finetune_loop"] = _mod
_spec.loader.exec_module(_mod)
evaluate_domain_finetune_loop = _mod.evaluate_domain_finetune_loop


class TestVerifyDomainFinetuneLoop(unittest.TestCase):
    def test_blocks_weak_uplift_promotion(self):
        report = evaluate_domain_finetune_loop(
            contract={
                "required_candidates": ["c1"],
                "min_uplift_f1": 0.02,
                "block_promote_on_weak_uplift": True,
                "required_evidence_markers": [],
                "require_champion_shadow_ok": False,
                "require_acceptance_gate_ok": False,
                "require_rollback_ready_evidence": False,
            },
            champion_shadow={"ok": True},
            acceptance_gate={"ok": True},
            history_rows=[
                {
                    "candidate_id": "c1",
                    "promoted": True,
                    "uplift_f1": 0.005,
                    "evidence_path": "docs/reports/ml_shadow/evidence/detector_candidate_2026_05_24.md",
                }
            ],
        )
        self.assertFalse(report["checks"]["promote_uplift_ok"])
        self.assertIn("c1", report["drift"]["weak_uplift_promotions"])

    def test_allows_promotion_above_uplift_threshold(self):
        report = evaluate_domain_finetune_loop(
            contract={
                "required_candidates": ["c1"],
                "min_uplift_f1": 0.01,
                "block_promote_on_weak_uplift": True,
                "required_evidence_markers": [],
                "require_champion_shadow_ok": False,
                "require_acceptance_gate_ok": False,
                "require_rollback_ready_evidence": False,
            },
            champion_shadow={"ok": True},
            acceptance_gate={"ok": True},
            history_rows=[
                {
                    "candidate_id": "c1",
                    "promoted": True,
                    "uplift_f1": 0.018,
                    "evidence_path": "docs/reports/ml_shadow/evidence/detector_candidate_2026_05_29.md",
                }
            ],
        )
        self.assertTrue(report["checks"]["promote_uplift_ok"])


if __name__ == "__main__":
    unittest.main()
