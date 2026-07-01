"""Tests for ml_lineage_service on Orin ONNX paths."""

from pathlib import Path

from app_config.app_config import app_config


def test_model_lineage_resolves_processor_models_binary_classifier(monkeypatch, tmp_path):
    from services import artifact_paths_service as aps
    from services.ml_lineage_service import current_model_lineage_snapshot

    det = tmp_path / "app" / "processor" / "models" / "detection" / "weights"
    det.mkdir(parents=True)
    (det / "test-binary.onnx").write_bytes(b"onnx")
    clf = tmp_path / "app" / "processor" / "models" / "classification" / "weights"
    clf.mkdir(parents=True)
    (clf / "test-classifier.onnx").write_bytes(b"cls")

    monkeypatch.setattr(aps, "repo_root_path", lambda: str(tmp_path))
    import services.ml_lineage_service as mls

    monkeypatch.setattr(mls, "repo_root_path", lambda: str(tmp_path))
    monkeypatch.delenv("BIRDLENSE_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", raising=False)

    orig = app_config.get

    def get_override(key, default=None):
        if key == "processor.inference_backend":
            return "onnxruntime"
        if key == "processor.classifier_inference_backend":
            return "onnxruntime"
        if key == "processor.models.binary":
            return "models/detection/weights/test-binary.onnx"
        if key == "processor.models.classifier":
            return "models/classification/weights/test-classifier.onnx"
        return orig(key, default)

    monkeypatch.setattr(app_config, "get", get_override)
    snap = current_model_lineage_snapshot()
    assert snap["artifacts"]["detector"]["exists"] is True
    assert snap["artifacts"]["classifier"]["exists"] is True
    assert snap["artifacts"]["detector"]["sha256"]
    assert snap["artifacts"]["classifier"]["sha256"]
    assert Path(snap["artifacts"]["detector"]["configured_path"]).is_file()
    assert Path(snap["artifacts"]["classifier"]["configured_path"]).is_file()
    assert snap["artifacts"]["detector"]["detector_backend"] == "onnxruntime"
    assert snap["artifacts"]["classifier"]["classifier_backend"] == "onnxruntime"


def test_model_lineage_onnxruntime_detector_backend(monkeypatch, tmp_path):
    from services import artifact_paths_service as aps
    from services.ml_lineage_service import current_model_lineage_snapshot

    det = tmp_path / "app" / "processor" / "models" / "detection" / "weights"
    det.mkdir(parents=True)
    (det / "detector.onnx").write_bytes(b"onnx")
    clf = tmp_path / "app" / "processor" / "models" / "classification" / "weights"
    clf.mkdir(parents=True)
    (clf / "classifier.onnx").write_bytes(b"cls")

    monkeypatch.setattr(aps, "repo_root_path", lambda: str(tmp_path))
    import services.ml_lineage_service as mls

    monkeypatch.setattr(mls, "repo_root_path", lambda: str(tmp_path))
    monkeypatch.setenv("BIRDLENSE_INFERENCE_BACKEND", "onnxruntime")

    orig = app_config.get

    def get_override(key, default=None):
        if key == "processor.models.binary":
            return "models/detection/weights/detector.onnx"
        if key == "processor.models.classifier":
            return "models/classification/weights/classifier.onnx"
        if key == "processor.classifier_inference_backend":
            return "onnxruntime"
        return orig(key, default)

    monkeypatch.setattr(app_config, "get", get_override)
    snap = current_model_lineage_snapshot()
    det_art = snap["artifacts"]["detector"]
    assert det_art["detector_backend"] == "onnxruntime"
    assert det_art["exists"] is True
