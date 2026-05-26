"""Согласованность классов YOLO-классификатора, каталога Species и папок датасета."""

import pytest

from app_config.app_config import app_config
from models import Species, Video, VideoSpecies, db


@pytest.fixture(autouse=True)
def _disable_settings_passwords():
    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        yield
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)


def test_normalize_classifier_label_matches_processor_style():
    from services.species_dataset_alignment_service import normalize_classifier_label

    assert normalize_classifier_label("Parus_major_(Great_Tit)") == "Parus major (Great Tit)"
    assert normalize_classifier_label("Blue_OR_Jay") == "Blue/Jay"


def test_resolve_classifier_weights_prefers_efficientnet_engine(monkeypatch):
    from services.species_dataset_alignment_service import resolve_classifier_weights_path

    cfg = {
        "processor.classifier_engine": "efficientnet_b2",
        "processor.models.classifier_efficientnet_b2": "models/classification/weights/custom_b2",
    }
    abs_path, log_path = resolve_classifier_weights_path(lambda key, default=None: cfg.get(key, default))
    assert log_path == "models/classification/weights/custom_b2"
    assert abs_path.endswith("/app/processor/models/classification/weights/custom_b2")


def test_load_classifier_labels_reads_class_labels_txt(tmp_path):
    from services.species_dataset_alignment_service import load_classifier_labels_or_error

    model_dir = tmp_path / "birds_classifier_efficientnetb2"
    model_dir.mkdir(parents=True)
    (model_dir / "class_labels.txt").write_text("Bird A\nBird B\n", encoding="utf-8")

    labels, err = load_classifier_labels_or_error(str(model_dir))
    assert err is None
    assert labels == ["Bird A", "Bird B"]


def test_alignment_when_weights_unreadable(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (None, "classifier weights not found: /none"),
    )
    with app.app_context():
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt["classifier_readable"] is False
    assert rpt["classifier_error"]


def test_alignment_model_class_matches_catalog_scientific_common(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )
    with app.app_context():
        if not Species.query.filter_by(name="Parus major (Great Tit)").first():
            db.session.add(Species(name="Parus major (Great Tit)"))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt["classifier_readable"] is True
    assert rpt["in_classifier_not_in_catalog_count"] == 0


def test_alignment_common_name_catalog_row_matches_scientific_common_label(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Aegithalos_caudatus_(Long-tailed_Tit)"], None),
    )
    with app.app_context():
        if not Species.query.filter_by(name="Long-tailed Tit").first():
            db.session.add(Species(name="Long-tailed Tit"))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt["in_classifier_not_in_catalog_count"] == 0
    assert "Aegithalos caudatus (Long-tailed Tit)" not in rpt["in_classifier_not_in_catalog"]


def test_alignment_extra_model_class_not_in_catalog(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)", "Only_In_Model_Class"], None),
    )
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: [],
    )
    with app.app_context():
        if not Species.query.filter_by(name="Parus major (Great Tit)").first():
            db.session.add(Species(name="Parus major (Great Tit)"))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt["in_classifier_not_in_catalog_count"] == 1
    assert "Only In Model Class" in rpt["in_classifier_not_in_catalog"]


def test_alignment_ignores_model_classes_outside_allowlist(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)", "Only_In_Model_Class"], None),
    )
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: ["Parus major (Great Tit)"],
    )
    with app.app_context():
        if not Species.query.filter_by(name="Parus major (Great Tit)").first():
            db.session.add(Species(name="Parus major (Great Tit)"))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    assert rpt["in_classifier_not_in_catalog_count"] == 0
    assert "Only In Model Class" not in rpt["in_classifier_not_in_catalog"]


def test_alignment_species_outside_allowlist_but_present_in_model_is_not_flagged(
    app,
    monkeypatch,
):
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    outside_name = "Knob Billed Duck ALIGN_IN_MODEL"
    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (
            ["Parus_major_(Great_Tit)", "Knob_Billed_Duck_ALIGN_IN_MODEL"],
            None,
        ),
    )
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: ["Parus major (Great Tit)"],
    )

    with app.app_context():
        duck = Species(name=outside_name)
        db.session.add(duck)
        db.session.flush()
        video = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/in-model-outside-allowlist.mp4",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=duck.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.8,
                source="video",
            ),
        )
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(
                db.session,
                app_config.get,
            )
        finally:
            VideoSpecies.query.filter_by(video_id=video.id).delete()
            Video.query.filter_by(id=video.id).delete()
            Species.query.filter_by(id=duck.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert outside_name not in names


def test_alignment_species_with_video_not_in_model(app, monkeypatch):
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )
    jay_name = "Cyanocitta cristata (Blue Jay ALIGN_TEST_7e4b)"
    with app.app_context():
        if not Species.query.filter_by(name="Parus major (Great Tit)").first():
            db.session.add(Species(name="Parus major (Great Tit)"))
            db.session.commit()
        jay = Species(name=jay_name)
        db.session.add(jay)
        db.session.flush()
        v = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/7e4b.mp4",
        )
        db.session.add(v)
        db.session.flush()
        vs = VideoSpecies(
            video_id=v.id,
            species_id=jay.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.9,
            source="video",
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
    assert rpt["in_catalog_not_in_classifier_count"] >= 1
    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert jay_name in names


def test_alignment_does_not_treat_allowlist_only_species_as_classifier_match(app, monkeypatch):
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    duck_name = "Knob Billed Duck ALIGN_ALLOWLIST_ONLY"
    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: [duck_name],
    )

    with app.app_context():
        duck = Species(name=duck_name)
        db.session.add(duck)
        db.session.flush()
        video = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/allowlist-only.mp4",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=duck.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.8,
                source="video",
            ),
        )
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(
                db.session,
                app_config.get,
            )
        finally:
            VideoSpecies.query.filter_by(video_id=video.id).delete()
            Video.query.filter_by(id=video.id).delete()
            Species.query.filter_by(id=duck.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert duck_name in names


def test_alignment_hint_when_allowlist_and_classifier_counts_differ(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: ["Parus major (Great Tit)", "Extra allowlist row"],
    )
    with app.app_context():
        if not Species.query.filter_by(name="Parus major (Great Tit)").first():
            db.session.add(Species(name="Parus major (Great Tit)"))
            db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
    hint = rpt.get("hints", {}).get("allowlist_vs_classifier_count", "")
    assert "allowlist lines=2" in hint
    assert "classifier classes=1" in hint
    assert "dump_classifier_allowlist" in hint


def test_alignment_ignores_birds_parent_not_in_classifier(app, monkeypatch):
    """Родитель каталога «Birds» не сравнивается с классами YOLO."""
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )

    with app.app_context():
        birds = Species.query.filter_by(name="Birds").first()
        created = False
        if not birds:
            birds = Species(name="Birds")
            db.session.add(birds)
            db.session.flush()
            created = True
        video = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/birds-parent.mp4",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=birds.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.8,
                source="video",
            ),
        )
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
        finally:
            VideoSpecies.query.filter_by(video_id=video.id).delete()
            Video.query.filter_by(id=video.id).delete()
            if created:
                Species.query.filter_by(id=birds.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert "Birds" not in names


def test_alignment_generic_bird_flagged_when_not_in_classifier(app, monkeypatch):
    """Вид «Bird» участвует в сравнении: без класса в модели — в рассогласовании."""
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )

    with app.app_context():
        b = Species.query.filter_by(name="Bird").first()
        created = False
        if not b:
            b = Species(name="Bird")
            db.session.add(b)
            db.session.flush()
            created = True
        video = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/generic-bird.mp4",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=b.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.8,
                source="video",
            ),
        )
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
        finally:
            VideoSpecies.query.filter_by(video_id=video.id).delete()
            Video.query.filter_by(id=video.id).delete()
            if created:
                Species.query.filter_by(id=b.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert "Bird" in names


def test_alignment_apostrophe_variants_match_classifier(app, monkeypatch):
    """БД с ASCII apostrophe, метка YOLO с типографским U+2019 — один ключ."""
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    label = "Abert\u2019s_Towhee_ALIGN_APOST"  # RIGHT SINGLE QUOTATION MARK
    catalog_name = "Abert's Towhee ALIGN APOST"
    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: ([label], None),
    )

    with app.app_context():
        sp = Species(name=catalog_name)
        db.session.add(sp)
        db.session.flush()
        v = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/apost.mp4",
        )
        db.session.add(v)
        db.session.flush()
        vs = VideoSpecies(
            video_id=v.id,
            species_id=sp.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.9,
            source="video",
        )
        db.session.add(vs)
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
        finally:
            VideoSpecies.query.filter_by(id=vs.id).delete()
            Video.query.filter_by(id=v.id).delete()
            Species.query.filter_by(id=sp.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert catalog_name not in names


def test_alignment_ignores_service_species_not_in_classifier(app, monkeypatch):
    import services.species_dataset_alignment_service as mod
    from datetime import datetime, timezone

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )

    with app.app_context():
        rodent = Species.query.filter_by(name="Rodent").first()
        created_rodent = False
        if not rodent:
            rodent = Species(name="Rodent")
            db.session.add(rodent)
            db.session.flush()
            created_rodent = True
        video = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="align-test/rodent.mp4",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=rodent.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.8,
                source="video",
            ),
        )
        db.session.commit()
        try:
            rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)
        finally:
            VideoSpecies.query.filter_by(video_id=video.id).delete()
            Video.query.filter_by(id=video.id).delete()
            if created_rodent:
                Species.query.filter_by(id=rodent.id).delete()
            db.session.commit()

    names = {row["name"] for row in rpt["in_catalog_not_in_classifier"]}
    assert "Rodent" not in names


def test_alignment_ignores_service_dataset_folders(app, monkeypatch):
    import services.species_dataset_alignment_service as mod

    monkeypatch.setattr(
        mod,
        "load_classifier_labels_or_error",
        lambda _path: (["Parus_major_(Great_Tit)"], None),
    )
    monkeypatch.setattr(
        mod,
        "_dataset_split_class_names",
        lambda _get: {"Rodent", "Unknown", "Birds"},
    )

    with app.app_context():
        if not Species.query.filter_by(name="Rodent").first():
            db.session.add(Species(name="Rodent"))
        if not Species.query.filter_by(name="Unknown").first():
            db.session.add(Species(name="Unknown"))
        db.session.commit()
        rpt = mod.build_classifier_dataset_alignment_report(db.session, app_config.get)

    assert rpt["dataset_folders_species_not_in_classifier_count"] == 0
    assert rpt["dataset_folders_species_not_in_classifier"] == []


def test_dataset_split_class_names_uses_real_folders_only(tmp_path, monkeypatch):
    import services.species_dataset_alignment_service as mod

    dataset_root = tmp_path / "dataset" / "train" / "Observed Species"
    dataset_root.mkdir(parents=True)
    monkeypatch.setattr(mod, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_names",
        lambda _get: ["Allowlist Only"],
    )

    names = mod._dataset_split_class_names(app_config.get)

    assert "Observed Species" in names
    assert "Allowlist Only" not in names


def test_species_name_match_keys_include_dataset_sanitized_variant():
    from services.species_dataset_alignment_service import _species_name_match_keys

    keys = _species_name_match_keys("Blue/Green Bird", {})

    assert "blue green bird" in keys


class TestClassifierDatasetAlignmentApi:
    def test_endpoint_ok_without_weights(self, client, monkeypatch):
        import services.species_dataset_alignment_service as mod

        monkeypatch.setattr(
            mod,
            "load_classifier_labels_or_error",
            lambda _path: (None, "classifier weights not found"),
        )
        r = client.get("/api/ui/system/species-registry/classifier-dataset-alignment")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("classifier_readable") is False
