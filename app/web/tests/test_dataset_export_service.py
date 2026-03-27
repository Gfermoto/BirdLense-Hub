from datetime import datetime, timezone
import io
import json
import zipfile

from models import db, Species, Video, VideoSpecies
from services import dataset_export_service as des


class TestDatasetExportOrphans:
    def test_retro_export_skips_and_deletes_orphaned_detections(self, app):
        with app.app_context():
            vs = VideoSpecies(
                video_id=999999,
                species_id=999999,
                start_time=0.0,
                end_time=1.0,
                confidence=0.9,
                source='video',
                track_id=7,
            )
            db.session.add(vs)
            db.session.commit()
            orphan_id = vs.id

            result = des.retro_export_all_video_detections(min_confidence=0.0)
            assert result['skipped_orphaned'] >= 1
            assert result['deleted_orphaned'] >= 1
            assert db.session.get(VideoSpecies, orphan_id) is None

    def test_clean_dataset_remove_orphaned_keeps_only_valid_tracks(self, app, tmp_path, monkeypatch):
        with app.app_context():
            species = Species(name='Test Bird')
            db.session.add(species)
            db.session.flush()
            video = Video(
                processor_version='test',
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path='2026/03/27/000000/video.mp4',
            )
            db.session.add(video)
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    start_time=0.0,
                    end_time=1.0,
                    confidence=0.8,
                    source='video',
                    track_id=1,
                )
            )
            db.session.commit()

            train = tmp_path / 'dataset' / 'train' / 'Test Bird'
            train.mkdir(parents=True, exist_ok=True)
            (train / f'{video.id}_1_1.jpg').write_bytes(b'not-an-image')
            (train / '999999_1_2.jpg').write_bytes(b'not-an-image')
            monkeypatch.setattr(des, 'data_dir', lambda: str(tmp_path))

            result = des.clean_dataset(
                dry_run=True,
                remove_fullframe=False,
                remove_orphaned=True,
            )
            assert result['deleted_orphaned'] == 1

    def test_build_dataset_zip_ready_for_train_split(self, tmp_path, monkeypatch):
        train_a = tmp_path / 'dataset' / 'train' / 'A'
        train_b = tmp_path / 'dataset' / 'train' / 'B'
        train_a.mkdir(parents=True, exist_ok=True)
        train_b.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (train_a / f'1_1_{i}.jpg').write_bytes(b'jpeg')
            (train_b / f'2_1_{i}.jpg').write_bytes(b'jpeg')
        monkeypatch.setattr(des, 'data_dir', lambda: str(tmp_path))
        monkeypatch.setattr(des, '_get_image_dimensions', lambda _p: None)

        zip_bytes, err = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            split_seed=42,
            min_images_per_class=1,
        )
        assert err is None
        assert zip_bytes

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), 'r')
        names = set(zf.namelist())
        assert 'classes.txt' in names
        assert any(n.startswith('train/A/') for n in names)
        assert any(n.startswith('val/A/') for n in names)
        assert any(n.startswith('train/B/') for n in names)
        assert any(n.startswith('val/B/') for n in names)

    def test_ready_for_train_test_split_and_manifest(self, tmp_path, monkeypatch):
        train_a = tmp_path / 'dataset' / 'train' / 'A'
        train_a.mkdir(parents=True, exist_ok=True)
        for i in range(20):
            (train_a / f'100_{i}_{i}.jpg').write_bytes(b'x')
        monkeypatch.setattr(des, 'data_dir', lambda: str(tmp_path))
        monkeypatch.setattr(des, '_get_image_dimensions', lambda _p: None)

        zip_bytes, err = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            test_ratio=0.15,
            split_seed=7,
            min_images_per_class=1,
        )
        assert err is None
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), 'r')
        names = set(zf.namelist())
        assert any(n.startswith('test/A/') for n in names)
        meta = json.loads(zf.read('dataset_info.json').decode())
        assert meta['manifest']['schema'] == 'birdlense_dataset_export_v2'
        assert 'fingerprint_sha256_16' in meta['manifest']
        assert 'quality' in meta
        assert meta['quality']['duplicate_track_count'] == 0

    def test_strict_quality_rejects_duplicate_tracks(self, tmp_path, monkeypatch):
        train_a = tmp_path / 'dataset' / 'train' / 'A'
        train_a.mkdir(parents=True, exist_ok=True)
        (train_a / '1_1_10.jpg').write_bytes(b'a')
        (train_a / '1_1_11.jpg').write_bytes(b'b')
        for i in range(10):
            (train_a / f'9_{i}_{i}.jpg').write_bytes(b'x')
        monkeypatch.setattr(des, 'data_dir', lambda: str(tmp_path))
        monkeypatch.setattr(des, '_get_image_dimensions', lambda _p: None)

        zip_ok, err_ok = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            test_ratio=0.0,
            split_seed=1,
            min_images_per_class=1,
            strict_quality=False,
        )
        assert err_ok is None
        meta = json.loads(
            zipfile.ZipFile(io.BytesIO(zip_ok), 'r').read('dataset_info.json').decode(),
        )
        assert meta['quality']['duplicate_track_count'] >= 1

        zip_bad, err_bad = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            test_ratio=0.0,
            split_seed=1,
            min_images_per_class=1,
            strict_quality=True,
        )
        assert zip_bad is None
        assert err_bad and 'strict_quality' in err_bad

    def test_strict_quality_rejects_skipped_small_classes(self, tmp_path, monkeypatch):
        train_a = tmp_path / 'dataset' / 'train' / 'Enough'
        train_b = tmp_path / 'dataset' / 'train' / 'Tiny'
        train_a.mkdir(parents=True, exist_ok=True)
        train_b.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (train_a / f'1_1_{i}.jpg').write_bytes(b'x')
        (train_b / '2_1_0.jpg').write_bytes(b'y')
        monkeypatch.setattr(des, 'data_dir', lambda: str(tmp_path))
        monkeypatch.setattr(des, '_get_image_dimensions', lambda _p: None)

        zip_ok, err_ok = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            split_seed=1,
            min_images_per_class=3,
            strict_quality=False,
        )
        assert err_ok is None
        meta = json.loads(
            zipfile.ZipFile(io.BytesIO(zip_ok), 'r').read('dataset_info.json').decode(),
        )
        assert 'Tiny' in (meta.get('classes_skipped_too_small') or [])

        zip_bad, err_bad = des.build_dataset_zip(
            ready_for_train=True,
            val_ratio=0.2,
            split_seed=1,
            min_images_per_class=3,
            strict_quality=True,
        )
        assert zip_bad is None
        assert err_bad and 'strict_quality' in err_bad
        assert 'Tiny' in err_bad
