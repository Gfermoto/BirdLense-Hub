"""SiteAdapter scaffold tests (RC5)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from site_adapter import (  # noqa: E402
    STATUS_ACTIVE,
    STATUS_CANARY,
    adjust_confidence_with_site_adapter,
    apply_site_adapter_canary,
    load_site_adapter,
    site_adapter_status,
    write_site_adapter_manifest,
)


class TestSiteAdapter(unittest.TestCase):
    def test_missing_manifest_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = site_adapter_status(tmp)
            self.assertFalse(st["present"])
            self.assertEqual(st["status"], "inactive")
            self.assertFalse(apply_site_adapter_canary(data_dir=tmp))

    def test_write_and_load_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = write_site_adapter_manifest(
                tmp,
                version="2026.07.19",
                source="feedback_export",
                status=STATUS_CANARY,
                canary_share=0.1,
            )
            loaded = load_site_adapter(tmp)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.version, m.version)
            st = site_adapter_status(tmp)
            self.assertTrue(st["present"])
            self.assertTrue(st["canary_ready"])
            # No priors/weights → canary apply still false.
            self.assertFalse(apply_site_adapter_canary(data_dir=tmp, track_id=1))

    def test_species_priors_adjust_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_site_adapter_manifest(
                tmp,
                version="2026.07.19-priors",
                source="unit_test",
                status=STATUS_ACTIVE,
                canary_share=1.0,
                species_priors={"great tit": 0.15},
            )
            st = site_adapter_status(tmp)
            self.assertEqual(st["runtime_apply"], "species_priors")
            self.assertTrue(apply_site_adapter_canary(data_dir=tmp, track_id=42))
            conf, info = adjust_confidence_with_site_adapter(
                data_dir=tmp,
                species="Great Tit",
                confidence=0.50,
                track_id=42,
            )
            self.assertTrue(info["applied"])
            self.assertAlmostEqual(conf, 0.65, places=4)
            # Unknown species: selected but no delta → not applied.
            conf2, info2 = adjust_confidence_with_site_adapter(
                data_dir=tmp,
                species="Eurasian Jay",
                confidence=0.50,
                track_id=42,
            )
            self.assertFalse(info2["applied"])
            self.assertAlmostEqual(conf2, 0.50, places=4)

    def test_canary_share_buckets(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_site_adapter_manifest(
                tmp,
                version="bucket-v1",
                source="unit_test",
                status=STATUS_CANARY,
                canary_share=0.0,
                species_priors={"dunnock": 0.1},
            )
            self.assertFalse(apply_site_adapter_canary(data_dir=tmp, track_id=1))


if __name__ == "__main__":
    unittest.main()
