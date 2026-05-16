"""Flask-Limiter подключён; в CI тестов лимиты выключены (conftest)."""


def test_rate_limiter_disabled_in_web_tests(app):
    from extensions import limiter

    assert limiter.enabled is False
