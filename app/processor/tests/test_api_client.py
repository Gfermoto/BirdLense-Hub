"""Unit tests for the processor API client."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from api import API  # noqa: E402


class TestApiClient(unittest.TestCase):
    """API payload serialization tests."""

    def test_create_video_uses_processor_version_from_environment(self):
        """create_video should not hardcode processor_version."""
        with patch.dict(
            os.environ,
            {
                'API_URL_BASE': 'http://example.test/api',
                'PROCESSOR_VERSION': 'wave3-provenance-test',
            },
            clear=False,
        ):
            api = API()
            response = MagicMock()
            response.json.return_value = {'video_id': 7}
            with patch('api.requests.request', return_value=response) as request_mock:
                api.create_video(
                    species_video=[
                        {'species_name': 'Great Tit', 'confidence': 0.9}
                    ],
                    species_audio=[],
                    start_time=MagicMock(
                        isoformat=lambda: '2026-04-15T12:00:00+00:00'
                    ),
                    end_time=MagicMock(
                        isoformat=lambda: '2026-04-15T12:01:00+00:00'
                    ),
                    video_path='data/recordings/test/video.mp4',
                    spectrogram_path=None,
                )

        payload = request_mock.call_args.kwargs['json']
        self.assertEqual(payload['processor_version'], 'wave3-provenance-test')

    def test_send_request_tracks_ingest_conflict_reason_metric(self):
        with patch.dict(
            os.environ,
            {
                'API_URL_BASE': 'http://example.test/api',
            },
            clear=False,
        ):
            api = API()
            response = MagicMock()
            response.status_code = 409
            response.json.return_value = {'conflict_reason': 'payload_hash_mismatch'}
            http_error = requests.exceptions.HTTPError("409 conflict")
            http_error.response = response
            response.raise_for_status.side_effect = http_error
            counters = []
            with patch('api.requests.request', return_value=response):
                with patch('api.inc_counter', side_effect=lambda name, delta=1: counters.append((name, int(delta)))):
                    with self.assertRaises(requests.exceptions.HTTPError):
                        api._send_request('POST', 'videos', {'a': 1})
        names = [name for name, _ in counters]
        self.assertIn('api_ingest_conflict_total', names)
        self.assertIn('api_ingest_conflict_reason_payload_hash_mismatch_total', names)


if __name__ == '__main__':
    unittest.main()
