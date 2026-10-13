
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == (
        "GenAI Knowledge & Research Assistant API"
    )
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == (
        "GenAI Knowledge & Research Assistant"
    )
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"


def test_health_response_has_expected_fields():
    response = client.get("/health")
    data = response.json()

    assert set(data.keys()) == {
        "status",
        "app_name",
        "version",
        "environment",
    }
