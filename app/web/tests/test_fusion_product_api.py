"""Routes for product-style recognition improvement."""

from __future__ import annotations

import json

from app_config.app_config import app_config


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def _open_access():
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")


def test_recognition_improvement_summary_route_reports_feedback(app, client):
    from models import ActivityLog, db

    _open_access()
    app_config.set("detection.use_learned_fusion", True)
    app_config.set("detection.fusion_model_path", "")
    with app.app_context():
        db.session.add(
            ActivityLog(
                type="species_correction",
                data=json.dumps(
                    {
                        "action": "correct_species",
                        "detection_id": 1,
                        "video_id": 1001,
                        "to_species_name": "Mouse",
                    }
                ),
            )
        )
        db.session.commit()

    response = client.get("/api/ui/system/recognition-improvement")
    assert response.status_code == 200
    body = response.get_json()
    assert body["active_mode"] == "heuristic"
    assert body["feedback"]["corrected_examples"] == 1


def test_recognition_improvement_train_route_exposes_done_status(client, monkeypatch):
    import services.fusion_product_service as fps

    _open_access()
    monkeypatch.setattr(fps.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        fps,
        "run_recognition_training_job",
        lambda: {
            "active_mode": "trained",
            "model": {"label": "trained-v-test", "configured_path": "/tmp/fusion_state.pt"},
            "feedback": {"corrected_examples": 12},
            "settings": {"enabled": True, "alpha": 0.6},
        },
    )

    response = client.post("/api/ui/system/recognition-improvement/train")
    assert response.status_code == 202

    status = client.get("/api/ui/system/recognition-improvement/train/status")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "done"
    assert body["result"]["active_mode"] == "trained"
