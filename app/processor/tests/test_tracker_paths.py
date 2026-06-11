import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from tracker_paths import resolve_tracker_config_path  # noqa: E402


class TestTrackerPaths(unittest.TestCase):
    def test_builtin_name_unchanged_when_no_file(self):
        self.assertEqual(resolve_tracker_config_path("botsort.yaml"), "botsort.yaml")

    def test_resolves_models_tracker_relative(self):
        here = os.path.dirname(os.path.abspath(__file__))
        proc_root = os.path.abspath(os.path.join(here, ".."))
        yaml_path = os.path.join(proc_root, "models/tracker/bytetrack_birdlense.yaml")
        if not os.path.isfile(yaml_path):
            self.skipTest("bundled tracker yaml missing")
        resolved = resolve_tracker_config_path("models/tracker/bytetrack_birdlense.yaml")
        self.assertEqual(resolved, yaml_path)

    def test_resolves_bare_tracker_yaml_under_models_tracker(self):
        here = os.path.dirname(os.path.abspath(__file__))
        proc_root = os.path.abspath(os.path.join(here, ".."))
        yaml_path = os.path.join(proc_root, "models/tracker/bytetrack_birdlense_unstick.yaml")
        if not os.path.isfile(yaml_path):
            self.skipTest("bundled unstick tracker yaml missing")
        resolved = resolve_tracker_config_path("bytetrack_birdlense_unstick.yaml")
        self.assertEqual(resolved, yaml_path)

    def test_absolute_existing_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            p = f.name
        try:
            self.assertEqual(resolve_tracker_config_path(p), os.path.abspath(p))
        finally:
            os.unlink(p)


if __name__ == "__main__":
    unittest.main()
