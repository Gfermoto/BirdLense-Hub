"""Synthetic tests for scripts/verify_parity_report.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestVerifyParityReport(unittest.TestCase):
    def test_verify_pass(self):
        from verify_parity_report import verify_parity_report

        report = {
            "schema": "parity_report@v1",
            "ok": True,
            "sections": {
                "quality": {"precision_proxy": 0.9, "recall_proxy": 0.8},
                "event_structure": {"unknown_share": 0.1},
            },
        }
        ok, errs = verify_parity_report(report=report)
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_verify_fail(self):
        from verify_parity_report import verify_parity_report

        report = {
            "schema": "parity_report@v1",
            "ok": False,
            "sections": {
                "quality": {"precision_proxy": 0.1, "recall_proxy": 0.0},
                "event_structure": {"unknown_share": 0.99},
            },
        }
        ok, errs = verify_parity_report(report=report)
        self.assertFalse(ok)
        self.assertTrue(any("precision_proxy_low" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
