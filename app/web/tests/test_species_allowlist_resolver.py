from services.species_catalog.allowlist import resolve_allowlist_path


def test_resolve_allowlist_prefers_engine_path_when_enabled(monkeypatch):
    cfg = {
        "species.catalog_allowlist_follow_classifier_engine": True,
        "species.catalog_allowlist_file": "models/classification/weights/legacy/class_names.txt",
        "processor.classifier_engine": "efficientnet_b2",
        "processor.models.classifier_efficientnet_b2": "models/classification/weights/birds_classifier_efficientnetb2",
    }

    monkeypatch.setattr(
        "services.species_catalog.allowlist._processor_root",
        lambda: "/tmp/processor",
    )
    monkeypatch.setattr(
        "services.species_catalog.allowlist.os.path.isfile",
        lambda p: p.endswith("birds_classifier_efficientnetb2/class_labels.txt"),
    )

    path = resolve_allowlist_path(lambda key, default=None: cfg.get(key, default))
    assert path == "/tmp/processor/models/classification/weights/birds_classifier_efficientnetb2/class_labels.txt"


def test_resolve_allowlist_uses_explicit_path_when_follow_disabled(monkeypatch):
    cfg = {
        "species.catalog_allowlist_follow_classifier_engine": False,
        "species.catalog_allowlist_file": "models/classification/weights/legacy/class_names.txt",
        "processor.classifier_engine": "efficientnet_b2",
        "processor.models.classifier_efficientnet_b2": "models/classification/weights/birds_classifier_efficientnetb2",
    }

    monkeypatch.setattr(
        "services.species_catalog.allowlist._processor_root",
        lambda: "/tmp/processor",
    )

    path = resolve_allowlist_path(lambda key, default=None: cfg.get(key, default))
    assert path == "/tmp/processor/models/classification/weights/legacy/class_names.txt"
