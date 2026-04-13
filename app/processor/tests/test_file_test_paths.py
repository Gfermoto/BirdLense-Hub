import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from file_test_paths import scan_video_files_in_dir  # noqa: E402


class TestFileTestPaths(unittest.TestCase):
    def test_scan_sorted_and_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "a.mp4"), "wb").close()
            open(os.path.join(tmp, "b.MOV"), "wb").close()
            with open(os.path.join(tmp, "skip.txt"), "w", encoding="utf-8") as f:
                f.write("x")
            got = scan_video_files_in_dir(tmp)
            self.assertEqual(len(got), 2)
            self.assertTrue(all(x.endswith((".mp4", ".MOV")) for x in got))
            self.assertEqual([os.path.basename(p) for p in got], ["a.mp4", "b.MOV"])

    def test_missing_dir_empty(self):
        self.assertEqual(scan_video_files_in_dir("/nonexistent/dir/xyz"), [])


if __name__ == "__main__":
    unittest.main()
