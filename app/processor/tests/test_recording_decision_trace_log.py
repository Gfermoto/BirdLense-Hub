"""Tests for recording decision trace logging helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_decision_trace_log import write_decision_trace_activity  # noqa: E402


class TestRecordingDecisionTraceLog(unittest.TestCase):
    def test_writes_activity_when_trace_has_rows(self):
        api = MagicMock()
        api.activity_log_async = None
        trace = {"persisted_tracks": [{"species_name": "Robin"}], "rejected_tracks": []}

        write_decision_trace_activity(api, trace)

        api.activity_log.assert_called_once_with("decision_trace", trace)

    def test_prefers_async_activity_log(self):
        api = MagicMock()
        trace = {"persisted_tracks": [{"species_name": "Robin"}], "rejected_tracks": []}

        write_decision_trace_activity(api, trace)

        api.activity_log_async.assert_called_once_with("decision_trace", trace)
        api.activity_log.assert_not_called()

    def test_skips_empty_trace(self):
        api = MagicMock()

        write_decision_trace_activity(api, {"persisted_tracks": [], "rejected_tracks": []})

        api.activity_log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
