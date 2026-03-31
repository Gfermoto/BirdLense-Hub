"""Согласованность классов YOLO-классификатора, каталога Species и папок датасета."""

import pytest

from app_config.app_config import app_config
from models import Species, Video, VideoSpecies, db


@pytest.fixture(autouse=True)
def _disable_settings_passwords():
    old_admin = app_config.get('general.settings_password')
    old_contrib = app_config.get('general.contributor_password')
    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    try:
        yield
    finally:
        app_config.set('general.settings_password', old_admin)
        app_config.set('general.contributor_password', old_contrib)


def test_normalize_classifier_label_matches_processor_style():
    from services.species_dataset_alignment_service import normalize_classifier_label

    assert normalize_classifier_label('Parus_major_(Great_Tit)') == 'Parus major (Great Tit)'
    assert normalize_classifier_label('Blue_OR_Jay') == 'Blue/Jay'


def test_alignment_when_weights_unreadable(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        'load_classifier_labels_or_error',
        lambda _path: (None, 'classifier weights not found: /none'),
    )
    with app.app_context():
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt['classifier_readable'] is False
    assert rpt['classifier_error']


def test_alignment_model_class_matches_catalog_scientific_common(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        'load_classifier_labels_or_error',
        lambda _path: (['Parus_major_(Great_Tit)'], None),
    )
    with app.app_context():
        if not Species.query.filter_by(name='Parus major (Great Tit)').first():
            db.session.add(Species(name='Parus major (Great Tit)'))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt['classifier_readable'] is True
    assert rpt['in_classifier_not_in_catalog_count'] == 0


def test_alignment_extra_model_class_not_in_catalog(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        'load_classifier_labels_or_error',
        lambda _path: (['Parus_major_(Great_Tit)', 'Only_In_Model_Class'], None),
    )
    with app.app_context():
        if not Species.query.filter_by(name='Parus major (Great Tit)').first():
            db.session.add(Species(name='Parus major (Great Tit)'))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt['in_classifier_not_in_catalog_count'] == 1
    assert 'Only In Model Class' in rpt['in_classifier_not_in_catalog']


def test_alignment_species_with_video_not_in_model(app, monkeypatch):
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    monkeypatch.setattr(
        mod,
        'load_classifier_labels_or_error',
        lambda _path: (['Parus_major_(Great_Tit)'], None),
    )
    jay_name = 'Cyanocitta cristata (Blue Jay ALIGN_TEST_7e4b)'
    with app.app_context():
        if not Species.query.filter_by(name='Parus major (Great Tit)').first():
            db.session.add(Species(name='Parus major (Great Tit)'))
            db.session.commit()
        jay = Species(name=jay_name)
        db.session.add(jay)
        db.session.flush()
        v = Video(
            processor_version='t',
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path='align-test/7e4b.mp4',
        )
        db.session.add(v)
        db.session.flush()
        vs = VideoSpecies(
            video_id=v.id,
            species_id=jay.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.9,
            source='video',
            track_id=1,
        )
        db.session.add(vs)
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
        finally:
            VideoSpecies.query.filter_by(id=vs.id).delete()
            Video.query.filter_by(id=v.id).delete()
            Species.query.filter_by(id=jay.id).delete()
            db.session.commit()
    assert rpt['in_catalog_not_in_classifier_count'] >= 1
    names = {row['name'] for row in rpt['in_catalog_not_in_classifier']}
    assert jay_name in names


class TestClassifierDatasetAlignmentApi:
    def test_endpoint_ok_without_weights(self, client, monkeypatch):
        import services.species_dataset_alignment_service as mod

        monkeypatch.setattr(
            mod,
            'load_classifier_labels_or_error',
            lambda _path: (None, 'classifier weights not found'),
        )
        r = client.get('/api/ui/system/species-registry/classifier-dataset-alignment')
        assert r.status_code == 200
        body = r.get_json()
        assert body.get('classifier_readable') is False
