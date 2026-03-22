"""Gallery opt-in upload (#80): background thread must use Flask app context."""
from datetime import datetime, timezone


class TestGalleryUploadThread:
    def test_gallery_thread_wraps_upload_in_app_context(self, monkeypatch):
        """Regression: upload ran outside app context → SQLAlchemy / DB failed silently.

        Uses a minimal Flask app (not full create_app) so the test stays fast and does not
        double-run startup hooks from web.app.
        """
        from flask import Flask

        import routes.processor_routes as processor_routes

        mini = Flask(__name__)
        seen = []

        def spy(video_id):
            from flask import has_app_context

            seen.append((video_id, has_app_context()))

        monkeypatch.setattr(
            processor_routes,
            'upload_video_detections_to_gallery',
            spy,
        )
        processor_routes._run_gallery_upload_thread(mini, 42)
        assert seen == [(42, True)]


class TestGalleryUploadService:
    def test_upload_single_detection_posts_multipart(self, monkeypatch):
        """Multipart POST for one VideoSpecies row (no full Flask create_app — avoids double startup)."""
        from types import SimpleNamespace

        from app_config.app_config import app_config as real_config
        from services.gallery_upload_service import _upload_video_species_to_gallery

        posts = []

        def fake_post(url, files=None, data=None, timeout=None):
            class R:
                status_code = 200
                text = 'ok'

            posts.append({'url': url, 'files': files, 'data': dict(data or {})})
            return R()

        monkeypatch.setattr(
            'services.gallery_upload_service.requests.post',
            fake_post,
        )
        monkeypatch.setattr(
            'services.gallery_upload_service.extract_detection_frame_cropped',
            lambda *a, **k: b'\xff\xd8\xff\xd9',
        )

        overrides = {
            'gallery.upload_url': 'http://gallery.example/upload',
            'secrets.latitude': '55.0',
            'secrets.longitude': '37.0',
        }

        def get_cfg(key, default=None):
            if key in overrides:
                return overrides[key]
            return real_config.get(key, default)

        monkeypatch.setattr(
            'services.gallery_upload_service.app_config.get',
            get_cfg,
        )

        st = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        video = SimpleNamespace(
            id=7,
            start_time=st,
            video_path='data/recordings/2025/06/01/120000/video.mp4',
        )
        vs = SimpleNamespace(
            id=99,
            source='video',
            frames='[{"t": 0.5, "bbox": [0.1, 0.2, 0.8, 0.9]}]',
            start_time=0.0,
            end_time=1.0,
            confidence=0.95,
        )
        ok = _upload_video_species_to_gallery(vs, video, 'GalleryUploadBird')
        assert ok is True
        assert len(posts) == 1
        assert posts[0]['url'] == 'http://gallery.example/upload'
        assert posts[0]['data']['species'] == 'GalleryUploadBird'
        assert posts[0]['data']['detection_id'] == '99'
        assert posts[0]['data']['video_id'] == '7'
        assert posts[0]['data']['latitude'] == '55.0'
        assert posts[0]['data']['longitude'] == '37.0'
        assert 'image' in posts[0]['files']
