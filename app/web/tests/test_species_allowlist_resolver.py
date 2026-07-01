from services.species_catalog.allowlist import resolve_allowlist_path


def test_resolve_allowlist_prefers_engine_path_when_enabled(monkeypatch):
    cfg = {
        "species.catalog_allowlist_follow_classifier_engine": True,
        "species.catalog_allowlist_file": "models/classification/weights/legacy/class_names.txt",
        "species.catalog_allowlist_use_active_classifier": False,
        "processor.classifier_engine": "birder_eu",
        "processor.birder_eu_variant": "convnext_v2_tiny_eu-common256px",
        "processor.models.classifier": "models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx",
    }

    monkeypatch.setattr(
        "services.species_catalog.allowlist._processor_root",
        lambda: "/tmp/processor",
    )
    monkeypatch.setattr(
        "services.species_catalog.allowlist.os.path.isfile",
        lambda p: p.endswith("convnext_v2_tiny_eu-common256px/class_labels.txt"),
    )

    path = resolve_allowlist_path(lambda key, default=None: cfg.get(key, default))
    assert path == "/tmp/processor/models/classification/convnext_v2_tiny_eu-common256px/class_labels.txt"


def test_resolve_allowlist_uses_explicit_path_when_follow_disabled(monkeypatch):
    cfg = {
        "species.catalog_allowlist_follow_classifier_engine": False,
        "species.catalog_allowlist_file": "models/classification/weights/legacy/class_names.txt",
        "species.catalog_allowlist_use_active_classifier": False,
        "processor.classifier_engine": "birder_eu",
    }

    monkeypatch.setattr(
        "services.species_catalog.allowlist._processor_root",
        lambda: "/tmp/processor",
    )
    monkeypatch.setattr(
        "services.species_catalog.allowlist.os.path.isfile",
        lambda p: p.endswith("legacy/class_names.txt"),
    )

    path = resolve_allowlist_path(lambda key, default=None: cfg.get(key, default))
    assert path == "/tmp/processor/models/classification/weights/legacy/class_names.txt"
