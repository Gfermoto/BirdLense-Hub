"""Tests for scripts/verify_action_labeling_gates.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = next(
    (
        p
        for p in (Path(__file__).resolve().parents[3], Path('/workspace'))
        if (p / 'scripts').exists()
    ),
    Path(__file__).resolve().parents[3],
)


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'verify_action_labeling_gates.py'
    spec = importlib.util.spec_from_file_location(
        'verify_action_labeling_gates',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_action_labeling_gates'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestVerifyActionLabelingGates(unittest.TestCase):
    """Validation tests for action-labeling gate script."""

    @classmethod
    def setUpClass(cls):
        """Load target module once."""
        cls.mod = _load_module()

    def test_verify_action_gates_ok(self):
        """Green path for API payload and dataset row."""
        action_events = {
            'schema': 'video_action_events@v1',
            'available': True,
            'events': [
                {
                    'label': 'arrival',
                    'source': 'weak_label',
                    'time_offset': 1.0,
                    'time': '2026-05-01T00:00:01Z',
                    'confidence': 0.6,
                },
                {
                    'label': 'departure',
                    'source': 'weak_label',
                    'time_offset': 3.0,
                    'time': '2026-05-01T00:00:03Z',
                    'confidence': 0.55,
                },
            ],
        }
        dataset_rows = [
            {
                'video_id': 1,
                'track_id': 2,
                'camera_id': 'cam-1',
                'action_label': 'possible_feeding',
                't_start_ms': 0,
                't_end_ms': 500,
                'confidence': 0.8,
                'annotator_id': 'op-1',
                'created_at_utc': '2026-05-01T00:00:00Z',
            }
        ]
        ok, out = self.mod.verify_action_gates(
            action_events=action_events,
            dataset_rows=dataset_rows,
            min_events=1,
            min_dataset_rows=1,
            min_segment_ms=300,
            allow_extended_labels=False,
        )
        self.assertTrue(ok)
        self.assertTrue(out['ok'])

    def test_verify_action_gates_fail_short_segment(self):
        """Fail path for invalid short action segment."""
        dataset_rows = [
            {
                'video_id': 1,
                'track_id': 2,
                'camera_id': 'cam-1',
                'action_label': 'arrival',
                't_start_ms': 100,
                't_end_ms': 200,
                'confidence': 0.7,
                'annotator_id': 'op-1',
                'created_at_utc': '2026-05-01T00:00:00Z',
            }
        ]
        ok, out = self.mod.verify_action_gates(
            action_events=None,
            dataset_rows=dataset_rows,
            min_events=1,
            min_dataset_rows=1,
            min_segment_ms=300,
            allow_extended_labels=False,
        )
        self.assertFalse(ok)
        self.assertFalse(out['ok'])
        self.assertTrue(out['errors'])

    def test_cli_main_ok(self):
        """CLI returns zero for valid fixture files."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            action_events = base / 'action_events.json'
            dataset_jsonl = base / 'dataset.jsonl'
            action_events.write_text(
                json.dumps(
                    {
                        'schema': 'video_action_events@v1',
                        'available': True,
                        'events': [
                            {
                                'label': 'arrival',
                                'source': 'weak_label',
                                'time_offset': 1.0,
                                'time': '2026-05-01T00:00:01Z',
                                'confidence': 0.6,
                            }
                        ],
                    }
                ),
                encoding='utf-8',
            )
            dataset_jsonl.write_text(
                json.dumps(
                    {
                        'video_id': 1,
                        'track_id': 2,
                        'camera_id': 'cam-1',
                        'action_label': 'departure',
                        't_start_ms': 1000,
                        't_end_ms': 1700,
                        'confidence': 0.9,
                        'annotator_id': 'op-2',
                        'created_at_utc': '2026-05-01T00:00:00Z',
                    }
                )
                + '\n',
                encoding='utf-8',
            )
            argv_prev = sys.argv
            try:
                sys.argv = [
                    'verify_action_labeling_gates.py',
                    '--action-events',
                    str(action_events),
                    '--dataset-jsonl',
                    str(dataset_jsonl),
                    '--min-events',
                    '1',
                    '--min-dataset-rows',
                    '1',
                ]
                rc = self.mod.main()
            finally:
                sys.argv = argv_prev
            self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
