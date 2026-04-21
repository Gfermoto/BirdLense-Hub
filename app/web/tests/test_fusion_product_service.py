"""Product-style recognition improvement flow built on top of fusion jobs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app_config.app_config import app_config


@pytest.fixture
def isolated_product_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    uc = tmp_path / "user_config.yaml"
    uc.write_text("detection: {}\nprocessor:\n  models: {}\n", encoding="utf-8")
    monkeypatch.setattr(app_config, "user_config_file", str(uc))
    app_config.reload()
    yield tmp_path
    app_config.reload()


def _write_species_correction(app, *, detection_id: int, video_id: int, species_name: str):
    from models import ActivityLog, db

    with app.app_context():
        db.session.add(
            ActivityLog(
                type="species_correction",
                data=json.dumps(
                    {
                        "action": "correct_species",
                        "detection_id": detection_id,
                        "video_id": video_id,
                        "to_species_name": species_name,
                    }
                ),
            )
        )
        db.session.commit()


def test_build_recognition_improvement_summary_reports_heuristic_feedback(
    app,
    isolated_product_config,
):
    from services.fusion_product_service import build_recognition_improvement_summary

    app_config.set("detection.use_learned_fusion", True)
    app_config.set("detection.fusion_model_path", "")
    _write_species_correction(app, detection_id=1, video_id=101, species_name="Mouse")
    _write_species_correction(app, detection_id=2, video_id=101, species_name="Mouse")
    _write_species_correction(app, detection_id=3, video_id=102, species_name="Great Tit")
    _write_species_correction(app, detection_id=4, video_id=103, species_name="Blue Tit")

    with app.app_context():
        summary = build_recognition_improvement_summary()

    assert summary["active_mode"] == "heuristic"
    assert summary["feedback"]["corrected_examples"] == 4
    assert summary["feedback"]["unique_videos"] == 3
    assert summary["feedback"]["unique_species"] == 3
    assert summary["feedback"]["ready_for_training"] is False
    assert summary["model"]["label"]


def test_run_recognition_training_job_exports_trains_registers_and_activates(
    app,
    monkeypatch,
    isolated_product_config,
):
    from services import fusion_product_service as fps

    export_csv = Path(isolated_product_config) / "exports" / "fusion" / "fusion_training_test.csv"
    export_csv.parent.mkdir(parents=True, exist_ok=True)
    export_csv.write_text("detector_conf,label\n0.5,1\n", encoding="utf-8")

    monkeypatch.setattr(
        fps,
        "run_fusion_export_job",
        lambda: {"output_path": str(export_csv), "rows_written": 1, "source": "decision_trace"},
    )

    def _fake_run(cmd, check, capture_output, text):
        out_dir = Path(cmd[cmd.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "fusion_state.pt").write_bytes(b"fake-model")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(fps.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        fps,
        "run_fusion_eval_job",
        lambda **kwargs: {
            "accuracy_at_0_5": 0.91,
            "ece": 0.03,
            "source_csv": kwargs.get("source_csv"),
        },
    )

    with app.app_context():
        result = fps.run_recognition_training_job()

    registry_path = Path(isolated_product_config) / "ml" / "fusion_registry.json"
    restart_flag = Path(isolated_product_config) / "restart_processor.flag"

    assert result["active_mode"] == "trained"
    assert Path(result["model"]["configured_path"]).is_file()
    assert registry_path.is_file()
    assert restart_flag.is_file()
    assert app_config.get("detection.use_learned_fusion") is True
    assert app_config.get("detection.fusion_model_path") == result["model"]["configured_path"]


def test_rollback_recognition_model_falls_back_to_heuristic_without_previous_model(
    app,
    monkeypatch,
    isolated_product_config,
):
    from services import fusion_product_service as fps

    trained_model = Path(isolated_product_config) / "ml" / "fusion" / "trained-v1" / "fusion_state.pt"
    trained_model.parent.mkdir(parents=True, exist_ok=True)
    trained_model.write_bytes(b"fake-model")

    fps._save_registry(
        {
            "active_model_id": "trained-v1",
            "models": [
                {
                    "id": "trained-v1",
                    "label": "trained-v1",
                    "model_path": str(trained_model),
                    "created_at": "2026-04-21T00:00:00+00:00",
                    "activated_at": "2026-04-21T00:00:00+00:00",
                    "status": "active",
                }
            ],
        }
    )
    app_config.set("detection.use_learned_fusion", True)
    app_config.set("detection.fusion_model_path", str(trained_model))

    with app.app_context():
        result = fps.rollback_recognition_model()

    assert result["active_mode"] == "heuristic"
    assert app_config.get("detection.use_learned_fusion") is True
    assert app_config.get("detection.fusion_model_path") == ""
