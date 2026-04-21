"""Tests for UI automation bridge endpoints."""

from __future__ import annotations


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_shipped_fusion_scripts_match_container_contract():
    """Every path in REQUIRED_SHIPPED_SCRIPT_RELPATHS must exist (keep in sync with app/Dockerfile)."""
    from services import fusion_training_service as fts

    root = fts.repo_root()
    for rel in fts.REQUIRED_SHIPPED_SCRIPT_RELPATHS:
        assert (root / rel).is_file(), f"missing {rel} under {root}"


def test_fusion_processor_src_resolvable():
    """Recognition export/eval import fusion_metrics from processor/src (shipped via COPY processor/)."""
    from services import fusion_training_service as fts

    src = fts.fusion_processor_src_dir()
    assert (src / "fusion_metrics.py").is_file()
    assert (src / "fusion_model.py").is_file()


def test_repo_root_finds_script_in_container_layout(tmp_path, monkeypatch):
    """Repo root lookup should walk upward until it finds the shipped scripts dir."""
    from services import fusion_training_service as fts

    fake_module = tmp_path / "app" / "web" / "services" / "fusion_training_service.py"
    fake_script = tmp_path / "app" / "scripts" / "export_fusion_training_data.py"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    fake_module.parent.mkdir(parents=True, exist_ok=True)
    fake_module.write_text("", encoding="utf-8")

    monkeypatch.setattr(fts, "__file__", str(fake_module))

    assert fts.repo_root() == tmp_path / "app"


def test_repo_root_falls_back_to_cwd(tmp_path, monkeypatch):
    """Repo root lookup should also work when the source file path is opaque."""
    from services import fusion_training_service as fts

    fake_module = tmp_path / "site-packages" / "services" / "fusion_training_service.py"
    repo_root = tmp_path / "repo"
    fake_script = repo_root / "scripts" / "export_fusion_training_data.py"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    fake_module.parent.mkdir(parents=True, exist_ok=True)
    fake_module.write_text("", encoding="utf-8")

    monkeypatch.setattr(fts, "__file__", str(fake_module))
    monkeypatch.setattr(fts.Path, "cwd", staticmethod(lambda: repo_root))

    assert fts.repo_root() == repo_root


def test_fusion_export_route_runs_job_and_exposes_status(client, monkeypatch):
    """Fusion export should start and expose a finished status."""
    from app_config.app_config import app_config
    import services.system_fusion_telegram_jobs_service as sftj

    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    monkeypatch.setattr(sftj.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        sftj,
        "run_fusion_export_job",
        lambda: {"output_path": "/tmp/fusion.csv", "rows_written": 12},
    )

    response = client.post("/api/ui/system/fusion/export")
    assert response.status_code == 202

    status = client.get("/api/ui/system/fusion/export/status")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "done"
    assert body["result"]["rows_written"] == 12


def test_flatten_fusion_eval_report_rows_roundtrip(tmp_path):
    from services.fusion_training_service import flatten_fusion_eval_report_rows, write_fusion_eval_report_csv

    report = {
        "n": 100,
        "positive_rate": 0.4,
        "accuracy_at_0_5": 0.82,
        "brier": 0.21,
        "ece": 0.03,
        "thresholds": {
            "0.50": {
                "coverage": 0.5,
                "precision": 0.9,
                "recall": 0.7,
                "risk": 0.1,
                "count": 50,
            }
        },
        "bins": [{"bin": 0, "lo": 0.0, "hi": 0.1, "count": 10, "confidence": 0.2, "accuracy": 0.3, "gap": 0.1}],
        "risk_coverage": [{"threshold": 0.5, "coverage": 0.5, "precision": 0.9, "risk": 0.1}],
    }
    out = tmp_path / "rep.csv"
    n = write_fusion_eval_report_csv(report, out, source_csv="/data/fusion_training_x.csv")
    assert n > 0
    text = out.read_text(encoding="utf-8")
    assert "source_training_csv" in text
    assert "threshold_0.50" in text or "0.50" in text
    rows = flatten_fusion_eval_report_rows(report, "/data/fusion_training_x.csv")
    assert rows[0]["section"] == "meta"


def test_fusion_eval_download_sends_csv(client, tmp_path, monkeypatch):
    """Latest fusion eval report CSV should download when present."""
    from app_config.app_config import app_config
    import services.system_fusion_telegram_jobs_service as sftj

    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    report_csv = tmp_path / "fusion_eval_report_test.csv"
    report_csv.write_text("section,metric,value\na,b,c\n", encoding="utf-8")
    monkeypatch.setattr(sftj, "latest_fusion_eval_report_path", lambda: report_csv)

    with client.session_transaction() as sess:
        sess["access_role"] = "admin"
        sess["settings_unlocked"] = True

    response = client.get("/api/ui/system/fusion/eval/download")
    assert response.status_code == 200
    assert b"section,metric,value" in response.data


def test_fusion_eval_route_runs_job_and_exposes_status(client, monkeypatch):
    """Fusion eval should start and expose a finished status."""
    from app_config.app_config import app_config
    import services.system_fusion_telegram_jobs_service as sftj

    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    monkeypatch.setattr(sftj.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        sftj,
        "run_fusion_eval_job",
        lambda **kwargs: {
            "n": 123,
            "accuracy_at_0_5": 0.91,
            "positive_rate": 0.5,
            "brier": 0.1,
            "ece": 0.02,
            "thresholds": {},
            "bins": [],
            "risk_coverage": [],
            "source_csv": "/tmp/f.csv",
            "eval_report_csv_path": "/tmp/r.csv",
            "eval_report_csv_rows": 4,
        },
    )

    response = client.post(
        "/api/ui/system/fusion/eval",
        json={"slice_fields": ["species"]},
    )
    assert response.status_code == 202

    status = client.get("/api/ui/system/fusion/eval/status")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "done"
    assert body["result"]["accuracy_at_0_5"] == 0.91


def test_telegram_proxy_refresh_route_runs_job_and_exposes_status(client, monkeypatch):
    """Telegram proxy refresh should start and expose a finished status."""
    from app_config.app_config import app_config
    import services.system_fusion_telegram_jobs_service as sftj

    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    monkeypatch.setattr(sftj.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(
        sftj,
        "refresh_telegram_proxy_service",
        lambda: {
            "checked": 3,
            "working": 1,
            "best_proxy": "socks5h://1.2.3.4:1080",
        },
    )

    response = client.post("/api/ui/system/telegram-proxy/refresh")
    assert response.status_code == 202

    status = client.get("/api/ui/system/telegram-proxy/refresh/status")
    assert status.status_code == 200
    body = status.get_json()
    assert body["status"] == "done"
    assert body["result"]["best_proxy"] == "socks5h://1.2.3.4:1080"
