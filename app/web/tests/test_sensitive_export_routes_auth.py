"""GET timeline/export, report/pdf, unknowns — не для гостя при двух паролях (#304–306)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone


@contextmanager
def _pw_context(app_config, admin: str, contrib: str):
    old_a = app_config.get("general.settings_password")
    old_c = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", admin)
    app_config.set("general.contributor_password", contrib)
    try:
        yield
    finally:
        app_config.set("general.settings_password", old_a)
        app_config.set("general.contributor_password", old_c)


def test_timeline_export_403_anonymous_when_passwords(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se-admin", "se-contrib"):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            "/api/ui/timeline/export",
            query_string={"start_time": ts, "end_time": ts, "format": "json"},
        )
        assert r.status_code == 403
        assert r.get_json().get("error") == "Access denied"


def test_timeline_export_200_contributor_session(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se2-admin", "se2-contrib"):
        ts = int(datetime.now(timezone.utc).timestamp())
        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"
        r = client.get(
            "/api/ui/timeline/export",
            query_string={"start_time": ts, "end_time": ts, "format": "json"},
        )
        assert r.status_code == 200


def test_report_pdf_403_anonymous_when_passwords(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se3-admin", "se3-contrib"):
        r = client.get("/api/ui/report/pdf", query_string={"month": "2026-03"})
        assert r.status_code == 403
        assert r.get_json().get("error") == "Access denied"


def test_report_pdf_200_contributor_session(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se4-admin", "se4-contrib"):
        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"
        r = client.get("/api/ui/report/pdf", query_string={"month": "2026-03"})
        assert r.status_code == 200
        assert r.data[:4] == b"%PDF"


def test_unknowns_403_anonymous_when_passwords(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se5-admin", "se5-contrib"):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            "/api/ui/unknowns",
            query_string={"start_time": ts - 3600, "end_time": ts},
        )
        assert r.status_code == 403
        assert r.get_json().get("error") == "Access denied"


def test_unknowns_200_contributor_session(app, client):
    from app_config.app_config import app_config

    with _pw_context(app_config, "se6-admin", "se6-contrib"):
        ts = int(datetime.now(timezone.utc).timestamp())
        with client.session_transaction() as sess:
            sess["access_role"] = "contributor"
        r = client.get(
            "/api/ui/unknowns",
            query_string={"start_time": ts - 3600, "end_time": ts},
        )
        assert r.status_code == 200
        assert isinstance(r.json, list)
