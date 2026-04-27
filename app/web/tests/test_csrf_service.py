"""Production CSRF protection for browser-driven UI mutations."""


def _enable_prod_csrf(monkeypatch):
    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    monkeypatch.setenv("BIRDLENSE_STRICT_API_AUTH", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "pytest-csrf-flask-secret")
    monkeypatch.setenv("PROCESSOR_SECRET", "pytest-csrf-processor-secret")


def test_csrf_token_endpoint_sets_cookie(client, monkeypatch):
    _enable_prod_csrf(monkeypatch)
    r = client.get("/api/ui/csrf-token")
    assert r.status_code == 200
    assert r.get_json()["csrf_token"]
    assert "birdlense_csrf_token=" in r.headers.get("Set-Cookie", "")


def test_prod_ui_mutation_requires_csrf_token(client, monkeypatch):
    _enable_prod_csrf(monkeypatch)
    r = client.post("/api/ui/settings/logout")
    assert r.status_code == 403
    assert r.get_json()["error"] == "CSRF token required"


def test_prod_ui_mutation_accepts_matching_csrf_cookie_and_header(client, monkeypatch):
    _enable_prod_csrf(monkeypatch)
    token = client.get("/api/ui/csrf-token").get_json()["csrf_token"]
    r = client.post("/api/ui/settings/logout", headers={"X-Birdlense-CSRF-Token": token})
    assert r.status_code == 200


def test_processor_mutation_uses_processor_token_not_csrf(client, monkeypatch):
    _enable_prod_csrf(monkeypatch)
    monkeypatch.setenv("PROCESSOR_SECRET", "processor-token")
    r = client.post(
        "/api/processor/videos",
        json={},
        headers={"X-Processor-Token": "processor-token"},
    )
    assert r.status_code == 400
