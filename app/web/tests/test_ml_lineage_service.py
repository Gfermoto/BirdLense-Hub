"""Снимок линейки модели (observability → model_lineage)."""

from app_config.app_config import app_config


def test_model_lineage_resolves_processor_models_binary_classifier(monkeypatch):
    """processor.models.binary|classifier — те же ключи, что у two-stage процессора."""
    from services.ml_lineage_service import current_model_lineage_snapshot

    orig = app_config.get

    def get_override(key, default=None):
        if key == "processor.models.binary":
            return "models/detection/weights/test-binary.pt"
        if key == "processor.models.classifier":
            return "models/classification/weights/test-classifier.pt"
        return orig(key, default)

    monkeypatch.setattr(app_config, "get", get_override)
    snap = current_model_lineage_snapshot()
    assert snap["artifacts"]["detector"]["exists"] is True
    assert snap["artifacts"]["classifier"]["exists"] is True
    assert snap["artifacts"]["detector"]["sha256"]
    assert snap["artifacts"]["classifier"]["sha256"]
