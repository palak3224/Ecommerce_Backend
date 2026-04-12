"""Smoke tests: factory and minimal HTTP surface (Tier 1 — backend_audit_priorities)."""


def test_create_app_testing_sets_flags():
    from app import create_app

    app = create_app("testing")
    assert app.config["TESTING"] is True
    assert "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get("status") == "ok"
