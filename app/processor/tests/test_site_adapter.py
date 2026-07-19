"""SiteAdapter scaffold tests (RC5)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from site_adapter import (  # noqa: E402
    STATUS_CANARY,
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
            # Runtime apply stays noop until weights exist.
            self.assertFalse(apply_site_adapter_canary(data_dir=tmp, track_id=1))


if __name__ == "__main__":
    unittest.main()
