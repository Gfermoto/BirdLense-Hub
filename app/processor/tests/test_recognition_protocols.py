"""RC4 recognition protocol stubs."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from recognition_protocols import (  # noqa: E402
    BoxProvider,
    SpeciesAuthority,
    SpeciesHint,
    TriggerSource,
    hub_is_species_authority,
)


class _StubTrigger:
    name = "opencv"

    def poll(self):
        return None


class _StubBoxes:
    name = "yolo"

    def boxes_for_window(self, *, start_time, end_time, camera_id=None):
        return []


class _StubHint:
    name = "frigate"

    def hints_for_window(self, *, start_time, end_time, camera_id=None):
        return []


class _StubAuth:
    name = "hub"

    def may_accept_named(self, row):
        return True


class _Cfg:
    def get(self, key, default=None):
        return default


class TestRecognitionProtocols(unittest.TestCase):
    def test_structural_protocols(self):
        self.assertIsInstance(_StubTrigger(), TriggerSource)
        self.assertIsInstance(_StubBoxes(), BoxProvider)
        self.assertIsInstance(_StubHint(), SpeciesHint)
        self.assertIsInstance(_StubAuth(), SpeciesAuthority)

    def test_hub_default_authority(self):
        self.assertTrue(hub_is_species_authority(_Cfg()))


if __name__ == "__main__":
    unittest.main()
