import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from recording_ingest_gate import log_missing_video_gate  # noqa: E402


class TestRecordingIngestGate(unittest.TestCase):
    def test_log_missing_video_gate_ignores_empty_api(self):
        log_missing_video_gate(
            None,
            detection_count=1,
            video_path_for_api="data/recordings/x/video.mp4",
            video_output="/tmp/missing.mp4",
        )

    def test_logs_missing_file_reason_code(self):
        api = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = os.path.join(tmp, "missing.mp4")
            log_missing_video_gate(
                api,
                detection_count=1,
                video_path_for_api="data/recordings/2026/05/16/120000/video.mp4",
                video_output=missing_path,
            )
        api.activity_log.assert_called_once_with(
            type="ingest_gate",
            data={
                "reason": "video_file_missing",
                "reason_code": "REC_FILE_MISSING",
                "stage": "processor_finalize",
                "video_path": "data/recordings/2026/05/16/120000/video.mp4",
                "video_output": missing_path,
                "detection_count": 1,
                "file_exists": False,
                "file_size_bytes": 0,
            },
        )

    def test_logs_unplayable_file_reason_code_when_file_exists(self):
        api = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = os.path.join(tmp, "broken.mp4")
            with open(bad_file, "wb") as fh:
                fh.write(b"not-a-real-mp4")
            log_missing_video_gate(
                api,
                detection_count=2,
                video_path_for_api="data/recordings/2026/05/16/120001/video.mp4",
                video_output=bad_file,
            )
        api.activity_log.assert_called_once()
        payload = api.activity_log.call_args.kwargs["data"]
        self.assertEqual(payload["reason_code"], "REC_FILE_UNPLAYABLE")
        self.assertTrue(payload["file_exists"])
        self.assertGreater(payload["file_size_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
