"""Тесты зеркалирования записей на SFTP (#350)."""

import os
import sys
import threading
from unittest.mock import patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)


@pytest.fixture
def mirror_mod(monkeypatch):
    """Загрузить модуль с изолированным app_config."""
    import recordings_remote_mirror as mod

    class _Cfg:
        config = {
            'storage': {
                'recordings_mirror': {
                    'enabled': False,
                    'protocol': 'sftp',
                    'host': '',
                    'port': 22,
                    'username': '',
                    'remote_base_path': '/nas/rec',
                    'max_concurrent_uploads': 2,
                    'upload_retries': 2,
                    'retry_backoff_seconds': 0.01,
                    'strict_host_key': False,
                    'known_hosts_path': '',
                    'ssh_private_key_path': '',
                    'delete_local_after_success': False,
                },
            },
        }

        @staticmethod
        def get(key, default=None):
            keys = key.split('.')
            v = _Cfg.config
            for k in keys:
                if not isinstance(v, dict) or k not in v:
                    return default
                v = v[k]
            return v

    monkeypatch.setattr(mod, 'app_config', _Cfg(), raising=False)
    return mod


def test_session_relative_valid(mirror_mod, tmp_path):
    rec = str(tmp_path / 'recordings')
    sess = str(tmp_path / 'recordings' / '2026' / '04' / '27' / '120000')
    os.makedirs(sess, exist_ok=True)
    assert mirror_mod._session_relative_to_recordings(sess, rec) == '2026/04/27/120000'


def test_session_relative_rejects_escape(mirror_mod, tmp_path):
    rec = str(tmp_path / 'recordings')
    os.makedirs(rec, exist_ok=True)
    other = str(tmp_path / 'other' / '2026' / '04' / '27' / '120000')
    os.makedirs(other, exist_ok=True)
    assert mirror_mod._session_relative_to_recordings(other, rec) is None


def test_schedule_no_thread_when_disabled(mirror_mod):
    started = []

    def capture_thread(*a, **kw):
        started.append(1)
        return threading.Thread(*a, **kw)

    with patch.object(mirror_mod.threading, 'Thread', side_effect=capture_thread):
        mirror_mod.schedule_recordings_session_mirror('/tmp/fake-session')
    assert started == []


def test_schedule_starts_thread_when_enabled(mirror_mod, monkeypatch, tmp_path):
    data = tmp_path
    rec = data / 'recordings'
    d = rec / '2026' / '04' / '27' / '120000'
    d.mkdir(parents=True)
    (d / 'video.mp4').write_bytes(b'x')
    monkeypatch.setattr(mirror_mod, 'get_data_dir', lambda: str(data))

    mirror_mod.app_config.config['storage']['recordings_mirror']['enabled'] = True
    mirror_mod.app_config.config['storage']['recordings_mirror']['host'] = '127.0.0.1'
    mirror_mod.app_config.config['storage']['recordings_mirror']['username'] = 'u'

    def fake_upload_impl(_session_dir: str) -> None:
        mirror_mod.inc_counter('recordings_mirror_uploads_success_total')

    started = []
    real_thread_cls = mirror_mod.threading.Thread

    def capture_thread(*a, **kw):
        t = real_thread_cls(*a, **kw)
        started.append(t)
        return t

    with patch.object(mirror_mod.threading, 'Thread', side_effect=capture_thread):
        with patch.object(mirror_mod, '_upload_session_impl', side_effect=fake_upload_impl):
            mirror_mod.schedule_recordings_session_mirror(str(d))

    assert len(started) == 1
    started[0].join(timeout=5)
    assert not started[0].is_alive()
