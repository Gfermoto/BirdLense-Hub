"""Unit tests for the processor API client."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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


if __name__ == '__main__':
    unittest.main()
