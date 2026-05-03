"""Снимок линейки модели (observability → model_lineage)."""

from pathlib import Path

from app_config.app_config import app_config


def test_model_lineage_resolves_processor_models_binary_classifier(monkeypatch, tmp_path):
    """processor.models.binary|classifier — как у two-stage процессора.

    app/processor/models/ в .gitignore: в CI нет фиктивных .pt; создаём их в tmp_path.
    """
    from services import artifact_paths_service as aps
    from services.ml_lineage_service import current_model_lineage_snapshot

    det = tmp_path / "app" / "processor" / "models" / "detection" / "weights"
    det.mkdir(parents=True)
    (det / "test-binary.pt").write_bytes(b"bin")
    clf = tmp_path / "app" / "processor" / "models" / "classification" / "weights"
    clf.mkdir(parents=True)
    (clf / "test-classifier.pt").write_bytes(b"cls")

    monkeypatch.setattr(aps, "repo_root_path", lambda: str(tmp_path))
    # Stabilize against host env forcing OpenVINO backend.
    monkeypatch.delenv("BIRDLENSE_INFERENCE_BACKEND", raising=False)

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
    assert Path(snap["artifacts"]["detector"]["configured_path"]).is_file()
    assert Path(snap["artifacts"]["classifier"]["configured_path"]).is_file()


def test_model_lineage_openvino_detector_resolves_binary_openvino(monkeypatch, tmp_path):
    """Метка detector_backend и путь IR при processor.inference_backend=openvino (#371)."""
    from services import artifact_paths_service as aps
    from services.ml_lineage_service import current_model_lineage_snapshot

    ov_dir = tmp_path / "app" / "processor" / "ov_export"
    ov_dir.mkdir(parents=True)
    (ov_dir / "model.xml").write_text("<net />", encoding="utf-8")
    clf_dir = tmp_path / "app" / "processor" / "models" / "classification" / "weights"
    clf_dir.mkdir(parents=True)
    (clf_dir / "c.pt").write_bytes(b"cls")

    monkeypatch.setattr(aps, "repo_root_path", lambda: str(tmp_path))
    monkeypatch.setenv("BIRDLENSE_INFERENCE_BACKEND", "openvino")
    monkeypatch.setenv("BIRDLENSE_BINARY_OPENVINO_PATH", str(ov_dir))

    orig = app_config.get

    def get_override(key, default=None):
        if key == "processor.models.classifier":
            return "models/classification/weights/c.pt"
        return orig(key, default)

    monkeypatch.setattr(app_config, "get", get_override)
    snap = current_model_lineage_snapshot()
    det = snap["artifacts"]["detector"]
    assert det["detector_backend"] == "openvino"
    assert det["exists"] is True
    assert det["sha256"]
    assert Path(det["configured_path"]) == ov_dir
