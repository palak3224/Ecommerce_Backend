import pytest

from app import create_app


@pytest.fixture
def app():
    """Flask app with testing config (in-memory SQLite, no notification scheduler)."""
    application = create_app("testing")
    yield application


@pytest.fixture
def client(app):
    return app.test_client()
