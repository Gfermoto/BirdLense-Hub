"""Тесты resolve_recording_video_file (пересчёт треков, устаревшие пути в БД)."""

import os

import pytest


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(root))
    return root


def test_resolve_standard_data_recordings_path(data_root):
    from data_paths import resolve_recording_video_file

    rel = "data/recordings/2026/04/08/120000/video.mp4"
    full = data_root / "recordings/2026/04/08/120000/video.mp4"
    full.parent.mkdir(parents=True)
    full.write_bytes(b"1")
    got = resolve_recording_video_file(rel)
    assert got == os.path.realpath(str(full))


def test_resolve_legacy_path_relative_to_recordings(data_root):
    from data_paths import resolve_recording_video_file

    rel = "2026/04/08/120001/video.mp4"
    full = data_root / "recordings/2026/04/08/120001/video.mp4"
    full.parent.mkdir(parents=True)
    full.write_bytes(b"1")
    got = resolve_recording_video_file(rel)
    assert got == os.path.realpath(str(full))


def test_resolve_rejects_traversal(data_root):
    from data_paths import resolve_recording_video_file

    assert resolve_recording_video_file("../../../etc/passwd") is None


def test_resolve_missing_file_returns_none(data_root):
    from data_paths import resolve_recording_video_file

    assert (
        resolve_recording_video_file(
            "data/recordings/2026/04/08/120002/video.mp4",
        )
        is None
    )
