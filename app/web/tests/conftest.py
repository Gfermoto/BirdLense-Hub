"""Pytest fixtures for web API tests."""
import os
import sys

import pytest

# Set test DB before any app imports
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

# Add project root to path (app/ on host, or /app in Docker)
_app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)
# In Docker, app_config is at /app/app_config; on host, at app/app_config
_parent = os.path.dirname(_app_root)
if _parent not in sys.path and os.path.isdir(os.path.join(_parent, 'app_config')):
    sys.path.insert(0, _parent)


@pytest.fixture
def app():
    """Create Flask app. Run: cd app && pytest web/tests, or in Docker: pytest tests/."""
    try:
        from app import create_app
    except ImportError:
        from web.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
